"""Semantic search using VectorCypherRetriever (fixed template) + semantic NL search (LLM traversal)"""

from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import VectorRetriever, VectorCypherRetriever
from neo4j_graphrag.embeddings import OpenAIEmbeddings

from backend.settings_db import get_all_settings
from backend.database import conn_manager
from backend.models import GraphResponse, NodeDTO, RelationshipDTO


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


async def semantic_search(question: str, top_k: int = 10) -> GraphResponse:
    """Vector search → find entry nodes → n-hop traversal."""
    s = get_all_settings()
    index_name = s.get("vector_index_name", "entity_vector")
    hops = int(s.get("semantic_query_hops", "1"))
    if not index_name:
        raise ValueError("Vector index name not configured in settings")

    embedder = _get_embedder()
    driver = GraphDatabase.driver(
        s.get("neo4j_uri", "bolt://localhost:7687"),
        auth=(s.get("neo4j_username", "neo4j"), s.get("neo4j_password", "")),
        max_connection_lifetime=3600, max_connection_pool_size=10,
    )
    try:
        vretriever = VectorRetriever(driver=driver, index_name=index_name, embedder=embedder)
        hits = vretriever.search(query_text=question, top_k=top_k)

        node_ids = []
        for item in hits.items:
            node = item.content
            if hasattr(node, "element_id"):
                node_ids.append(str(node.element_id))

        if not node_ids:
            return GraphResponse(nodes=[], relationships=[])

        traverse = f"""
MATCH (node) WHERE elementId(node) IN $node_ids
OPTIONAL MATCH (node)-[*1..{hops}]-(related)
WHERE related IS NOT NULL AND NOT related = node
RETURN node, collect(DISTINCT related) AS related_nodes
"""
        records, _ = await conn_manager.run_query(cypher=traverse, parameters={"node_ids": node_ids})
        return _parse_records(records if records else [])
    finally:
        driver.close()


from openai import OpenAIClient
from backend.nl2cypher import _get_schema, _fix_unnamed_rels


async def semantic_nl_search(question: str, top_k: int = 5) -> tuple[GraphResponse, str]:
    s = get_all_settings()
    uri = s.get("neo4j_uri", "bolt://localhost:7687")
    user = s.get("neo4j_username", "neo4j")
    pwd = s.get("neo4j_password", "")
    db = s.get("neo4j_database", "neo4j")
    index_name = s.get("vector_index_name", "entity_vector")

    embedder = _get_embedder()
    sync_driver = GraphDatabase.driver(uri, auth=(user, pwd), max_connection_lifetime=3600, max_connection_pool_size=10)
    try:
        retriever = VectorRetriever(driver=sync_driver, index_name=index_name, embedder=embedder)
        hits = retriever.search(query_text=question, top_k=top_k)

        entry_lines = []
        for item in hits.items:
            node = item.content
            if hasattr(node, "labels"):
                props_dict = dict(node)
                props_dict.pop("embedding", None)
                props_str = ", ".join(f"{k}: {v}" for k, v in props_dict.items())
                labels_str = ", ".join(node.labels)
                entry_lines.append(f"  [{labels_str}] elementId: {node.element_id} {{{props_str}}}  [score: {item.metadata.get('score', 0):.4f}]")
        entry_context = "\n".join(entry_lines) if entry_lines else "  (no nodes found)"

        schema = _get_schema(sync_driver, db, include_samples=False)
        from backend.nl2cypher import _get_examples
        examples = _get_examples()

        examples_str = "\n".join(examples) if examples else "(no examples)"
        prompt = f"""Task: Based on the entry node(s) found below, generate a Cypher query to traverse the graph and answer the user question.

Schema:
{schema}

Examples of good Cypher queries:
{examples_str}

Entry node(s) found by vector search (start from these):
{entry_context}

User question:
{question}

Rules:
- Use WHERE elementId(n) IN [...] to reference the entry nodes
- MATCH to traverse relationships
- RETURN all node and relationship variables so the graph can be rendered
- Include relationship variables in RETURN
- Always add LIMIT 200
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
        if generated_cypher.startswith("```"):
            generated_cypher = generated_cypher.split("\n", 1)[-1]
            if "```" in generated_cypher:
                generated_cypher = generated_cypher.rsplit("```", 1)[0]
            generated_cypher = generated_cypher.strip()

        generated_cypher = _fix_unnamed_rels(generated_cypher)
        records, _ = await conn_manager.run_query(cypher=generated_cypher)
        return _parse_records(records), generated_cypher
    finally:
        sync_driver.close()
