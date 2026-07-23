"""Semantic search using VectorCypherRetriever (fixed template) + semantic NL search (LLM traversal)"""

from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import VectorRetriever, VectorCypherRetriever
from neo4j_graphrag.embeddings import OpenAIEmbeddings

from settings_db import get_all_settings
from database import conn_manager
from models import GraphResponse, NodeDTO, RelationshipDTO


def _get_embedder():
    s = get_all_settings()
    endpoint = s.get("embedding_endpoint", "https://api.openai.com/v1")
    api_key = s.get("embedding_api_key", "")
    model = s.get("embedding_model", "text-embedding-3-small")
    if not api_key:
        raise ValueError("Embedding API key not configured in settings")
    return OpenAIEmbeddings(model=model, api_key=api_key, base_url=endpoint.rstrip("/") + "/")


def _serialize_props(props: dict) -> dict:
    result = {}
    for k, v in props.items():
        if isinstance(v, (list, tuple)):
            result[k] = [str(i) for i in v]
        elif isinstance(v, dict):
            result[k] = _serialize_props(v)
        elif type(v).__module__.startswith("neo4j."):
            result[k] = str(v)
        else:
            result[k] = v
    return result


def _parse_records(records: list) -> GraphResponse:
    """Extract Node/Relationship objects from Neo4j records (same as main.py)."""
    nodes_map: dict[str, NodeDTO] = {}
    rels_map: dict[str, RelationshipDTO] = {}

    def walk(val):
        if val is None:
            return
        if hasattr(val, "labels") and hasattr(val, "element_id"):
            props = _serialize_props(dict(val))
            nid = str(val.element_id)
            if nid not in nodes_map:
                caption = props.get("name") or props.get("title") or (list(props.values())[0] if props else "")
                nodes_map[nid] = NodeDTO(id=nid, labels=list(val.labels), properties=props, caption=str(caption))
            return
        if hasattr(val, "type") and hasattr(val, "start_node") and hasattr(val, "end_node"):
            rid = str(val.element_id)
            if rid not in rels_map:
                rels_map[rid] = RelationshipDTO(
                    id=rid, type=val.type,
                    source=str(val.start_node.element_id),
                    target=str(val.end_node.element_id),
                    properties=_serialize_props(dict(val)),
                )
                walk(val.start_node)
                walk(val.end_node)
            return
        if hasattr(val, "nodes") and hasattr(val, "relationships"):
            for n in val.nodes: walk(n)
            for r in val.relationships: walk(r)
            return
        if isinstance(val, dict):
            for v in val.values(): walk(v)
        elif isinstance(val, (list, tuple)):
            for v in val: walk(v)
        elif hasattr(val, "values"):
            for v in val.values(): walk(v)

    for record in records:
        for v in record.values():
            walk(v)
    return GraphResponse(nodes=list(nodes_map.values()), relationships=list(rels_map.values()))


# ─── Interface 1: Fixed template (hops configurable) ────────────────────────

# Hardcoded traversal template, {hops} replaced at runtime
FIXED_TPL = """
OPTIONAL MATCH (node)-[*1..{hops}]-(related)
WHERE related IS NOT NULL
RETURN node, collect(DISTINCT related) AS related_nodes, score
"""


from typing import Optional

async def semantic_search(question: str, top_k: Optional[int] = None) -> GraphResponse:
    """Vector search → filter by score threshold → n-hop traversal."""
    s = get_all_settings()
    index_name = s.get("vector_index_name", "entity_vector")
    hops = int(s.get("semantic_query_hops", "1"))
    threshold = float(s.get("semantic_score_threshold", "0.6"))
    if top_k is None:
        top_k = int(s.get("semantic_top_k", "10"))
    if not index_name:
        raise ValueError("Vector index name not configured in settings")

    embedder = _get_embedder()
    driver = GraphDatabase.driver(
        s.get("neo4j_uri", "bolt://localhost:7687"),
        auth=(s.get("neo4j_username", "neo4j"), s.get("neo4j_password", "")),
        max_connection_lifetime=3600, max_connection_pool_size=10,
    )
    try:
        # 1. Vector search - fetch enough candidates, then filter by score
        vretriever = VectorRetriever(driver=driver, index_name=index_name, embedder=embedder)
        raw = vretriever.get_search_results(query_text=question, top_k=max(top_k, 100))

        # Filter by score threshold, keep minimum 3 results
        scored = []
        for record in raw.records:
            eid = record.get("elementId")
            score = record.get("score", 0)
            if eid and score is not None:
                scored.append((str(eid), score))
        scored.sort(key=lambda x: x[1], reverse=True)

        print("=== [Semantic scores] ===", flush=True)
        for eid, s in scored[:10]:
            print(f"  score={s:.4f} eid={eid[:20]}...", flush=True)

        filtered = [eid for eid, s in scored if s >= threshold]
        if not filtered and scored:
            filtered = [scored[0][0]]
            print(f"  [threshold={threshold} too high, fallback to top-1]", flush=True)

        print(f"  threshold={threshold}, filtered={len(filtered)}, total_candidates={len(scored)}", flush=True)
        node_ids = filtered[:top_k]

        if not node_ids:
            return GraphResponse(nodes=[], relationships=[])

        # 2. Traverse from entry nodes with parameterized Cypher
        if hops == 1:
            traverse = """
MATCH (node) WHERE elementId(node) IN $node_ids
OPTIONAL MATCH (node)-[r]-(related)
WHERE related IS NOT NULL AND NOT related = node
RETURN node, collect(DISTINCT r) AS rels, collect(DISTINCT related) AS related_nodes
"""
        else:
            traverse = f"""
MATCH (node) WHERE elementId(node) IN $node_ids
OPTIONAL MATCH (node)-[r*1..{hops}]-(related)
WHERE related IS NOT NULL AND NOT related = node
UNWIND r AS single_rel
RETURN node, collect(DISTINCT single_rel) AS rels, collect(DISTINCT related) AS related_nodes
"""
        records, _ = await conn_manager.run_query(cypher=traverse, parameters={"node_ids": node_ids})
        return _parse_records(records if records else [])
    finally:
        driver.close()


