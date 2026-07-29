# 智能查询分析接口设计

> 版本: v1.0
> 日期: 2026-07-27

## 1. 概述

对外提供一个 RESTful API 端点，用户输入问题后，后端自动完成：策略选择 → 知识图谱检索 → 专题统计脚本生成执行 → 文本说明输出。

## 2. API 定义

### 2.1 请求

```
POST /api/query/auto
Content-Type: application/json
```

**请求体：**

```json
{
  "question": "某事件调用了哪些便携站？资源分布情况如何？",
  "strategy": "auto",
  "top_k": 10,
  "score_threshold": 0.6,
  "analyze_prompt": null,
  "stream": false
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `question` | string | 是 | - | 用户问题 |
| `strategy` | string | 否 | `"auto"` | `"auto"`(LLM分类) / `"parallel"`(并行择优) / `"sequential"`(顺序尝试) |
| `top_k` | int | 否 | settings.semantic_top_k | 语义检索 top_k |
| `score_threshold` | float | 否 | settings.semantic_score_threshold | 语义检索分数阈值 |
| `analyze_prompt` | string\|null | 否 | null（使用系统默认） | 覆盖专题分析提示词 |
| `stream` | bool | 否 | false | 是否 SSE 流式输出 |

### 2.2 响应

#### 非流式模式 (`stream: false`)

```json
{
  "result": "根据查询结果...（文本说明，引用统计数值）",
  "strategy_used": "nl2cypher",
  "stats_summary": {
    "total_nodes": 15,
    "total_relationships": 23,
    "nodes_by_label": {"dm_event_info": 3, "dm_equipment_info": 12},
    "rels_by_type": {"EVENT_TRIGGER_DISPATCH_APPLY": 3, ...}
  },
  "generated_cypher": "..."
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `result` | string | 最终文本说明 |
| `strategy_used` | string | 实际使用的检索策略 |
| `stats_summary` | dict | 统计数据（可选，供调用方参考） |
| `generated_cypher` | string\|null | 若走 NL 路径，返回生成的 Cypher |

#### SSE 流式模式 (`stream: true`)

```
event: strategy
data: {"strategy": "parallel", "reason": "问题涉及多种资源关联，选择并行检索"}

event: retrieve
data: {"method": "nl2cypher", "nodes": 15, "rels": 23, "status": "ok"}

event: retrieve
data: {"method": "semantic_nl", "nodes": 8, "rels": 12, "status": "ok"}

event: script
data: {"status": "running", "detail": "正在执行统计分析..."}

event: text
data: "根据查询结果，该事件共调用..."

event: text
data: "其中便携站设备..."

event: done
data: {"strategy_used": "nl2cypher", "total_nodes": 15, "total_rels": 23}
```

| 事件类型 | 推送时机 | 说明 |
|----------|----------|------|
| `strategy` | 策略选择完成 | 告知调用方选择了哪种策略 |
| `retrieve` | 某一路检索完成 | 可能多次推送（并行模式） |
| `script` | 统计脚本执行 | 状态更新 |
| `text` | 文本生成中 | 最终文本的分块推送 |
| `done` | 全部完成 | 汇总信息 |

## 3. 三种 strategy 模式

### 3.1 `"auto"` — LLM 分类模式

**流程：**

```
用户问题 → LLM分类(极简) → 单一检索 → 统计脚本+文本 → 返回
                           ├─ nl2cypher
                           ├─ semantic
                           └─ semantic_nl
```

**LLM 分类调用：** `temperature=0, max_tokens=50`

```
Classify the question into one of: nl, semantic, semantic_nl.

Rules:
- nl: asks about specific entities, relationships, attributes (e.g. "find all events", "list equipment used by event X")
- semantic: vague, fuzzy, or conceptual search (e.g. "emergency response resources", "communication equipment")
- semantic_nl: needs both semantic matching and specific traversal (e.g. "equipment distribution in typhoon events")

Return only one word.
```

**延迟预计：** 1s(分类) + 3-6s(检索) + 3-5s(脚本+文本) = **7-12s**

### 3.2 `"parallel"` — 并行择优模式

**流程：**

```
用户问题 → 三种检索并行 → LLM 评判择优 → 统计脚本+文本 → 返回
           ├─ nl2cypher   ─┐
           ├─ semantic     ─┼─ asyncio.gather(timeout=8s)
           └─ semantic_nl  ─┘
```

**数据融合规则（轻量 LLM 评判）：**
1. 等待所有检索完成（或超时 8s）
2. 已经完成的路中，将各路的**概要信息**（仅节点标签分布 + 关系类型分布 + 节点数）简化为 2-3 行
3. 一次极轻 LLM 调用（约 200 token，温度 0）评判哪个结果最能回答用户问题

   ```
   Question: 某事件调用了哪些便携站？

   Result A (nl2cypher): 3 nodes (1 dm_event_info, 2 dm_equipment_info), 2 rels (EVENT_TRIGGER_DISPATCH_APPLY)
   Result B (semantic): 15 nodes (5 dm_equipment_info, 3 dm_event_info, 7 other), 12 rels (3 types)
   Result C (semantic_nl): 8 nodes (2 dm_event_info, 6 dm_equipment_info), 6 rels (2 types)

   Which result best answers the question? Return only the letter.
   ```

4. 取 LLM 选中的路为主数据
5. 若某路无数据则从候选移除，不参与评选

**超时处理：** 某一路超时后直接丢弃，不影响其他路。所有路都超时或为空则返回错误。

**延迟预计：** 6-9s（取决于最慢检索路径 + LLM 评判 1-2s）

### 3.3 `"sequential"` — 顺序尝试模式

**流程：**

```
用户问题 → 先试NL2Cypher → 有数据? → 统计脚本+文本 → 返回
                    ↓ 无数据
              试语义NL → 有数据? → 统计脚本+文本 → 返回
                    ↓ 无数据
              试语义检索 → 统计脚本+文本 → 返回
                    ↓ 无数据
              返回空结果
```

**命中条件：** `nodes > 0` 即为命中，停止后续尝试。

**延迟预计：** 最坏情况 ≈ 三种检索串行 = 9-18s，最好情况 = 3-6s

## 4. 模块设计

### 4.1 `auto_analyzer.py` — 编排入口

```python
async def auto_analyze(
    question: str,
    strategy: str = "auto",
    top_k: int | None = None,
    score_threshold: float | None = None,
    analyze_prompt: str | None = None,
    stream: bool = False,
) -> AsyncGenerator[dict, None] | dict:
    """智能查询分析入口。

    - stream=False: 返回完整结果 dict
    - stream=True: yield 事件 dict（SSE 分块）
    """
```

**内部流程：**

```python
async def auto_analyze(...):
    # 1. 策略选择
    strategy_used = await _select_strategy(question, strategy)
    yield {"event": "strategy", "data": {"strategy": strategy_used}}

    # 2. 数据检索
    graph_data, cypher = await _retrieve(question, strategy_used, top_k, score_threshold)
    yield {"event": "retrieve", "data": {"nodes": len(graph_data.nodes), "rels": len(graph_data.relationships)}}

    # 3. 统计脚本执行
    stats = await _run_stats(graph_data, analyze_prompt)
    yield {"event": "script", "data": {"status": "done", "stats": stats}}

    # 4. 最终文本生成
    async for text_chunk in _generate_text(question, graph_data, stats, analyze_prompt):
        yield {"event": "text", "data": text_chunk}

    yield {"event": "done", "data": {"strategy_used": strategy_used, ...}}
```

### 4.2 `strategy_selector.py` — 策略判定

```python
async def llm_classify(question: str) -> str:
    """LLM 分类：返回 nl / semantic / semantic_nl"""

async def parallel_trial(question: str, top_k: int, score_threshold: float) -> tuple[str, GraphResponse, str | None]:
    """并行执行三种检索，返回 (best_method, graph_data, generated_cypher)"""

async def sequential_trial(question: str, top_k: int, score_threshold: float) -> tuple[str, GraphResponse, str | None]:
    """顺序尝试三种检索，命中即止"""
```

### 4.3 `stats_engine.py` — 专题统计引擎

```python
async def generate_and_execute(
    graph_data: GraphResponse,
    schema: str,
    user_prompt: str | None = None,
) -> dict:
    """LLM 生成 Python 统计脚本 → 执行 → 返回统计结果"""

    # 1. 预计算基础统计（_aggregate_stats）
    # 2. 构建脚本提示词（schema + 业务场景 + 用户自定义 prompt）
    # 3. LLM 生成脚本
    # 4. PythonREPLTool 执行
    # 5. 返回统计 dict
```

### 4.4 与现有模块的关系

```
auto_analyzer
  ├── strategy_selector (新增)
  │     ├── llm_classify()
  │     └── parallel_trial()
  ├── nl2cypher.nl2cypher()       (已有)
  ├── semantic_search.semantic_search()  (已有)
  ├── semantic_search.semantic_nl_search() (已有)
  ├── stats_engine (新增)
  │     ├── _aggregate_stats()    (复用 llm_service)
  │     └── _safe_exec()          (复用 llm_service)
  └── llm_service.call_llm_stream()  (复用，用于最终文本 SSE 输出)
```

## 5. 配置项

在 `settings_db.py` 中新增：

| key | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `auto_default_strategy` | string | `"auto"` | 默认策略模式 |
| `auto_analyze_prompt` | text | 内置默认提示词 | 专题分析提示词模板 |
| `auto_parallel_timeout` | int | `8` | 并行检索超时秒数 |
| `auto_semantic_top_k` | int | `10` | 语义检索默认 top_k |
| `auto_semantic_score_threshold` | float | `0.6` | 语义检索默认分数阈值 |

**默认专题分析提示词**（内置，前端可覆盖）：

```
你是一个应急指挥领域的数据分析专家。以下是知识图谱查询结果。

数据概览：
- 节点数量: {node_count}
- 关系数量: {rel_count}
- 节点类型分布: {nodes_by_label}
- 关系类型分布: {rels_by_type}

统计结果（精确计算）:
{stats_json}

用户问题: {question}

请基于以上数据，用中文写一段分析说明：
1. 概括查询到的核心信息
2. 引用统计数值说明关键数据特征
3. 指出数据中值得关注的关系或模式
4. 如有异常或缺失数据，适当说明

要求：语言简洁专业，数值引用准确，150-300字。
```

## 6. 效率优化策略

| 优化 | 说明 | 预期效果 |
|------|------|----------|
| **策略选择极轻量** | max_tokens=50, temperature=0 | ~1s |
| **并行检索超时** | asyncio.wait_for + 8s 超时 | 避免单路拖垮整体 |
| **Schema 缓存复用** | 走现有 `_schema_cache` 全局缓存 | 无额外 DB 查询 |
| **统计脚本+文本合并** | 一次 LLM 调用完成统计 + 生成文本 | 节省 3-5s |
| **统计脚本降级** | LLM 脚本失败时自动用 `_aggregate_stats` 兜底 | 保证可用性 |
| **非流式预缓存** | `stream: false` 时内部仍用流式拼接再返回 | 统一代码路径 |
| **连接池复用** | 三种检索共享同一个 sync_driver 连接 | 减少连接开销 |

## 7. 错误处理

| 场景 | 行为 |
|------|------|
| 所有检索都返回空 | 返回 `result: "未找到相关数据"` + `stats: {}` |
| 统计脚本生成失败 | 降级使用 `_aggregate_stats` 预计算统计 |
| 统计脚本执行失败 | 降级同上了 |
| 检索超时 | 已完成的路中有数据的取最优，全超时则返回错误 |
| LLM 调用失败 | 返回 HTTP 500，detail 中包含失败阶段 |
| 非法 strategy 参数 | 兜底走 `"auto"` |

## 8. 依赖新增

- 无需新增外部依赖。复用现有的 `PythonREPLTool`(langchain-experimental)、`httpx`、`neo4j` 等

## 9. 实施建议

按以下顺序实施：

1. **`strategy_selector.py`** — 先实现 LLM 分类和顺序尝试（独立可测）
2. **`stats_engine.py`** — 专题脚本生成 + 执行（复用现有 _safe_exec）
3. **`auto_analyzer.py`** — 编排逻辑 + SSE 流式
4. **`models.py`** — 新增 `AutoAnalyzeRequest` / `AutoAnalyzeResponse`
5. **`main.py`** — 注册 `/api/query/auto` 端点
6. **`settings_db.py`** — 新增配置项 + AiConfigPanel 前端配置
7. **`deploy/`** — 同步部署目录代码
