"""Strategy selection for auto query analyze.

Provides:
- llm_classify():  LLM-based question classification (nl / semantic / semantic_nl)
- parallel_trial(): Run all 3 retrievals concurrently, LLM judges best result
- sequential_trial(): Try retrievals one by one, stop on first non-empty result
"""

import asyncio
import httpx
import re

from settings_db import get_all_settings
from models import GraphResponse, NodeDTO, RelationshipDTO


# ─── Internal helpers ────────────────────────────────────────────────────


def _records_to_graph(records: list) -> GraphResponse:
    """Convert nl2cypher raw Neo4j records to GraphResponse."""
    nodes_map: dict[str, NodeDTO] = {}
    rels_map: dict[str, RelationshipDTO] = {}

    def walk(val):
        if val is None:
            return
        if hasattr(val, "labels") and hasattr(val, "element_id"):
            props = {k: v for k, v in dict(val).items() if k not in ("elementId", "embedding")}
            for k, v in props.items():
                if type(v).__module__.startswith("neo4j."):
                    props[k] = str(v)
            nid = str(val.element_id)
            if nid not in nodes_map:
                caption = props.get("name") or props.get("title") or (list(props.values())[0] if props else "")
                nodes_map[nid] = NodeDTO(id=nid, labels=list(val.labels), properties=props, caption=str(caption))
            return
        if hasattr(val, "type") and hasattr(val, "start_node") and hasattr(val, "end_node"):
            rid = str(val.element_id)
            if rid not in rels_map:
                sp = {k: v for k, v in dict(val).items() if k != "elementId"}
                rels_map[rid] = RelationshipDTO(
                    id=rid, type=val.type,
                    source=str(val.start_node.element_id),
                    target=str(val.end_node.element_id),
                    properties=sp,
                )
                walk(val.start_node)
                walk(val.end_node)
            return
        if hasattr(val, "nodes") and hasattr(val, "relationships"):
            for n in val.nodes:
                walk(n)
            for r in val.relationships:
                walk(r)
            return
        if isinstance(val, dict):
            for v in val.values():
                walk(v)
        elif isinstance(val, (list, tuple)):
            for v in val:
                walk(v)
        elif hasattr(val, "values"):
            for v in val.values():
                walk(v)

    for record in records:
        for v in record.values():
            walk(v)
    return GraphResponse(nodes=list(nodes_map.values()), relationships=list(rels_map.values()))


def _summarize_graph(graph: GraphResponse) -> str:
    """Generate one-line summary for LLM judge."""
    if not graph.nodes:
        return "0 nodes"
    label_counts = {}
    for n in graph.nodes:
        for lbl in n.labels:
            label_counts[lbl] = label_counts.get(lbl, 0) + 1
    rel_counts = {}
    for r in graph.relationships:
        rel_counts[r.type] = rel_counts.get(r.type, 0) + 1

    nodes_part = ", ".join(f"{c}x {lbl}" for lbl, c in sorted(label_counts.items()))
    rels_part = ", ".join(f"{c}x {rt}" for rt, c in sorted(rel_counts.items())) if rel_counts else "0 rels"
    return f"{len(graph.nodes)} nodes ({nodes_part}), {len(graph.relationships)} rels ({rels_part})"


# ─── Strategy Selection ─────────────────────────────────────────────────

def _load_keywords() -> frozenset:
    """Load strategy keywords from node_templates.json."""
    import os, json
    path = os.path.join(os.path.dirname(__file__), "node_templates.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return frozenset(data.get("strategy_keywords", []))
    except Exception:
        return frozenset()


_NAMED_ENTITY_KEYWORDS = _load_keywords()


def llm_classify(question: str) -> str:
    """Rule-based classification: nl or semantic_nl."""
    for kw in _NAMED_ENTITY_KEYWORDS:
        if kw in question:
            return "semantic_nl"
    return "nl"


async def _judge_best(question: str, candidates: list[tuple[str, GraphResponse, str | None]]) -> tuple[str, GraphResponse, str | None]:
    """LLM 从多个结果中评判最优。candidates: [(method, graph, cypher), ...]"""
    s = get_all_settings()
    endpoint = s.get("llm_endpoint", "https://api.openai.com/v1").rstrip("/")
    api_key = s.get("llm_api_key", "")
    model = s.get("llm_model", "gpt-4o")

    lines = [f"Question: {question}"]
    labels = "ABCDEFGH"
    for i, (method, graph, _) in enumerate(candidates):
        lines.append(f"\nResult {labels[i]} ({method}): {_summarize_graph(graph)}")
    lines.append("\nWhich result best answers the question? Return only the letter.")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{endpoint}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "\n".join(lines)}],
                "temperature": 0,
                "max_tokens": 5,
            },
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip().upper()

    m = re.search(r"[A-H]", raw)
    idx = ord(m.group()) - ord("A") if m else 0
    if idx >= len(candidates):
        idx = 0
    return candidates[idx]


async def parallel_trial(question: str, top_k: int, score_threshold: float) -> tuple[str, GraphResponse, str | None]:
    """并行执行三种检索，LLM 评判择优。返回 (method, graph, cypher)."""
    s = get_all_settings()
    parallel_timeout = int(s.get("auto_parallel_timeout", "8"))

    async def _run_nl():
        from nl2cypher import nl2cypher as _nl2cypher
        result = await _nl2cypher(question)
        graph = _records_to_graph(result.get("records", []))
        return graph, result.get("generated_cypher", ""), "nl2cypher"

    async def _run_semantic():
        from semantic_search import semantic_search as _semantic_search
        graph = await _semantic_search(question, top_k)
        return graph, None, "semantic"

    async def _run_semantic_nl():
        from semantic_search import semantic_nl_search as _semantic_nl_search
        graph, cypher = await _semantic_nl_search(question, top_k)
        return graph, cypher, "semantic_nl"

    async def _run_with_timeout(fn):
        try:
            return await asyncio.wait_for(fn(), timeout=parallel_timeout)
        except Exception as e:
            print(f"[parallel_trial] task failed: {e}", flush=True)
            return None

    results = await asyncio.gather(
        _run_with_timeout(_run_nl),
        _run_with_timeout(_run_semantic),
        _run_with_timeout(_run_semantic_nl),
    )

    # Filter: non-None results that have nodes
    valid = []
    for r in results:
        if r is None:
            continue
        graph, cypher, method = r
        if graph.nodes:
            valid.append((method, graph, cypher))

    if not valid:
        return ("", GraphResponse(nodes=[], relationships=[]), None)

    if len(valid) == 1:
        return valid[0]

    return await _judge_best(question, valid)


async def sequential_trial(question: str, top_k: int, score_threshold: float) -> tuple[str, GraphResponse, str | None]:
    """顺序尝试三种检索，命中即止。返回 (method, graph, cypher)."""
    # 1. NL2Cypher
    from nl2cypher import nl2cypher as _nl2cypher
    result = await _nl2cypher(question)
    graph = _records_to_graph(result.get("records", []))
    if graph.nodes:
        return ("nl2cypher", graph, result.get("generated_cypher", ""))

    # 2. Semantic NL
    from semantic_search import semantic_nl_search as _semantic_nl_search
    graph, cypher = await _semantic_nl_search(question, top_k)
    if graph.nodes:
        return ("semantic_nl", graph, cypher)

    # 3. Semantic
    from semantic_search import semantic_search as _semantic_search
    graph = await _semantic_search(question, top_k)
    return ("semantic", graph, None)
