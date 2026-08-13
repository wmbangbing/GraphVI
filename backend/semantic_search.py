"""Semantic search using VectorCypherRetriever (fixed template) + semantic NL search (LLM traversal)"""

import asyncio
import httpx
from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import VectorRetriever, VectorCypherRetriever
from neo4j_graphrag.embeddings import OpenAIEmbeddings

from settings_db import get_all_settings
from database import conn_manager
from models import GraphResponse, NodeDTO, RelationshipDTO

_embed_client = None
_embed_client_key = ""


def _invalidate_embed_client():
    """Force recreation of the cached embedding httpx client."""
    global _embed_client, _embed_client_key
    if _embed_client is not None:
        import asyncio
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            pass
        _embed_client = None
    _embed_client_key = ""


def _get_embed_client(endpoint: str, api_key: str) -> httpx.Client:
    """Get or create a cached sync httpx client for embedding API calls."""
    global _embed_client, _embed_client_key
    key = f"{endpoint}|{api_key[:8]}"
    if _embed_client is None or _embed_client_key != key:
        _embed_client = httpx.Client(
            timeout=30,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )
        _embed_client_key = key
    return _embed_client


class _HttpxEmbedder:
    """Custom embedder using httpx directly, with connection reuse."""
    def __init__(self, endpoint: str, api_key: str, model: str):
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._model = model

    def embed_query(self, text: str) -> list[float]:
        client = _get_embed_client(self._endpoint, self._api_key)
        r = client.post(
            f"{self._endpoint}/embeddings",
            json={"model": self._model, "input": text},
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]


def _get_embedder():
    s = get_all_settings()
    endpoint = s.get("embedding_endpoint", "https://api.openai.com/v1")
    api_key = s.get("embedding_api_key", "")
    model = s.get("embedding_model", "text-embedding-3-small")
    if not api_key:
        raise ValueError("Embedding API key not configured in settings")
    return _HttpxEmbedder(endpoint, api_key, model)


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
    """Extract Node/Relationship objects from Neo4j records (same as main.py).

    Supports BOTH native Neo4j Node/Relationship objects AND map-format nodes
    produced by the APOC embedding-exclusion fix:
      {id: elementId, labels: [...], props: {...}}
    """
    nodes_map: dict[str, NodeDTO] = {}
    rels_map: dict[str, RelationshipDTO] = {}

    def extract_map_node(val):
        """Recognize {id, labels, props} map nodes (from APOC removeKeys fix)."""
        if not isinstance(val, dict):
            return None
        if "props" in val and ("labels" in val or "id" in val):
            props = _serialize_props(dict(val.get("props") or {}))
            props.pop("embedding", None)
            nid = str(val.get("id", ""))
            labels = list(val.get("labels") or [])
            if not nid:
                return None
            caption = (props.get("name") or props.get("title") or props.get("event_name")
                       or props.get("person_name") or props.get("equipment_name")
                       or props.get("vehicle_name") or (list(props.values())[0] if props else ""))
            return NodeDTO(id=nid, labels=labels, properties=props, caption=str(caption))
        return None

    def walk(val):
        if val is None:
            return
        # Map-format node (APOC wrapped) — check before generic dict walk
        mn = extract_map_node(val)
        if mn and mn.id:
            if mn.id not in nodes_map:
                nodes_map[mn.id] = mn
            return
        if hasattr(val, "labels") and hasattr(val, "element_id"):
            # Skip stub nodes (relationship endpoints inside collect() have no
            # labels/props) — they'd produce empty graph nodes.
            if not val.labels:
                return
            props = _serialize_props(dict(val))
            props.pop("embedding", None)
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
    query_limit = int(s.get("semantic_query_limit", "2000"))
    if top_k is None:
        top_k = int(s.get("semantic_top_k", "10"))
    if not index_name:
        raise ValueError("Vector index name not configured in settings")

    embedder = _get_embedder()
    from nl2cypher import _get_cached_driver
    driver = _get_cached_driver(
        s.get("neo4j_uri", "bolt://localhost:7687"),
        s.get("neo4j_username", "neo4j"),
        s.get("neo4j_password", ""),
    )

    # 1. 共享检索入口：问题分解 + 向量检索(retrieval_query) + rerank 精排过滤
    entries = await _retrieve_entries(question, top_k, threshold)
    node_ids = [e["eid"] for e in entries if e.get("eid")]
    print(f"=== [Semantic entries] 检索入口返回 {len(entries)} 个 entry ===", flush=True)

    if not node_ids:
        return GraphResponse(nodes=[], relationships=[])

    # 2. Traverse from entry nodes with parameterized Cypher
    if hops == 1:
        traverse = f"""
MATCH (node) WHERE elementId(node) IN $node_ids
OPTIONAL MATCH (node)-[r]-(related)
WHERE related IS NOT NULL AND NOT related = node
RETURN node, collect(DISTINCT r) AS rels, collect(DISTINCT related) AS related_nodes
LIMIT {query_limit}
"""
    else:
        traverse = f"""
MATCH (node) WHERE elementId(node) IN $node_ids
OPTIONAL MATCH (node)-[r*1..{hops}]-(related)
WHERE related IS NOT NULL AND NOT related = node
UNWIND r AS single_rel
RETURN node, collect(DISTINCT single_rel) AS rels, collect(DISTINCT related) AS related_nodes
LIMIT {query_limit}
"""
    records, _ = await conn_manager.run_query(cypher=traverse, parameters={"node_ids": node_ids})
    return _parse_records(records if records else [])


