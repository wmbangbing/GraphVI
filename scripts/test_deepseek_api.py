import httpx, json, sys

api_key = "sk-24d40c2b16ca49528a1e2f65c4f65de7"
model = "deepseek-v4-flash"
endpoint = "https://api.deepseek.com"

tests = [
    ("极简", "Write Python: result = {'sum': 2+2}"),
    ("函数", "Write Python function add(a,b), store add(2,3) in result"),
    ("列表", "Write Python to sum [1,2,3,4,5], store in result"),
    ("数据分析", """Write Python script analyzing nodes/relationships data.

Variables nodes and relationships are lists.
Each node: {id, labels, properties} where properties is a dict
Each rel: {id, type, source, target, properties}

Compute: result["count"] = len(nodes)
Store in result dict.
Only built-in Python."""),
]

for label, prompt in tests:
    print("\n--- " + label + " ---")
    try:
        resp = httpx.post(endpoint + "/chat/completions",
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.1, "max_tokens": 2048},
            timeout=60)
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        print("len:", len(content))
        print("preview:", repr(content[:150]))
        # Check if it looks like code
        has_fence = "```" in content
        has_def = "def " in content[:200]
        has_assign = "=" in content[:200]
        print("  fence:", has_fence, "def:", has_def, "assign:", has_assign)
    except Exception as e:
        print("ERROR:", e)
