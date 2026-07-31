# _fix_unnamed_rels 完整场景分析

## 功能目标

对 LLM 生成的有缺陷 Cypher 进行后处理修补，确保图谱可渲染：
1. 匿名节点 → 命名（`(:Label)` → `(n1:Label)`）
2. 匿名关系 → 命名（`[:TYPE]` → `[r1:TYPE]`）
3. 方向转无向（`->` / `<-` → `-`）
4. RETURN 补全所有 MATCH 变量

## 所有可能出现的 Cypher 模式

### 一、MATCH 部分

| # | 模式 | 例子 | 当前能处理？ |
|---|------|------|------------|
| M1 | 标准 MATCH | `MATCH (a:Label)-[:R]-(b:Label)` | ✅ |
| M2 | 多 MATCH | `MATCH (a)-[:R1]-(b) MATCH (b)-[:R2]-(c)` | ✅ |
| M3 | OPTIONAL MATCH | `OPTIONAL MATCH (a)-[:R]-(b)` | ✅ |
| M4 | 多 OPTIONAL MATCH | 连续多个 OPTIONAL MATCH | ✅ |
| M5 | 带 WHERE 的 MATCH | MATCH + `WHERE x.pac STARTS WITH '45'` | ⚠️ 已修 |
| M6 | WHERE 含 CONTAINS/ENDS WITH | `WHERE x.name CONTAINS 'test'` | ✅ (WITH 已排除) |
| M7 | 多类型关系 | `-[:TYPE1\|:TYPE2]-` | ✅ |
| M8 | 变长路径 | `-[:TYPE*1..3]-` | ⚠️ 未测试 |
| M9 | 关系属性 | `-[:TYPE {prop: val}]-` | ⚠️ 未测试 |
| M10 | 匿名节点和匿名关系混合 | `(:A)-[:R]->(:B)` | ✅ |

### 二、RETURN 部分

| # | 模式 | 例子 | 当前能处理？ |
|---|------|------|------------|
| R1 | 标准 RETURN | `RETURN a, b` | ✅ |
| R2 | RETURN DISTINCT | `RETURN DISTINCT a` | ⚠️ 当前可能破坏语法 |
| R3 | RETURN + 聚合 | `RETURN a, count(b)` | ⚠️ 当前可能破坏 |
| R4 | RETURN 带 ORDER BY | `RETURN a ORDER BY a.name` | ✅ |
| R5 | RETURN 带 SKIP | `RETURN a SKIP 10` | ✅ (LIMIT/ORDER/SKIP 都会保留) |
| R6 | RETURN 已完整 | `RETURN a, b, r1, r2, r3` | ✅ 不变 |

### 三、变量名冲突

| # | 模式 | 例子 | 当前能处理？ |
|---|------|------|------------|
| V1 | 已存在 n1/r1 | MATCH 中已有 `[r1:TYPE]` | ✅ 会跳过已存在的 |
| V2 | 自动命名与已有冲突 | 已有 `r9`，自增到 `r10` | ✅ |
| V3 | n1 冲突 | 用户节点叫 `n1` | ✅ |

### 四、方向处理

| # | 模式 | 例子 | 当前能处理？ |
|---|------|------|------------|
| D1 | 有向出 | `-[:TYPE]->` | ✅ |
| D2 | 有向入 | `<-[:TYPE]-` | ✅ |
| D3 | 无向 | `-[:TYPE]-` | ✅ |
| D4 | 已命名有向 | `-[r:TYPE]->` | ✅ 只转方向不改名 |

### 五、边界情况

| # | 模式 | 风险 | 当前状态 |
|---|------|------|---------|
| E1 | 子查询 `EXISTS { MATCH ... }` | 内部 MATCH 被错误处理 | ⚠️ 未测试 |
| E2 | `CALL { ... }` 子查询 | 同上 | ⚠️ 未测试 |
| E3 | UNWIND | `UNWIND [...] AS x RETURN x` | ✅ 无 MATCH，不影响 |
| E4 | 字符串字面量含 `-[:` | `WHERE x = '-[:TEST]-'` | ⚠️ 可能被误匹配 |
| E5 | **大小写 RETURN** | `return a, b`（小写） | ⚠️ `\bRETURN\b` 大小写敏感 |

## 验证过的流程

```
                    Cypher 输入
                        │
                        ▼
    0. 提取已有变量名（去重）
                        │
                        ▼
    1. 定位 RETURN 位置（只查 RETURN 不查 WITH）
                        │
                        ▼
    2. MATCH 区间命名匿名节点  (:Label) → (n1:Label)
                        │
                        ▼
    3. MATCH 区间命名匿名关系  [:TYPE] → [r1:TYPE]（3种方向）
                        │
                        ▼
    4. 方向转无向  -> / <- → -
                        │
                        ▼
    5. 收集 MATCH 区间所有变量（节点+关系）
                        │
                        ▼
    6. RETURN 补全缺失变量
                        │
                        ▼
                    输出 Cypher
```

## 未覆盖的已知风险

1. **E1/E2 子查询**：`EXISTS { MATCH (a)-[:R]-(b) }` — 内部的 MATCH 关系也会被处理并补进外部 RETURN，导致语义错误
2. **E4 字符串字面量**：`WHERE x = '-[:TEST]-'` — 会被正则匹配到并改名，破坏语义
3. **R2/R3 聚合/去重 RETURN**：在 `RETURN a, count(b)` 中追加变量可能破坏聚合语义
4. **E5 小写 return**：Python 正则默认大小写敏感，`\bRETURN\b` 不匹配 `return`
5. **M8 变长路径**：`-[:TYPE*1..3]-` 的 `*` 和 `..` 在正则中可能异常
