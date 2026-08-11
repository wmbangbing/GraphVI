# 语义检索优化设计：共享检索组件（问题分解 + rerank）

## Context

语义NL接口存在入口质量不稳定问题：直接用完整问题向量化做向量检索，再用 top_k/阈值过滤，经常"不多不少不准"——完整问题含干扰词（如"物资/装备/车辆"）会匹配到非目标实体；top_k 固定值无法适配不同查询的数据量。

**已验证的方案**（测试脚本确认）：
1. **问题分解**：LLM 从问题提取 `retrieval_query`（干净检索 query），消除干扰词，向量检索聚焦目标实体（`scripts/test_question_analysis.py`）
2. **rerank 精排**：Qwen3-Reranker-4B 对候选精排 + 阈值过滤，分数分离清晰（相关 0.9+ vs 不相关 <0.1），耗时 ~1s（`scripts/test_rerank_api.py`）

目标：把这两个组件集成到**语义、语义NL、query/auto** 三个接口，共享高质量入口选择，各接口保留各自的扩展方式。

## 方案：共享检索组件

### 后端新增函数

| 函数 | 职责 |
|---|---|
| `analyze_question(question)` | LLM 问题分解 → `retrieval_query`（干净向量检索 query），失败返回原始问题 |
| `rerank_filter(candidates, question)` | Qwen3-Reranker 精排 + 阈值过滤，失败/未配置返回原候选 |
| `_retrieve_entries(question)` | **共享入口**：问题分解 → 向量检索(retrieval_query) → rerank 精排 → 阈值过滤 → entry 列表 |

**`_retrieve_entries` 流程**：
```
analyze_question → retrieval_query
      ↓
向量检索（VectorRetriever, top_k 候选）
      ↓
rerank_filter（Qwen3-Reranker 精排 + threshold 过滤）
      ↓
entry 列表（供扩展查询）
```

### 三接口集成

| 接口 | 入口 | 扩展 |
|---|---|---|
| `semantic_search`（语义）| `_retrieve_entries`（替代原向量检索+过滤）| 保留固定模板遍历 |
| `semantic_nl_search`（语义NL）| `_retrieve_entries` | 保留 LLM 生成 Cypher |
| `auto_analyze`（query/auto）| 零改动（复用 semantic/semantic_nl）| — |

### 新增配置项（settings_db.py + AiConfigPanel.vue）

| 配置 | 默认 | 说明 |
|---|---|---|
| `enable_semantic_rerank` | `true` | 总开关（关闭则退回现状：完整问题 + 向量分数）|
| `rerank_endpoint` | `https://api.siliconflow.cn/v1` | rerank API 地址 |
| `rerank_api_key` | 空 | rerank API key |
| `rerank_model` | `Qwen/Qwen3-Reranker-4B` | 重排模型 |
| `rerank_threshold` | `0.8` | 过滤阈值 |

设置页（AiConfigPanel.vue）新增「重排序」配置区，参照 embedding 对接方案：endpoint/api_key/model 输入 + 测试按钮 + 阈值。

### 后端测试接口

```
POST /api/test-rerank
```
参照 `/api/query/semantic/test` 的 embedding 测试方式：httpx POST `{endpoint}/rerank` 简单调用验证连接和模型可用。

### 错误兜底

| 场景 | 处理 |
|---|---|
| 问题分解失败/超时 | 用原始问题向量化（退回现状）|
| rerank 失败/未配置/开关关闭 | 用向量分数排序（退回现状）|
| rerank 后无 entry | 取向量前 N 候选（保留基础）|

## 关键文件

| 文件 | 修改 |
|---|---|
| `backend/semantic_search.py` | 新增 `analyze_question`/`rerank_filter`/`_retrieve_entries`；`semantic_search`/`semantic_nl_search` 改用共享入口 |
| `backend/settings_db.py` | 新增 5 个配置项默认值 |
| `backend/main.py` | 新增 `/api/test-rerank` 测试接口 |
| `frontend/src/components/AiConfigPanel.vue` | 新增「重排序」配置区（含测试按钮）|
| `deploy/backend/*` | 同步对应后端改动 |

## 验证

1. `scripts/test_rerank_api.py` 验证 rerank 效果（分数分离、耗时 ~1s）
2. 设置页配置 rerank 后，三接口发起查询：
   - 语义：entry 全为目标类型（无装备混入）
   - 语义NL：entry 干净，扩展查询完整
   - auto：自动受益
3. 关闭 `enable_semantic_rerank` 后退回现状（回归验证）
4. 问题分解/rerank 异常时正常兜底（日志可见）