# ─── Interface 2: LLM-generated traversal ──────────────────────────────────

import json
from openai import OpenAI as OpenAIClient
from nl2cypher import _get_schema, _fix_unnamed_rels


async def semantic_nl_search(question: str, top_k: Optional[int] = None) -> tuple[GraphResponse, str]:
    """Vector search → LLM generates traversal Cypher → execute.

    Returns (GraphResponse, generated_cypher).
    """
    s = get_all_settings()
    uri = s.get("neo4j_uri", "bolt://localhost:7687")
    user = s.get("neo4j_username", "neo4j")
    pwd = s.get("neo4j_password", "")
    db = s.get("neo4j_database", "neo4j")
    index_name = s.get("vector_index_name", "entity_vector")
    if top_k is None:
        top_k = int(s.get("semantic_top_k", "10"))

    embedder = _get_embedder()
    sync_driver = GraphDatabase.driver(uri, auth=(user, pwd), max_connection_lifetime=3600, max_connection_pool_size=10)
    try:
        # 1. Vector search with score threshold
        threshold = float(s.get("semantic_score_threshold", "0.6"))
        retriever = VectorRetriever(driver=sync_driver, index_name=index_name, embedder=embedder)
        raw = retriever.get_search_results(query_text=question, top_k=max(top_k, 100))

        # Filter by score threshold
        scored = []
        for rec in raw.records:
            eid = rec.get("elementId")
            score = rec.get("score", 0)
            node = rec.get("node", {})
            node_labels = rec.get("nodeLabels", [])
            if eid and isinstance(node, dict) and node:
                scored.append((str(eid), score, node, node_labels))
        scored.sort(key=lambda x: x[1], reverse=True)

        filtered_records = [r for r in scored if r[1] >= threshold]
        if not filtered_records and scored:
            filtered_records = [scored[0]]

        # 2. Build entry node context
        entry_lines = []
        node_ids = []
        for eid, score, node, node_labels in filtered_records[:top_k]:
            node_ids.append(str(eid))
            props_dict = {k: v for k, v in node.items() if k != "embedding"}
            props_str = ", ".join(f"{k}: {v}" for k, v in props_dict.items())
            labels_str = ", ".join(node_labels)
            entry_lines.append(f"  [{labels_str}] elementId: {eid} {{{props_str}}}  [score: {score:.4f}]")
        entry_context = "\n".join(entry_lines) if entry_lines else "  (no nodes found)"

        # 3. Get schema
        schema = _get_schema(sync_driver, db, include_samples=False)
        from nl2cypher import _get_examples
        examples = _get_examples()

        # 4. Build prompt — prescriptive template forces LLM to use the entry node IDs
        node_id_list = json.dumps(node_ids)
        examples_str = "\n".join(examples) if examples else "(no examples)"
        prompt = f"""Task: Write a Cypher query that starts from specific entry nodes and traverses relationships to answer the user question.

Schema:
{schema}

Examples:
{examples_str}

The entry nodes (start here):
{entry_context}

User question:
{question}

CRITICAL: Start with the EXACT pattern:
  MATCH (entry) WHERE elementId(entry) IN {node_id_list}
Then use OPTIONAL MATCH to traverse relationships from entry.
Do NOT add any extra WHERE conditions on the entry node.

Rules:
- Keep WHERE elementId(entry) IN {node_id_list} exactly as given
- Use OPTIONAL MATCH (not MATCH) so entry nodes are always returned
- RETURN entry, related nodes, and relationship variables
- Add LIMIT 200
- Only Cypher statement, no markdown"""

        oai = OpenAIClient(
            api_key=s.get("llm_api_key", ""),
            base_url=s.get("llm_endpoint", "https://api.openai.com/v1") + "/",
        )
        resp = oai.chat.completions.create(
            model=s.get("llm_model", "gpt-4o"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        generated_cypher = resp.choices[0].message.content.strip()
        # Strip markdown fences
        if generated_cypher.startswith("```"):
            generated_cypher = generated_cypher.split("\n", 1)[-1]
            if "```" in generated_cypher:
                generated_cypher = generated_cypher.rsplit("```", 1)[0]
            generated_cypher = generated_cypher.strip()

        # 5. Execute (pass node_ids as parameter for $node_ids)
        from nl2cypher import _fix_unnamed_rels
        generated_cypher = _fix_unnamed_rels(generated_cypher)
        records, _ = await conn_manager.run_query(cypher=generated_cypher, parameters={"node_ids": node_ids})
        return _parse_records(records), generated_cypher
    finally:
        sync_driver.close()
