# GraphVI 优化工作总结（2026-07-30 ~ 07-31）

## 一、背景与目标

系统基于 LLM 生成 Cypher 进行知识图谱语义查询。目标是：
- **数据完整**：图谱渲染需要所有节点和关系
- **查询高效**：减少笛卡尔积、索引利用、传输开销
- **LLM 输出不可靠时的兜底**：fix 函数自动修复

## 二、修复的 Bug

| Bug | 根因 | 修复 |
|---|---|---|
| `/api/query/auto` UnboundLocalError | `tree_builder.py` 中 `all_with_rels` 缩进错误，放在 for 循环内 | 提交 `3c33a22` 修复缩进 |
| `name 'httpx' is not defined` | `semantic_search.py` 缺 `import httpx` | 提交 `7e59369` 补充 |
| GraphView `zoom()` 报错 | 3D 模式下无 `zoom()` 方法 | 2D/3D 分支判断 |
| LLM 空响应 | `deepseek-v4-flash` 是推理模型，复杂 prompt 下 `reasoning_content` 耗尽 token | 请求体加 `thinking: {type: disabled}` |

## 三、LLM 客户端连接复用（已提交）

| 提交 | 内容 |
|---|---|
| `389de40` | LLM client 连接复用 + settings 失效逻辑 |
| `7e59369` | Embedding client 连接复用 + httpx 导入 |

## 四、Cypher 查询优化探索（核心主线）

### 4.1 优化目标演进

从"让 LLM 生成完美查询"逐步转向"fix 函数兜底 + 简单 prompt"。

### 4.2 尝试过的方案及结论

| 方案 | 结果 | 结论 |
|---|---|---|
| 教 LLM 用 `WITH + collect` 防笛卡尔积 | ❌ LLM 学不会 WITH 作用域 | 放弃 |
| CALL 子查询 | ✅ 隔离作用域，防笛卡尔积 | 采用 |
| 教 LLM 生成去重结构（共享路径走一次）| ❌ prompt 越复杂 LLM 越乱 | 放弃，fix 兜底 |
| 硬编码 `USING INDEX` / label 过滤 | ❌ 入口节点类型不固定 | 放弃，保持通用 |

### 4.3 性能测试数据

**入口匹配（PROFILE）：**
| 方式 | dbHits |
|---|---|
| `elementId(entry)` | 19 |
| `entry.id`（RANGE 索引正常）| 19 |
| `entry.id`（planner 选 LOOKUP 坏路径）| 18M |

**查询结构（5 事件）：**
| 方案 | dbHits | 说明 |
|---|---|---|
| CALL 子查询 | 9,191 | 链隔离，无笛卡尔积 |
| OPTIONAL MATCH + WITH | 238,399 | 链间笛卡尔积（26x）|

**大规模（100 事件）：**
| 方案 | 时间 | 节点 |
|---|---|---|
| CALL 3x | 22.3s | 896 |
| OM+WITH | 23.6s | 929 |

**300 事件 → 打崩远程服务器**（数据量爆炸）

### 4.4 网络传输优化（最大收益）

**发现：embedding 字段 2560 维 = 20KB/节点，占传输 99%**

| 方案 | 时间 | 序列化 |
|---|---|---|
| 完整节点（含 embedding）| 27.9s | 19,709 KB |
| APOC `removeKeys` 排除 embedding | 3.3s | 378 KB |
| **加速比** | | **8.5x** |

### 4.5 v2 fix 架构（最终验证通过）

**核心冲突**：APOC map 包装破坏节点身份 → UNWIND 复用失败

**v2 方案**：
```cypher
-- 内部 CALL：真节点（身份保留，可 UNWIND）
-- 最外层 RETURN：包成 APOC map 排除 embedding
RETURN [x IN related_events | {id: elementId(x), labels: labels(x),
                               props: apoc.map.removeKeys(x, ['embedding'])}]
```

**验证结果**：12.4s，245 节点 + 251 关系，`any node has embedding: False` ✅

### 4.6 遗留问题

| 问题 | 原因 | 方向 |
|---|---|---|
| 匿名关系（图上无边）| LLM 不命名 `[r:...]` | fix 命名 + 补边 |
| PARENT_OF*1..3 展开慢（57s）| 事件树深度遍历 | 独立优化 |
| 入口索引不通用 | 语义匹配节点类型多变 | 保持通用 |

## 五、关键结论

1. **LLM 生成 Cypher 不可靠**：匿名关系、作用域 bug、复杂度波动 → fix 函数必须存在
2. **prompt 保持简洁**：只引导基本结构（CALL + 索引字段），不做复杂教学
3. **v2 embedding 排除有效**：内部真节点 + 最外层 wrap
4. **不能硬编码 label/索引**：语义检索入口节点类型不固定
5. **embedding 是最大传输瓶颈**：排除后 8.5x 加速

## 六、后续 TODO

- [x] fix 函数：命名匿名关系 + 补边
- [x] `_parse_records` v2：识别 map 节点
- [x] LLM `thinking: disabled` 整合进 `llm_service.py`
- [x] 简化 `semantic_search.py` 的 prompt（保留索引修改）
- [ ] PARENT_OF 展开优化（限深或改用其他遍历）