def invalidate_schema_cache():
    """Clear the shared schema cache (called when schema_include changes)."""
    from nl2cypher import invalidate_schema_cache as _invalidate_nl_schema
    _invalidate_nl_schema()


# ─── Interface 2: LLM-generated traversal ──────────────────────────────────

import json
from openai import OpenAI as OpenAIClient
from nl2cypher import get_schema, _fix_unnamed_rels


def _inject_entry_labels(cypher: str, entry_labels: list[str]) -> str:
    """Add label constraints to the entry MATCH so the planner can use the
    RANGE index on entry.id.

    Without a label, `MATCH (entry) WHERE entry.id IN [...]` scans every node
    (10M+) — measured ~15-17s. With the label it uses the RANGE index and runs
    in <1s. Single label: `(entry)` -> `(entry:Label)`. Multiple labels: keep
    the bare entry but add an OR filter so the planner uses index-union.
    """
    import re as _re
    if not entry_labels or "entry.id IN" not in cypher:
        return cypher
    if len(entry_labels) == 1:
        lbl = entry_labels[0]
        return _re.sub(
            r"MATCH\s*\(\s*entry\s*\)\s*WHERE\s+entry\.id\s+IN",
            f"MATCH (entry:{lbl}) WHERE entry.id IN", cypher, count=1)
    m = _re.search(r"MATCH\s*\(\s*entry\s*\)\s*WHERE\s+entry\.id\s+IN\s*(\[[^\]]*\])", cypher)
    if not m:
        return cypher
    or_clause = " OR ".join(f"entry:{l}" for l in entry_labels)
    return (cypher[:m.start()] +
            f"MATCH (entry) WHERE entry.id IN {m.group(1)} AND ({or_clause})" +
            cypher[m.end():])


def _node_full_text(node: dict) -> str:
    """节点全量属性（排除 embedding）转文本，用于 rerank 相关性判断。"""
    props = {k: v for k, v in node.items() if k != "embedding"}
    return json.dumps(props, ensure_ascii=False, default=str)


async def analyze_question(question: str) -> str:
    """LLM 问题分解：提取干净 retrieval_query。关闭开关/失败时返回原始问题。"""
    s = get_all_settings()
    if s.get("enable_semantic_rerank", "true") != "true":
        return question
    from llm_service import _call_llm_async
    prompt = (
        "提取用于向量检索的简洁查询语句：聚焦问题的核心实体和主题词，"
        "必须保留目标实体类型词（如'事件/人员/装备/车辆'，不要去掉），"
        "只去掉查询指令词（查询/查找/返回等）和无关的资源描述（如'事件下的物资装备车辆'）。"
        f"只输出查询语句本身，不要解释。\n问题: {question}\n查询语句:"
    )
    try:
        raw = await _call_llm_async(prompt, temperature=0, max_tokens=100)
        raw = raw.strip().strip('"').strip("'").strip()
        return raw if raw else question
    except Exception:
        return question


