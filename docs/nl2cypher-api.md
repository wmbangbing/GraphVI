# NL → Cypher 接口文档

将自然语言转换为 Neo4j Cypher 查询语句，**不执行查询**。适用于第三方系统或工具集成。

## 请求

```
POST /api/nl2cypher
Content-Type: application/json
```

### 请求体

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `question` | string | 是 | 自然语言查询问题 |

### 示例

```json
{
  "question": "查询所有演员及其参演的电影"
}
```

## 响应

### 成功

```json
{
  "cypher": "MATCH (a:Actor)-[:ACTED_IN]->(m:Movie) RETURN a, m LIMIT 100"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `cypher` | string | 生成的 Cypher 查询语句 |

### 错误

```json
{
  "detail": "NL2Cypher error: ..."
}
```

HTTP 状态码：`500`

## 调用示例

### curl

```bash
curl -s -X POST http://localhost:8000/api/nl2cypher \
  -H "Content-Type: application/json" \
  -d '{"question":"查询所有节点"}' | jq .
```

### Python

```python
import httpx

resp = httpx.post(
    "http://localhost:8000/api/nl2cypher",
    json={"question": "查询所有演员及其参演的电影"},
)
result = resp.json()
print(result["cypher"])
# MATCH (a:Actor)-[:ACTED_IN]->(m:Movie) RETURN a, m LIMIT 100
```

### JavaScript

```javascript
const resp = await fetch("http://localhost:8000/api/nl2cypher", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: "查询所有演员" }),
});
const data = await resp.json();
console.log(data.cypher);
```

## 与 `/api/query/nl` 的区别

| | `/api/query/nl` | `/api/nl2cypher` |
|---|---|---|
| 生成 Cypher | 是 | 是 |
| 执行查询 | 是 | **否** |
| 返回图谱数据 | 是 | **否** |
| 返回 Cypher 语句 | `generated_cypher` 字段 | `cypher` 字段 |
| 适用场景 | 系统自身的前端查询 | 第三方系统集成 |

## 配置

接口行为受以下后台配置影响：

| 配置项 | 作用 |
|---|---|
| `llm_endpoint` | LLM API 地址 |
| `llm_api_key` | API Key |
| `llm_model` | 模型名称 |
| `nl_query_prompt` | 生成 Cypher 的提示词模板 |
| `nl_schema_examples` | 是否在 schema 中包含采样值 |
