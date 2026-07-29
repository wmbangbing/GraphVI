"""LLM service: AI summary generation + script-based statistics"""

import json
import httpx

from settings_db import get_all_settings


def _aggregate_stats(nodes: list, relationships: list, ignored_label: str = "") -> dict:
    """Auto-aggregate all numeric fields - works with any graph schema."""
    from utils import primary_label as _pl

    stats = {
        "total_nodes": len(nodes),
        "total_relationships": len(relationships),
        "nodes_by_label": {},
        "rels_by_type": {},
        "numeric_sums": {},
        "numeric_avgs": {},
        "numeric_mins": {},
        "numeric_maxs": {},
    }
    for n in nodes:
        lbl = _pl(n.get("labels") or ["?"], ignored_label)
        stats["nodes_by_label"][lbl] = stats["nodes_by_label"].get(lbl, 0) + 1
    for r in relationships:
        rt = r.get("type", "?")
        stats["rels_by_type"][rt] = stats["rels_by_type"].get(rt, 0) + 1

    groups = {}
    for n in nodes:
        lbl = _pl(n.get("labels") or ["?"], ignored_label)
        groups.setdefault(lbl, []).append(n)

    for lbl, items in groups.items():
        numeric_keys = set()
        for item in items:
            for k, v in item.get("properties", {}).items():
                if isinstance(v, (int, float)):
                    numeric_keys.add(k)
        for key in sorted(numeric_keys):
            vals = [item["properties"][key] for item in items
                    if isinstance(item.get("properties", {}).get(key), (int, float))]
            if not vals:
                continue
            ak = f"{lbl}.{key}"
            stats["numeric_sums"][ak] = sum(vals)
            stats["numeric_avgs"][ak] = round(sum(vals) / len(vals), 2)
            stats["numeric_mins"][ak] = min(vals)
            stats["numeric_maxs"][ak] = max(vals)
    return stats


def _format_stats(stats: dict) -> str:
    parts = [f"Total: {stats['total_nodes']} nodes, {stats['total_relationships']} relationships"]
    if stats["nodes_by_label"]:
        parts.append("\nNodes by label:")
        for lbl, cnt in sorted(stats["nodes_by_label"].items()):
            parts.append(f"  {lbl}: {cnt}")
    if stats["rels_by_type"]:
        parts.append("Relationships by type:")
        for rt, cnt in sorted(stats["rels_by_type"].items()):
            parts.append(f"  {rt}: {cnt}")
    if stats["numeric_sums"]:
        parts.append("Numeric aggregations (accurate):")
        for k in sorted(stats["numeric_sums"].keys()):
            parts.append(f"  {k}: sum={stats['numeric_sums'][k]}, avg={stats['numeric_avgs'][k]}, "
                        f"min={stats['numeric_mins'][k]}, max={stats['numeric_maxs'][k]}")
    return "\n".join(parts)


def _format_graph_data(nodes: list, relationships: list) -> dict:
    node_lines = []
    for n in nodes:
        labels = ", ".join(n.get("labels", []))
        props = ", ".join(
            f"{k}={v}" for k, v in n.get("properties", {}).items()
            if not str(v).startswith("http")
        )
        caption = n.get("caption") or n.get("properties", {}).get("name", "")
        line = f"  [{labels}] {caption}" + (f" ({props})" if props else "")
        node_lines.append(line)
    rel_lines = []
    for r in relationships:
        rel_lines.append(f"  {r.get('source')} --[{r.get('type')}]--> {r.get('target')}")
    return {
        "node_count": len(nodes),
        "rel_count": len(relationships),
        "nodes": "\n".join(node_lines) if node_lines else "（无节点数据）",
        "rels": "\n".join(rel_lines) if rel_lines else "（无关系数据）",
    }


def _build_prompt(template: str, data: dict) -> str:
    return template.format(**data)


def _call_llm_sync(prompt: str, temperature: float = 0.1, max_tokens: int = 8192) -> str:
    s = get_all_settings()
    endpoint = s.get("llm_endpoint", "https://api.openai.com/v1").rstrip("/")
    api_key = s.get("llm_api_key", "")
    model = s.get("llm_model", "gpt-4o")
    resp = httpx.post(
        f"{endpoint}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": max_tokens},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _call_llm_async(prompt: str, temperature: float = 0.1, max_tokens: int = 8192) -> str:
    """Async version of _call_llm_sync — non-blocking."""
    s = get_all_settings()
    endpoint = s.get("llm_endpoint", "https://api.openai.com/v1").rstrip("/")
    api_key = s.get("llm_api_key", "")
    model = s.get("llm_model", "gpt-4o")
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{endpoint}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": max_tokens},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _safe_exec(script: str, nodes: list, relationships: list) -> dict:
    """Execute LLM-generated Python via LangChain PythonREPL (subprocess)."""
    import json as _json
    wrapper = f"""import json, collections, math, statistics, itertools, re
nodes = {_json.dumps(nodes, ensure_ascii=False)}
relationships = {_json.dumps(relationships, ensure_ascii=False)}
result = {{}}
{script}
print("__RESULT__:" + json.dumps(result, ensure_ascii=False))
"""
    from langchain_experimental.tools import PythonREPLTool
    repl = PythonREPLTool()
    try:
        output = repl.run(wrapper)
    except Exception as e:
        raise RuntimeError(str(e)[:300])

    if "__RESULT__:" in output:
        result_str = output.split("__RESULT__:")[1].strip()
        try:
            return _json.loads(result_str)
        except _json.JSONDecodeError:
            raise RuntimeError("Parse error: " + result_str[:200])
    raise RuntimeError("No result: " + output[:200])


