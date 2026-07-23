"""测试 LLM 生成 Python 代码并执行的可行性"""
import json, httpx, sys, os

# ─── 配置 ───────────────────────────────────────────
LLM_ENDPOINT = "https://api.deepseek.com"
LLM_API_KEY = "sk-24d40c2b16ca49528a1e2f65c4f65de7"
LLM_MODEL = "deepseek-v4-flash"

# ─── 模拟数据 ───────────────────────────────────────
MOCK_NODES = [
    {"id": "1", "labels": ["Movie"], "properties": {"title": "钢铁侠", "year": 2008, "rating": 7.9, "length": 126}},
    {"id": "2", "labels": ["Movie"], "properties": {"title": "复仇者联盟4", "year": 2019, "rating": 8.5, "length": 181}},
    {"id": "3", "labels": ["Movie"], "properties": {"title": "流浪地球", "year": 2019, "rating": 7.9, "length": 125}},
    {"id": "4", "labels": ["Person"], "properties": {"name": "刘慈欣", "age": 60}},
    {"id": "5", "labels": ["Person"], "properties": {"name": "吴京", "age": 50}},
]
MOCK_RELS = [
    {"id": "r1", "type": "ACTED_IN", "source": "5", "target": "3", "properties": {}},
]

# ─── LLM 调用 ───────────────────────────────────────
def call_llm(prompt: str, max_tokens: int = 2048) -> str:
    resp = httpx.post(
        f"{LLM_ENDPOINT}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.1, "max_tokens": max_tokens},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

# ─── 安全执行 ───────────────────────────────────────
def safe_exec(script: str, nodes: list, relationships: list) -> dict:
    namespace = {"nodes": nodes, "relationships": relationships, "result": {}}
    allowed = {"len": len, "sum": sum, "min": min, "max": max, "abs": abs,
               "round": round, "sorted": sorted, "list": list, "dict": dict,
               "str": str, "int": int, "float": float, "bool": bool,
               "isinstance": isinstance, "type": type, "range": range,
               "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
               "any": any, "all": all, "True": True, "False": False, "None": None}
    exec_globals = {"__builtins__": allowed}
    exec(script, exec_globals, namespace)
    return namespace.get("result", {})

# ─── 提示词方案 A：简短版 ─────────────────────────────
PROMPT_A = """Given data: Movie {title,year,rating,length} Person {name,age}
Relationships: ACTED_IN

Write Python that processes `nodes` and `relationships` (lists of dicts).
Nodes have: id, labels, properties. Rels have: id, type, source, target, properties.
Store ALL results in dict `result`. Include counts by label, and numeric aggregations.
Only built-in Python."""

# ─── 提示词方案 B：详细版 ─────────────────────────────
PROMPT_B = """Write a Python script that analyzes graph data.

Available data:
- nodes: list of dicts, each with keys: id(str), labels(list[str]), properties(dict), caption(str)
- relationships: list of dicts, each with keys: id(str), type(str), source(str), target(str), properties(dict)

The data contains:
- Movie nodes with properties: title, year (int), rating (float), length (int)
- Person nodes with properties: name, age (int)
- ACTED_IN relationships between Person and Movie

Requirements:
1. Count nodes by label -> store in result["count_by_label"]
2. Count relationships by type -> result["count_by_rel_type"]
3. For EACH numeric property, compute sum/avg/min/max -> result["numeric_aggregations"]
   Format: {"Movie.rating": {"sum": 0, "avg": 0, "min": 0, "max": 0, "count": 0}}
4. Any other insights you find useful

Your response must contain ONLY valid Python code in a ```python block.
Do NOT include any explanations outside the code block."""

# ─── 测试 ───────────────────────────────────────────
for name, prompt in [("A:简短版", PROMPT_A), ("B:详细版", PROMPT_B)]:
    print(f"\n{'='*60}")
    print(f"测试 {name}")
    print(f"{'='*60}")
    try:
        raw = call_llm(prompt)
        print(f"LLM 返回长度: {len(raw)}")
        if len(raw) < 10:
            print("  ❌ LLM 返回为空或太短")
            continue

        # 清理代码块
        script = raw
        for fence in ("```python", "```"):
            if fence in script:
                script = script.split(fence, 1)[1]
        if "```" in script:
            script = script.rsplit("```", 1)[0]
        script = script.strip()

        if not script or not script.startswith(("#", "def ", "import ", "result", "for ", "count")):
            print(f"  ⚠️ 可能不是代码，前50字符: {repr(script[:50])}")
            # 保存看看
            with open(f"_test_output_{name[0]}.py", "w") as f:
                f.write(raw)
            continue

        # 保存
        fname = f"_test_script_{name[0]}.py"
        with open(fname, "w") as f:
            f.write(script)
        print(f"  ✅ 脚本已保存: {fname}")

        # 执行
        result = safe_exec(script, MOCK_NODES, MOCK_RELS)
        print(f"  执行结果: {json.dumps(result, ensure_ascii=False, indent=2)[:300]}")

    except Exception as e:
        print(f"  ❌ 错误: {e}")
