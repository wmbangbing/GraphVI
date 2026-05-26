# 自然语言查询优化方案

## 自定义 NL 查询提示词

在设置页 → AI 配置 → NL 查询提示词 中可自定义 Prompt 模板。默认提示词包含多跳匹配、只读安全、LIMIT 限制等规则。支持 `{schema}`、`{examples}`、`{query_text}` 三个占位变量。

## Few-shot 示例

自动从预设问题中提取有 Cypher 语句的条目，作为示例注入 Prompt。LLM 会模仿这些示例的查询风格和复杂度，默认取最近 10 条。

## Schema 构建

使用 Neo4j 标准过程（无需 APOC）自动获取 Schema：

- `CALL db.schema.nodeTypeProperties()` — 节点属性名和类型
- `CALL db.schema.relTypeProperties()` — 关系属性名和类型
- `CALL db.schema.visualization()` — 节点间连接模式

在设置页可开启 Schema 示例值功能。开启后对每个标签采样 2 条属性值附加到 Schema 中，帮助 LLM 生成更精确的 WHERE 条件。

## 缓存机制

- Schema 按数据库名缓存，切换数据库或重连时自动失效重建
- 首次构建约 1-2 秒，后续请求零额外开销
- 错误自愈接口已预留，可捕获 LLM 生成错误并自动重试

## 技术实现

基于 `neo4j-graphrag` 库的 `Text2CypherRetriever`，复用已配置的 LLM（OpenAI 兼容接口），无需额外部署。
