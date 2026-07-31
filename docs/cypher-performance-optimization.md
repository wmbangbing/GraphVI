# Cypher 查询性能优化实践

> 基于 Neo4j 官方文档、社区最佳实践以及 GraphVI 实际 Profiling 数据总结。

## 一、当前系统 Profiling 数据

测试环境：5 个入口 dm_event_info 节点，查询关联的车辆/人员/装备。

| 查询版本 | 执行时间 | dbHits | 说明 |
|---|---|---|---|
| `PARENT_OF*0..` 全部 4 个 CALL | **129s** | ~158k | LLM 原始输出 |
| `*0..` 仅第一个 CALL | **16s** | - | 去掉子 CALL 的 PARENT_OF |
| `*1..3` 仅第一个 CALL | **11s** | - | **最优方案** |
| `*0..` 但有 index 扫描 | 0.01s | 18 | 单个 elementId 查询成本 |

**关键发现：** 数据量很小（总共 18 个事件节点），但查询跑了 158k dbHits、2 分钟。问题在 Cypher 结构上，不是数据量。

---

## 二、Neo4j 官方最佳实践

### 2.1 变长路径必须有上界

> **Source:** [Neo4j Cypher Manual - Query Tuning](https://neo4j.com/docs/cypher-manual/current/planning-and-tuning/query-tuning/)

```cypher
// ❌ 无界变长 — 可能遍历全图
MATCH (n)-[:REL*]->(m)

// ✅ 有界变长 — 明确限制范围
MATCH (n)-[:REL*1..5]->(m)
```

**原因：** 变长路径的中间结果是指数增长的。每个节点每多一跳，路径数 × 平均度数。

### 2.2 用 `PROFILE` 分析瓶颈

```cypher
PROFILE MATCH (n:Label) WHERE n.id IN $ids ...
```

关注指标：
| 指标 | 含义 | 健康值 |
|---|---|---|
| `dbHits` | 数据库访问次数 | 越小越好 |
| `rows` | 每步产生的行数 | 应逐步减少 |
| `estimatedRows` | 优化器估算行数 | 与实际 rows 差距过大说明统计信息过时 |

### 2.3 从最有选择性的节点开始查询

> **Source:** [Neo4j Blog - Slow Cypher Statements](https://neo4j.com/blog/developer/slow-cypher-statements-fix/)

- 优先匹配能过滤掉最多数据的模式
- 使用 `USING INDEX` 提示优化器选择合适的起始点
- `elementId()` 是函数调用，不走索引，但节点少时无所谓

### 2.4 避免 OPTIONAL MATCH 之间的笛卡尔积

> **Source:** [Neo4j Knowledge Base - Cross Product](https://neo4j.com/developer/kb/cross-product-cypher-queries-will-not-perform-well/)

多个 `OPTIONAL MATCH` 如果不共享变量，会产生笛卡尔积：

```cypher
// ❌ OPTIONAL MATCH 间无共享变量 — 笛卡尔积
OPTIONAL MATCH (a)-[:R1]->(b)
OPTIONAL MATCH (c)-[:R2]->(d)

// ✅ 同一入口，结果可控
OPTIONAL MATCH (entry)-[:R1]->(b)
OPTIONAL MATCH (entry)-[:R2]->(d)
```

### 2.5 CALL 子查询是最佳实践

> **Source:** [Neo4j Cypher Manual - Subqueries](https://neo4j.com/docs/cypher-manual/current/subqueries/)

`CALL { ... }` 子查询是 Neo4j 5.x 推荐的防笛卡尔积方案：
- 每个 CALL 内部独立执行
- CALL 之间可以通过 importing WITH 传参
- **Neo4j 5.x 中 CALL 是顺序执行的**（不并行）

### 2.6 善用 Pattern Comprehension

替代多条 OPTIONAL MATCH + collect 的更高效写法：

```cypher
// OPTIONAL MATCH + collect（产生中间笛卡尔积）
OPTIONAL MATCH (entry)-[r1:R1]-(n1)
OPTIONAL MATCH (entry)-[r2:R2]-(n2)
RETURN collect(DISTINCT n1), collect(DISTINCT n2)

// Pattern comprehension（直接从入口展开，无中间行）
RETURN [(entry)-[:R1]-(n1) | n1] AS ns1,
       [(entry)-[:R2]-(n2) | n2] AS ns2
```

### 2.7 索引策略

> **Source:** [Neo4j Cypher Manual - Indexing](https://neo4j.com/docs/cypher-manual/current/indexes/)

| 索引类型 | 适用场景 | 创建语法 |
|---|---|---|
| RANGE | 精确匹配、范围查询 | `CREATE INDEX FOR (n:Label) ON (n.prop)` |
| TEXT | 字符串模糊搜索 | `CREATE FULLTEXT INDEX ... FOR (n:Label) ON EACH [n.prop]` |
| VECTOR | 向量相似度搜索 | `CREATE VECTOR INDEX ...` |
| POINT | 地理空间查询 | `CREATE POINT INDEX ...` |

**当前系统只有 `id` 字段有索引**，缺少常用业务字段索引。

---

## 三、本系统当前瓶颈分析

### 3.1 现状

```
MATCH (entry) WHERE elementId(entry) IN $ids  →  dbHits=18×5=90
CALL 1: PARENT_OF*1..3                        →  查找关联事件
CALL 2: PARENT_OF*1..3 + 4-hop path           →  重复遍历
CALL 3: PARENT_OF*1..3 + 4-hop path           →  重复遍历
CALL 4: PARENT_OF*1..3 + 4-hop path           →  重复遍历
RETURN: 4× _path_N collects                   →  大量数据列
```

### 3.2 问题清单

| 问题 | 影响 | 优先级 |
|---|---|---|
| `PARENT_OF*0..` 无界变长 | 指数级路径爆炸，129s → 超时 | P0 已修 |
| 子 CALL 重复 PARENT_OF 遍历 | 3 个多余遍历，16s→129s | P0 |
| 3 个本质相同的 CALL（equip/veh/person） | 3 倍重复 | P1 |
| `_path_N` 收集冗余数据（event 重复出现） | 数据传输量大 | P2 |
| 没有业务字段索引 | elementId 全表扫描 | P2 |

### 3.3 优化建议（按优先级）

#### P0：fix 函数增强

```python
# 当前已有：*0.. → *1..3
cypher = re.sub(r'\[([^:]*):(\w+)\*0\.\.\]', r'[\1:\2*1..3]', cypher)

# 需要新增：移除子 CALL 中的 PARENT_OF*（保留第一个 CALL）
# 正则匹配非首个 CALL 块内的 PARENT_OF 模式并删除
```

预期效果：129s → 11s（已验证）

#### P1：合并重复 CALL

将 equipment、vehicle、person 三个 CALL 合并为一个，共享前 4 跳路径。但实测合并后 13.8s 反而比 11s 慢（OPTIONAL MATCH 太多导致中间行膨胀），需要评估是否值得做。

#### P2：减少冗余 collect

`_path_N` 当前收集了 `apply`、`task`、`record`、`event`、`r1`-`r12`。其中 `event` 已在 `related_events` 中出现，`apply/task/record` 在多个 `_path_N` 中重复。可以考虑：

1. 每个中间节点只 collect 一次（在第一个出现的 CALL 中）
2. 后续 CALL 只 collect 关系变量

#### P3：建业务字段索引

```cypher
CREATE INDEX FOR (n:dm_event_info) ON (n.event_code);
CREATE INDEX FOR (n:dm_person_info) ON (n.person_name);
CREATE INDEX FOR (n:dm_vehicle_info) ON (n.plate_no);
CREATE INDEX FOR (n:dm_equipment_info) ON (n.equipment_code);
```

#### P4：考虑 Pattern Comprehension

将 CALL 内部的 4 条 OPTIONAL MATCH 改为 pattern comprehension：

```cypher
// 当前
OPTIONAL MATCH (entry)-[r1:R1]-(n1)
OPTIONAL MATCH (n1)-[r2:R2]-(n2)
...

// 改为
RETURN [(entry)-[:R1]->(n1)-[:R2]->(n2)-[:R3]->(n3) | {n1, n2, n3, r: ...}] AS chain
```

Pattern comprehension 在 Neo4j 内部执行更高效，且不会产生中间笛卡尔积行。

---

## 四、总结

| 优化步骤 | 预期时间 | 累计加速 |
|---|---|---|
| 原始版本 | 129s | 1x |
| + `*0..` → `*1..3` + 移除子 CALL PARENT_OF | 11s | **11.7x** |
| + 建索引 | ~5s | ~25x |
| + Pattern comprehension | ~2s | ~60x |