async def rerank_filter(candidates: list, question: str) -> list:
    """Qwen3-Reranker 精排 + 阈值过滤（按 rerank 分数降序）。
    关闭开关/未配置/失败时返回原候选。"""
    s = get_all_settings()
    if s.get("enable_semantic_rerank", "true") != "true":
        return candidates
    endpoint = s.get("rerank_endpoint", "").rstrip("/")
    api_key = s.get("rerank_api_key", "")
    model = s.get("rerank_model", "Qwen/Qwen3-Reranker-4B")
    threshold = float(s.get("rerank_threshold", "0.8"))
    if not endpoint or not api_key or not candidates:
        return candidates
    try:
        client = _get_embed_client(endpoint, api_key)
        documents = [_node_full_text(c["node"]) for c in candidates]

        def _call_rerank():
            resp = client.post(
                f"{endpoint}/rerank",
                json={"model": model, "query": question,
                      "documents": documents, "top_n": len(documents)},
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return [(item["index"], item.get("relevance_score", 0))
                    for item in resp.json().get("results", [])]

        reranked = await asyncio.to_thread(_call_rerank)
        kept = [candidates[i] for i, score in reranked if score >= threshold]
        return kept if kept else candidates
    except Exception:
        return candidates


async def _retrieve_entries(question: str, top_k: int, threshold: float) -> list:
    """共享检索入口：问题分解 → 向量检索(retrieval_query) → rerank 精排+阈值过滤。
    返回 [{node: dict, score: float}, ...]（按 rerank 分数降序，最多 top_k 个）。"""
    import time as _time
    _t0 = _time.monotonic()
    s = get_all_settings()
    uri = s.get("neo4j_uri", "bolt://localhost:7687")
    user = s.get("neo4j_username", "neo4j")
    pwd = s.get("neo4j_password", "")
    index_name = s.get("vector_index_name", "entity_vector")
    from nl2cypher import _get_cached_driver
    embedder = _get_embedder()
    driver = _get_cached_driver(uri, user, pwd)

    # 1. 问题分解 → 干净 retrieval_query
    retrieval_query = await analyze_question(question)
    _t1 = _time.monotonic()
    print(f"=== [Retrieve] 问题分解: {_t1 - _t0:.2f}s → query='{retrieval_query}' ===", flush=True)

    # 2. 向量检索（top_k 直接控制候选数量）
    retriever = VectorRetriever(driver=driver, index_name=index_name, embedder=embedder)
    raw = await asyncio.to_thread(
        retriever.get_search_results, query_text=retrieval_query, top_k=top_k
    )
    _t2 = _time.monotonic()

    # 3. 收集候选（node dict + labels + elementId）
    candidates = []
    for rec in raw.records:
        node = rec.get("node", {})
        if isinstance(node, dict) and node:
            candidates.append({"node": node, "score": rec.get("score", 0),
                               "labels": list(rec.get("nodeLabels", [])),
                               "eid": rec.get("elementId", "")})
    candidates.sort(key=lambda x: x["score"], reverse=True)
    print(f"=== [Retrieve] 向量检索: {_t2 - _t1:.2f}s, 候选 {len(candidates)} 个 ===", flush=True)

    # 4. 向量分数基础过滤（threshold 兜底）
    passed = [c for c in candidates if c["score"] >= threshold]
    if not passed and candidates:
        passed = [candidates[0]]
    print(f"=== [Retrieve] 向量阈值过滤: {len(passed)}/{len(candidates)} (threshold={threshold}) ===", flush=True)

    # 5. rerank 精排 + 阈值过滤
    kept = await rerank_filter(passed, question)
    _t3 = _time.monotonic()
    print(f"=== [Retrieve] rerank+过滤: {_t3 - _t2:.2f}s, entry {len(kept)} 个 ===", flush=True)

    return kept[:top_k]


async def semantic_nl_search(question: str, top_k: Optional[int] = None) -> tuple[GraphResponse, str]:
    """Vector search �?LLM generates traversal Cypher �?execute.

    Returns (GraphResponse, generated_cypher).
    """
    import time as _time
    _t_start = _time.monotonic()
    s = get_all_settings()
    uri = s.get("neo4j_uri", "bolt://localhost:7687")
    user = s.get("neo4j_username", "neo4j")
    pwd = s.get("neo4j_password", "")
    db = s.get("neo4j_database", "neo4j")
    index_name = s.get("vector_index_name", "entity_vector")
    if top_k is None:
        top_k = int(s.get("semantic_top_k", "10"))

    embedder = _get_embedder()
    from nl2cypher import _get_cached_driver
    sync_driver = _get_cached_driver(uri, user, pwd)

    # 1. 共享检索入口：问题分解 + 向量检索(retrieval_query) + rerank 精排过滤
    threshold = float(s.get("semantic_score_threshold", "0.6"))
    entries = await _retrieve_entries(question, top_k, threshold)
    scored = [(str(e["node"].get("id", "")), e["score"], e["node"], e["labels"])
              for e in entries]
    filtered_records = scored

    # 2. Build entry node context
    # Use the node's `id` property (UUID, RANGE-indexed) for querying, not elementId.
    entry_lines = []
    node_ids = []
    entry_labels: list[str] = []
    for eid, score, node, node_labels in filtered_records[:top_k]:
        props_dict = {k: v for k, v in node.items() if k != "embedding"}
        uid = str(props_dict.get("id", eid))  # indexed UUID field
        node_ids.append(uid)
        entry_labels.extend(l for l in (node_labels or []) if l != "_Embeddable")
        props_str = ", ".join(f"{k}: {v}" for k, v in props_dict.items())
        labels_str = ", ".join(node_labels)
        entry_lines.append(f"  [{labels_str}] id: {uid} elementId: {eid} {{{props_str}}}  [score: {score:.4f}]")
    entry_labels = sorted(set(entry_labels))
    entry_context = "\n".join(entry_lines) if entry_lines else "  (no nodes found)"

    # 3. Get schema (shared cache with nl2cypher)
    schema = await get_schema(sync_driver, db, include_samples=False)
    node_id_list = json.dumps(node_ids)

    # 4. Build prompt
    query_limit = int(s.get("semantic_query_limit", "2000"))
    prompt = f"""Task: Write a Cypher query that starts from specific entry nodes and traverses ONLY the relationships needed to answer the user question.

Schema:
{schema}

The entry nodes (start here):
{entry_context}

User question:
{question}

CRITICAL SELECTIVITY RULES:
- Traverse ONLY the relationship chains that are semantically relevant to the question.
  Ignore unrelated relationship types entirely.
- MINIMIZE the number of CALL subqueries (usually 1-3). Do NOT enumerate every
  relationship type from the schema.
- Example: if the question only asks about parent/child events, use ONLY PARENT_OF,
  e.g. MATCH (entry)-[:PARENT_OF]->(child_event) and/or <-[:PARENT_OF]-(parent_event).
  Do NOT traverse dispatch / work-order / attachment relationships in that case.

When you DO need a CALL, use this form (EXPLICIT scope, one CALL per relevant chain):
  CALL (entry) {{
    OPTIONAL MATCH (entry)-[:RELEVANT_REL]->(n1:Label1)-...->(target:LabelN)
    RETURN collect(DISTINCT target) AS name
  }}

Structure:
  MATCH (entry) WHERE entry.id IN {node_id_list}
  CALL (entry) {{
    OPTIONAL MATCH (entry)-[:RELEVANT_REL]->(...)->(target)
    RETURN collect(DISTINCT target) AS name
  }}
  RETURN name
  LIMIT {query_limit}

Rules:
- Start with: MATCH (entry) WHERE entry.id IN {node_id_list}
  (entry.id is the indexed UUID property. Do NOT use elementId(entry).)
- Use CALL (entry) {{ ... }} with EXPLICIT variable scope in parentheses.
  Do NOT use CALL {{ WITH entry ... }} — the old implicit-scope form is deprecated.
- Use OPTIONAL MATCH (not MATCH) inside CALL so entry is always returned
- Use full paths in each CALL, don't split a chain across multiple CALLs
- RETURN collect(DISTINCT target) AS name for each terminal target
- The main RETURN only needs the alias names from each CALL's RETURN
- When mixing multiple OR conditions with AND in WHERE, wrap the OR group in
  parentheses: (A OR B OR C) AND D
- Add LIMIT {query_limit} at the end
- Only Cypher statement, no markdown"""

    from llm_service import _call_llm_async
    import os, datetime
    _log_dir = os.path.join(os.path.dirname(__file__), "_prompt_logs")
    os.makedirs(_log_dir, exist_ok=True)
    _log_path = os.path.join(_log_dir, f"prompt_{datetime.datetime.now():%H%M%S%f}.txt")
    with open(_log_path, "w", encoding="utf-8") as _f:
        _f.write(prompt)
    _t_llm_start = _time.monotonic()
    generated_cypher = await _call_llm_async(prompt, temperature=0, max_tokens=8192)
    _t_llm_end = _time.monotonic()
    print(f"=== [SemanticNL] LLM 调用耗时: {_t_llm_end - _t_llm_start:.2f}s ===", flush=True)
    # Strip markdown fences
    if generated_cypher.startswith("```"):
        generated_cypher = generated_cypher.split("\n", 1)[-1]
        if "```" in generated_cypher:
            generated_cypher = generated_cypher.rsplit("```", 1)[0]
        generated_cypher = generated_cypher.strip()

    # 5. Execute (pass node_ids as parameter for $node_ids)
    from nl2cypher import _fix_unnamed_rels
    generated_cypher = _fix_unnamed_rels(generated_cypher)
    # Inject label constraints so the entry lookup uses the RANGE index (10x+
    # faster than the unlabelled full scan on a 10M-node graph).
    generated_cypher = _inject_entry_labels(generated_cypher, entry_labels)
    _t_cypher_start = _time.monotonic()
    records, _ = await conn_manager.run_query(cypher=generated_cypher, parameters={"node_ids": node_ids})
    _t_cypher_end = _time.monotonic()
    print(f"=== [SemanticNL] Neo4j 查询耗时: {_t_cypher_end - _t_cypher_start:.2f}s ===", flush=True)
    print(f"=== [SemanticNL] 总耗时: {_t_cypher_end - _t_start:.2f}s ===", flush=True)
    return _parse_records(records), generated_cypher
