# 2026-07-23 变更记录

## 新增功能

### 语义检索（语义 tab）
- **接口**: `POST /api/query/semantic`
- **流程**: 向量搜索 → 固定模板 n 跳遍历
- **配置**: `embedding_endpoint`, `embedding_api_key`, `embedding_model`, `vector_index_name`, `semantic_query_hops`
- **文件**: `backend/semantic_search.py` `semantic_search()`
- **前端**: QueryEditor 新增「语义」tab

### 语义NL检索（语义NL tab）
- **接口**: `POST /api/query/semantic-nl`
- **流程**: 向量搜索 → LLM 生成遍历 Cypher → 执行
- **文件**: `backend/semantic_search.py` `semantic_nl_search()`
- **前端**: QueryEditor 新增「语义NL」tab

## Bug 修复

### 语义搜索返回数据不完整
- **问题**: VectorRetriever 的 `default_record_formatter` 把 Node 转为 String，`hasattr(node, "element_id")` 永远为 False
- **修复**: 改用 `get_search_results()` 获取原始 records，直接读 `record.get("elementId")`

### 遍历查询不返回关系
- **问题 1**: `hops=1` 时 `OPTIONAL MATCH (node)-[*1..1]-(related)` 没有命名关系变量，无法 RETURN
- **问题 2**: `hops>1` 时变长路径 `[*1..N]` 没展开关系列表
- **修复**: 
  - `hops=1`: 单独用 `(node)-[r]-(related)` 命名 + `collect(DISTINCT r)`
  - `hops>1`: 用 `(node)-[r*1..{hops}]-(related)` + `UNWIND r AS single_rel` 展开收集

### 语义NL入口节点提取失败
- **问题**: `semantic_nl_search` 用 `retriever.search()` 返回的 `.content` 是 String，无法提取入口节点
- **修复**: 改用 `get_search_results()` + 从 dict 和 record 字段直接读 `elementId`/`nodeLabels`/属性

### 语义NL生成的 Cypher 不使用入口节点
- **问题**: LLM 忽略入口节点，自己用属性 `CONTAINS` 导致查不到
- **修复**: prompt 中内联实际 node_id_list，强制 `WHERE elementId(entry) IN [...]` + 不准额外过滤

### 设置保存 422 Unprocessable Content
- **问题**: `SettingsUpdate` 模型 `dict[str, str]` 不接受 `el-input-number` 传的数字类型
- **修复**: 改为 `dict[str, Any]`

### 关联跳数显示问题
- **问题**: `el-input-number` 接受数字，但默认值和加载值都是字符串
- **修复**: 默认值改为 `1`（number），fetch 时用 `Number(data.semantic_query_hops) || 1`

## 配置项

新增 settings 表配置项：

| 键 | 默认值 | 说明 |
|-----|--------|------|
| `embedding_endpoint` | `https://api.openai.com/v1` | Embedding API 地址 |
| `embedding_api_key` | `""` | Embedding API Key |
| `embedding_model` | `text-embedding-3-small` | Embedding 模型名 |
| `vector_index_name` | `entity_vector` | Neo4j 向量索引名 |
| `semantic_query_hops` | `1` | 语义检索关联跳数 |

## 文档

- `docs/vector-index-verification.md` — Neo4j 向量索引验证记录
- `docs/semantic-search-optimization.md` — 语义检索优化方向（分词 vs 整句分析）
