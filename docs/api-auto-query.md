# 智能查询分析接口 `/api/query/auto`

智能知识图谱查询接口。输入自然语言问题，系统自动选择最优查询策略，返回结构化的图谱数据和文本描述。

---

## 请求

```
POST /api/query/auto
Content-Type: application/json
```

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `question` | string | 是 | - | 自然语言问题，如"查询近期广西的事件" |
| `strategy` | string | 否 | `"auto"` | 查询策略：`"auto"`(自动选择) |
| `stream` | bool | 否 | `false` | 是否 SSE 流式输出 |
| `top_k` | int | 否 | settings 配置值 | 语义检索最多返回结果数 |
| `score_threshold` | float | 否 | settings 配置值 | 语义检索分数阈值(0-1) |

### 请求示例

```json
{
    "question": "查询近期广西的应急事件",
    "strategy": "auto",
    "stream": false
}
```

---

## 响应

### 非流式模式 (`stream: false`)

```json
{
    "result": "树状结构文本...",
    "strategy_used": "nl"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `result` | string | 树状文本结果，展示节点关系链 |
| `strategy_used` | string | 实际使用的策略：`nl` / `semantic_nl` |

> `nl`：自然语言转 Cypher 查询<br>
> `semantic_nl`：语义检索 → LLM 生成遍历 Cypher

### SSE 流式模式 (`stream: true`)

流式事件推送，客户端通过 `EventSource` 或 HTTP 流式读取：

```
event: strategy_start
data: {"message": "正在分析查询策略..."}

event: strategy
data: {"strategy": "nl"}

event: retrieve_start
data: {"message": "正在查询数据（策略：nl）..."}

event: retrieve
data: {"method": "nl", "nodes": 26, "relationships": 18}

event: text_start
data: {"message": "正在生成结果..."}

event: text
data: "树状文本内容（可能分多次推送）..."

event: done
data: {"strategy_used": "nl", "total_nodes": 26, "total_relationships": 18}
```

| 事件 | 说明 |
|------|------|
| `strategy_start` | 开始分析策略 |
| `strategy` | 策略选择结果 |
| `retrieve_start` | 开始查询数据 |
| `retrieve` | 查询完成，返回数据量 |
| `text_start` | 开始生成结果文本 |
| `text` | 结果文本分块 |
| `done` | 查询完成汇总 |

---

## 查询策略说明

`auto` 模式根据问题关键词自动选择：

| 策略 | 适用场景 | 示例问题 | 耗时 |
|------|---------|---------|------|
| `nl` | 按已知字段查询（地区编码、节点标签等） | "查询广西的事件"、"列出所有设备" | ~10-30s |
| `semantic_nl` | 按具体名称/概念查询（台风名、事件名等） | "查询巴威台风相关事件" | ~30-90s |

---

## 输出示例

```
[dm_event_info] 事件「巴威台风应急事件」类型:台风 级别:Ⅰ级 状态:响应中 时间:2026-07-07
  ├─触发申请─(dm_dispatch_apply)
  [dm_dispatch_apply] 申请 类型:地市调度 紧急:紧急 ...
    ├─生成任务─(dm_dispatch_task)
    [dm_dispatch_task] 任务 状态:待接收 负责人:张三 ...
```

---

## 错误处理

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 查询成功 |
| 400 | 参数错误（question 为空等） |
| 500 | 服务端错误（LLM 调用失败、Cypher 执行失败等） |

错误响应格式：

```json
{
    "detail": "错误描述信息"
}
```

