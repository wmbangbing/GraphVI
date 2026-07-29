"""Auto query analyze — orchestration entry for /api/query/auto."""

import json
from typing import AsyncGenerator

from backend.cache import get as cache_get, set as cache_set
from backend.models import GraphResponse
from backend.settings_db import get_all_settings


def _resolve_params(
    strategy: str, top_k: int | None, score_threshold: float | None
) -> tuple[str, int, float]:
    """Resolve parameter defaults from settings."""
    s = get_all_settings()
    if strategy not in ("auto", "parallel", "sequential"):
        strategy = s.get("auto_default_strategy", "auto")
    if top_k is None:
        top_k = int(s.get("auto_semantic_top_k", s.get("semantic_top_k", "10")))
    if score_threshold is None:
        score_threshold = float(
            s.get("auto_semantic_score_threshold", s.get("semantic_score_threshold", "0.6"))
        )
    return strategy, top_k, score_threshold


async def auto_analyze(
    question: str,
    strategy: str = "auto",
    top_k: int | None = None,
    score_threshold: float | None = None,
    analyze_prompt: str | None = None,
    summary_prompt: str | None = None,
    stream: bool = False,
) -> AsyncGenerator[dict, None] | dict:
    """Unified entry: dispatches to streaming or non-streaming mode.

    - analyze_prompt: domain context for stats script generation
    - summary_prompt: template for final text summary
    """
    if stream:
        return auto_analyze_stream(
            question, strategy, top_k, score_threshold, analyze_prompt, summary_prompt
        )
    return await auto_analyze_nonstream(
        question, strategy, top_k, score_threshold, analyze_prompt, summary_prompt
    )


async def auto_analyze_nonstream(
    question: str,
    strategy: str = "auto",
    top_k: int | None = None,
    score_threshold: float | None = None,
    analyze_prompt: str | None = None,
    summary_prompt: str | None = None,
) -> dict:
    """Non-streaming mode with file-based caching."""
    strategy, top_k, score_threshold = _resolve_params(strategy, top_k, score_threshold)

    cache_key = f"{question}|{strategy}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    events = []
    async for event in _pipeline(question, strategy, top_k, score_threshold, analyze_prompt, summary_prompt):
        events.append(event)
    result = _assemble_nonstream(events)

    from backend.settings_db import get_all_settings
    ttl = int(get_all_settings().get("cache_ttl", "300"))
    if ttl > 0:
        cache_set(cache_key, result, ttl)

    return result


async def auto_analyze_stream(
    question: str,
    strategy: str = "auto",
    top_k: int | None = None,
    score_threshold: float | None = None,
    analyze_prompt: str | None = None,
    summary_prompt: str | None = None,
) -> AsyncGenerator[dict, None]:
    """SSE streaming mode with file-based caching."""
    strategy, top_k, score_threshold = _resolve_params(strategy, top_k, score_threshold)
    cache_key = f"stream:{question}|{strategy}"

    cached = cache_get(cache_key)
    if cached is not None:
        for ev in cached:
            yield ev
        return

    events = []
    async for event in _pipeline(question, strategy, top_k, score_threshold, analyze_prompt, summary_prompt):
        events.append(event)
        yield event

    from backend.settings_db import get_all_settings
    ttl = int(get_all_settings().get("cache_ttl", "300"))
    if ttl > 0:
        cache_set(cache_key, events, ttl)


def _assemble_nonstream(events: list[dict]) -> dict:
    """Assemble SSE events into a single non-streaming response dict."""
    result = ""
    strategy_used = ""

    for ev in events:
        ev_type = ev.get("event", "")
        data = ev.get("data", {})
        if ev_type == "strategy":
            strategy_used = data.get("strategy", strategy_used)
        elif ev_type == "text":
            chunk = data if isinstance(data, str) else ""
            result += chunk

    return {
        "result": result,
        "strategy_used": strategy_used,
    }


async def _pipeline(
    question: str,
    strategy: str,
    top_k: int,
    score_threshold: float,
    analyze_prompt: str | None,
    summary_prompt: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Internal pipeline: strategy → retrieve → stats → text."""
    s = get_all_settings()
    from backend.strategy_selector import llm_classify, parallel_trial, sequential_trial

    # ─── Phase 1: Strategy Selection ─────────────────────────────────────
    yield {"event": "strategy_start", "data": {"message": "正在分析查询策略..."}}
    if strategy == "auto":
        method = llm_classify(question)
        yield {"event": "strategy", "data": {"strategy": method}}
        yield {"event": "retrieve_start", "data": {"message": f"正在查询数据（策略：{method}）..."}}
        graph_data, cypher = await _single_retrieve(question, method, top_k, score_threshold)
    elif strategy == "parallel":
        yield {"event": "strategy", "data": {"strategy": "parallel"}}
        yield {"event": "retrieve_start", "data": {"message": "正在并行查询数据..."}}
        method, graph_data, cypher = await parallel_trial(question, top_k, score_threshold)
    else:  # sequential
        yield {"event": "strategy", "data": {"strategy": "sequential"}}
        yield {"event": "retrieve_start", "data": {"message": "正在顺序查询数据..."}}
        method, graph_data, cypher = await sequential_trial(question, top_k, score_threshold)

    yield {
        "event": "retrieve",
        "data": {
            "method": method,
            "nodes": len(graph_data.nodes),
            "relationships": len(graph_data.relationships),
        },
    }

    # ─── Phase 2: Tree-structured text ──────────────────────────────────
    yield {"event": "text_start", "data": {"message": "正在生成结果..."}}
    ignored_lbl = s.get("ignored_label", "_Embeddable")
    from backend.tree_builder import build_tree_text
    full_text = build_tree_text(graph_data, ignored_lbl)
    yield {"event": "text", "data": full_text}

    yield {
        "event": "done",
        "data": {
            "strategy_used": method,
            "total_nodes": len(graph_data.nodes),
            "total_relationships": len(graph_data.relationships),
        },
    }


async def _single_retrieve(
    question: str, method: str, top_k: int, score_threshold: float
) -> tuple[GraphResponse, str | None]:
    """Execute single retrieval by method name."""
    if method == "nl":
        from backend.nl2cypher import nl2cypher as _nl2cypher
        from backend.strategy_selector import _records_to_graph

        result = await _nl2cypher(question)
        return _records_to_graph(result.get("records", [])), result.get("generated_cypher", "")
    elif method == "semantic_nl":
        from backend.semantic_search import semantic_nl_search as _semantic_nl_search

        graph, cypher = await _semantic_nl_search(question, top_k)
        return graph, cypher
    else:  # "semantic"
        from backend.semantic_search import semantic_search as _semantic_search

        graph = await _semantic_search(question, top_k)
        return graph, None