## 七、语义NL接口专项优化（7/31 晚间）

针对 `/api/query/semantic-nl`（LLM 生成 Cypher 遍历入口节点）的效率优化。

### 7.1 修复 fix 函数不支持 `CALL (entry) {` 显式作用域语法

**症状**：`Semantic NL query failed: Variable child_event not defined (SyntaxError)`

**根因**：LLM 用 Neo4j 5.26 显式作用域 `CALL (entry) { ... }`，但 `_fix_unnamed_rels` 的 `has_call` 检测正则 `\bCALL\s*\{` 匹配不到（中间隔着 `(entry)`）→ 误走非 CALL 分支 → 把 CALL 内部变量 `child_event`/`r1` 泄漏进主 RETURN。

**修复**（`nl2cypher.py`）：
1. `has_call` / CALL 提取正则改为 `\bCALL\s*(?:\(\s*[A-Za-z_]\w*\s*\))?\s*\{`，同时支持隐式/显式作用域
2. orphan 打包排除 `collect(DISTINCT v)` 已消费的变量（`collected_vars` 从整个 CALL 块提取）

### 7.2 语义NL提示词语义裁剪

**症状**：问"仅考虑父子关系的事件节点"，LLM 生成 10 个 CALL 穷举所有关系类型。

**根因**：提示词"Each CALL handles ONE relationship chain" + 多 CALL 模板 + 无"只遍历相关问题关系"约束，诱导 LLM 穷举 schema 全部关系。

**修复**（`semantic_search.py` prompt）：
- 加"只遍历与问题语义相关的关系链，忽略无关关系类型"
- "CALL 数量最小化（通常 1-3），不要穷举所有关系类型"
- 父子关系示例（只问父子 → 只用 PARENT_OF）

**效果**：10 CALL → 1-2 CALL

### 7.3 embedding 泄漏修复（`_wrap_return_apoc` + orphan 打包）

**根因 1**：`_wrap_return_apoc` 的 `match_section = cypher.split("RETURN")[0]` 取**第一个** CALL 的 RETURN → `node_vars` 只含第一个 CALL 的变量 → 后续 CALL 的别名（如 `parent_events`）不排除 embedding → 泄漏传输。

**根因 2**：orphan 打包的 `collected_vars` 从 `inner_fixed[:ret_m.start()]`（RETURN 前）提取，但 `collect()` 在 RETURN 里 → `child_event` 被重复 collect 进 `_path_N`（带 embedding）。

**修复**：
1. `match_section` 改用主 RETURN 位置（`rindex`）→ 所有 CALL 变量被识别，全部节点集合排除 embedding
2. `collected_vars` 从整个 CALL 块提取 → `_path_N` 只含关系（无 embedding）

### 7.4 label 注入：入口查询走 RANGE 索引（**最大收益**）

**症状**：Neo4j 查询耗时 14-22s，仅查 5 个事件 27 条 PARENT_OF 关系。

**根因**：入口 `MATCH (entry) WHERE entry.id IN [...]` 的 `entry` 无 label → planner 无法用 `dm_event_info` 的 RANGE index → 全表扫描 1041 万节点 → 12-17s。

**实测对比**（5 个 entry）：
| 方式 | 耗时 |
|---|---|
| 无 label `(entry)` | 17.03s |
| 带 label `(entry:dm_event_info)` | 0.71s |
| 多 label OR | 0.27s |
| 完整语义NL Cypher（带 label） | 2.76s |

**修复**（`semantic_search.py`）：`_inject_entry_labels()` 基于向量检索返回的 entry 实际 labels（非 `_Embeddable`）注入：
- 单 label：`MATCH (entry)` → `MATCH (entry:dm_event_info)`
- 多 label：`... IN [...] AND (entry:L1 OR entry:L2)`
- 不依赖 LLM，fix 后自动修正

**效果**：Neo4j 查询 22s → 1-3s（**10-30 倍**）

### 7.5 schema 缓存单次获取

**根因**：预热时 `nl_schema_examples=true` → `get_schema` 两次独立获取（semantic_nl 无 samples + nl2cypher 带 samples）→ 两次 `db.schema.*`。

**修复**（`nl2cypher.py` + `main.py`）：
- `get_schema` 无 samples 版本从带 samples 缓存**剥离 `Sample:` 行**派生
- 预热只获取一次（按配置），另一份自动派生

**效果**：预热只触发 1 次 `db.schema.*`（此前 2 次），启动时间约减半。

### 7.6 语义NL耗时日志

在 `semantic_nl_search` 增加：
```python
=== [SemanticNL] LLM 调用耗时: X.XXs ===
=== [SemanticNL] Neo4j 查询耗时: X.XXs ===
=== [SemanticNL] 总耗时: X.XXs ===
```

### 7.7 性能汇总（同一查询）

| 阶段 | Neo4j 查询 | 总耗时 |
|---|---|---|
| 原始（无 label + embedding 泄漏） | 22.0s | 28.8s |
| 修复 embedding 泄漏 | 14.7s | 18.7s |
| + label 注入 | 1.4s | 9.8s |
| 稳定区间（多次测试） | 0.7-2.7s | 6-11s |
