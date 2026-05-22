import json
import httpx

from backend.settings_db import get_all_settings


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


async def test_llm_connection() -> str:
    settings = get_all_settings()
    endpoint = settings.get("llm_endpoint", "https://api.openai.com/v1").rstrip("/")
    api_key = settings.get("llm_api_key", "")
    model = settings.get("llm_model", "gpt-4o")

    messages = [{"role": "user", "content": "回复 OK 即可"}]
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{endpoint}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 10},
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]


async def call_llm_stream(nodes: list, relationships: list, custom_prompt: str | None = None):
    settings = get_all_settings()
    endpoint = settings.get("llm_endpoint", "https://api.openai.com/v1").rstrip("/")
    api_key = settings.get("llm_api_key", "")
    model = settings.get("llm_model", "gpt-4o")
    prompt_template = custom_prompt or settings.get("summary_prompt", "")

    graph_data = _format_graph_data(nodes, relationships)
    prompt = _build_prompt(prompt_template, graph_data)

    messages = [
        {"role": "system", "content": "你是一个知识图谱分析专家，擅长从实体关系数据中发现模式和洞察。"},
        {"role": "user", "content": prompt},
    ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{endpoint}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2048,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