async def test_llm_connection(config_override: dict | None = None) -> str:
    if config_override:
        endpoint = config_override.get("llm_endpoint", "").rstrip("/")
        api_key = config_override.get("llm_api_key", "")
        model = config_override.get("llm_model", "gpt-4o")
    else:
        s = get_all_settings()
        endpoint = s.get("llm_endpoint", "https://api.openai.com/v1").rstrip("/")
        api_key = s.get("llm_api_key", "")
        model = s.get("llm_model", "gpt-4o")
    messages = [{"role": "user", "content": "回复 OK 即可"}]
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{endpoint}/chat/completions", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                              json={"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 10})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def call_llm_stream(nodes: list, relationships: list, custom_prompt: str | None = None):
    """SSE stream LLM summary with optional script-based statistics."""
    s = get_all_settings()
    endpoint = s.get("llm_endpoint", "https://api.openai.com/v1").rstrip("/")
    api_key = s.get("llm_api_key", "")
    model = s.get("llm_model", "gpt-4o")
    prompt_template = custom_prompt or s.get("summary_prompt", "")
    enable_script = s.get("enable_script_stats", "false") == "true"

    stats_context = ""

    if enable_script and nodes:
        # Step 1: LLM writes Python script
        schema_info = ""
        labels = {}
        for n in nodes:
            for lbl in n.get("labels", []):
                labels.setdefault(lbl, {})
                for k, v in n.get("properties", {}).items():
                    labels[lbl].setdefault(k, type(v).__name__)
        schema_lines = ["Data structure:"]
        for lbl, props in sorted(labels.items()):
            schema_lines.append(f"  {lbl}: {{{', '.join(f'{k}: {t}' for k, t in sorted(props.items()))}}}")
        schema_lines.append(f"\nTotal: {len(nodes)} nodes, {len(relationships)} relationships")
        schema_info = "\n".join(schema_lines)

        schema_preview = "\n".join(schema_info.split("\n")[:15])
        script_prompt = f"""Data schema:
{schema_preview}

Write a flat Python script (no functions) that processes `nodes` and `relationships` lists.

NODE FORMAT: {{"id":str, "labels":[str], "properties":{{key:value}}, "caption":str}}
  - Use node["labels"][0] for primary label (it's a list!)
  - Use node["properties"] for attribute values
REL FORMAT: {{"id":str, "type":str, "source":str, "target":str, "properties":{{}}}}

Store results in `result` dict (already defined).
Include: counts_by_label, counts_by_rel_type, numeric_aggregations per label.property.
Use defaultdict if needed. Standard library only."""

        precomputed = _aggregate_stats(nodes, relationships)
        print("=== [Pre-computed stats] ===", flush=True)
        print(_format_stats(precomputed), flush=True)

        try:
            script = _call_llm_sync(script_prompt, max_tokens=8192)
            print("=== [LLM RAW len=" + str(len(script)) + "] ===", flush=True)
            print(repr(script[:400]), flush=True)
            # Strip markdown fences - find opening and closing fences
            start = script.find("```python")
            if start < 0:
                start = script.find("```")
            if start >= 0:
                script = script[start + 3:]  # past the ```
                # find matching opening fence type
                is_python = script[:6] == "python"
                if is_python:
                    script = script[6:]     # past "python"
                end = script.rfind("```")
                if end >= 0:
                    script = script[:end]
            script = script.strip()
            if not script:
                raise RuntimeError("empty script after stripping")

            # Write script to file for debugging, then execute
            import os as _os
            script_path = _os.path.join(_os.path.dirname(__file__), "_generated_stats.py")
            with open(script_path, "w", encoding="utf-8") as _f:
                _f.write(script)
            print("=== [Script saved to " + script_path + "] ===", flush=True)

            computed = _safe_exec(script, nodes, relationships)
            print("=== [LLM script result] ===", flush=True)
            print(json.dumps(computed, ensure_ascii=False, indent=2)[:500], flush=True)
            if computed:
                stats_context = "\n\n[Accurate Computed Statistics]\n" + json.dumps(computed, ensure_ascii=False, indent=2)
            else:
                raise RuntimeError("script returned empty result")
        except Exception as e:
            print("=== [Fallback to pre-computed] ===", flush=True)
            print("Error: " + str(e)[:300], flush=True)
            stats_context = "\n\n[Computed Statistics]\n" + _format_stats(precomputed)
    else:
        stats_context = "\n\n[Computed Statistics]\n" + _format_stats(_aggregate_stats(nodes, relationships))

    graph_data = _format_graph_data(nodes, relationships)
    prompt = (
        stats_context
        + "\n\nRaw data:\n"
        + _build_prompt(prompt_template, graph_data)
        + "\n\nIMPORTANT: All numbers must come from [Computed Statistics] above. Do NOT recalculate."
    )

    messages = [
        {"role": "system", "content": "你是一个知识图谱分析专家。"},
        {"role": "user", "content": prompt},
    ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", f"{endpoint}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 4096, "stream": True}) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                d = line[6:]
                if d == "[DONE]":
                    break
                try:
                    chunk = json.loads(d)
                    content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
