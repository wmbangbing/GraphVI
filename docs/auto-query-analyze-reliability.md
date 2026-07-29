# 智能查询分析接口 — 可靠性分析

> 基础功能实现后，再按此文档逐步优化可靠性。

## 链路分析

```
问题 → [1.LLM分类] → [2.检索] → [3.LLM评判] → [4.LLM脚本] → [5.子进程执行] → [6.LLM文本]
                    └─ NL2Cypher
                    └─ 语义检索
                    └─ 语义NL
```

共 6 个环节，4 个依赖 LLM（分类、评判、脚本、文本），1 个涉及子进程。

---

## 风险清单与优化方案

### 1. LLM 分类无校验

**风险：** LLM 返回 `nl/semantic/semantic_nl` 之外的非法值，请求报错。

**优化方案：**

```python
VALID_STRATEGIES = {"nl", "semantic", "semantic_nl"}
def _validate_strategy(raw: str) -> str:
    raw = raw.strip().lower()
    return raw if raw in VALID_STRATEGIES else "nl"  # 兜底走 NL
```

**优先级：** P0 — 成本极低，效果显著

---

### 2. LLM 评判误选

**风险：** NL 有 3 个精确节点，语义有 50 个杂散节点，LLM 只看概要可能选后者。

**优化方案（混合策略）：**

```
parallel 模式下：
  1. NL 有数据 → 检查节点标签是否命中问题关键词
  2. 命中了 → 直接选 NL（跳过 LLM 评判）
  3. 未命中 → LLM 只在 语义/语义NL 之间评判
```

**优先级：** P1 — 不常触发但影响大

---

### 3. 脚本子进程无超时

**风险：** LLM 生成 `while True` 或超大循环，PythonREPLTool 挂死，worker 泄漏。

**优化方案：**

```python
import subprocess

def _safe_exec_with_timeout(script: str, timeout: int = 10) -> dict:
    """subprocess 替代 PythonREPLTool，自带超时"""
    wrapper = f"""..."""
    proc = subprocess.run(
        ["python", "-c", wrapper],
        capture_output=True, text=True,
        timeout=timeout,
    )
    # parse proc.stdout
```

注意：实际实施时需要处理 Windows 下 subprocess 的环境和编码问题。

**优先级：** P0 — 安全隐患

---

### 4. 无短期缓存

**风险：** 相同问题反复查询，浪费 LLM 和 Neo4j 资源。

**优化方案：**

```python
# 最简单的内存缓存，TTL 300s
_cache: dict[str, tuple[float, str]] = {}

def _get_cached(question: str) -> str | None:
    if question in _cache:
        ts, result = _cache[question]
        if time.time() - ts < 300:
            return result
        del _cache[question]
    return None
```

注意：仅缓存最终文本。如果数据变了缓存不感知，对实时性要求高的场景不适用。

**优先级：** P2 — 视调用量决定

---

### 5. 没必要每次跑统计脚本

**风险：** 简单列举问题（"这个事件关联了什么"）也生成+执行脚本，浪费 3-5s。

**优化方案：**

```python
_STAT_KEYWORDS = {"统计", "汇总", "分布", "多少种", "占比", "趋势", "数量", "合计"}

def _needs_script(question: str) -> bool:
    return any(kw in question for kw in _STAT_KEYWORDS)
```

不需要统计时，跳过脚本生成和执行，直接走文本生成。`stats_context` 用 `_aggregate_stats` 预计算结果代替。

**优先级：** P1 — 对延迟影响直接

---

### 6. SSE 连接断开

**风险：** 客户端在流式返回中断开连接，服务端继续生成浪费资源。

**优化方案：**

```python
# FastAPI 的 StreamingResponse 可以检测断开
async def generate():
    try:
        for chunk in async_generator:
            yield chunk
    except asyncio.CancelledError:
        # 客户端断开，清理资源
        pass
```

FastAPI 在客户端断开时会自动抛出 `CancelledError`，在生成器里捕获即可。

**优先级：** P2 — 不影响正确性

---

### 7. 文本生成 LLM 输出空

**风险：** LLM 返回空字符串或只有换行。

**优化方案：**

```python
result_text = (llm_output or "").strip()
if not result_text:
    result_text = f"查询到 {total_nodes} 个节点、{total_relationships} 个关系。{stats_text}，请重试。"
```

**优先级：** P1 — 兜底文案简单有效

---

### 8. 全链路超时

**风险：** 整体请求耗时过长（连续串行时可能 >30s），客户端自行断开。

**优化方案：**

```python
# FastAPI 端点设置总超时
async def auto_analyze_endpoint(body: AutoAnalyzeRequest):
    try:
        result = await asyncio.wait_for(
            auto_analyze(body),
            timeout=25,  # 整体 25s 上限
        )
        return result
    except asyncio.TimeoutError:
        raise HTTPException(504, "智能查询超时，请简化问题后重试")
```

**优先级：** P1 — 对外接口必需

---

## 优先级排序

| 优先级 | 优化项 | 原因 |
|--------|--------|------|
| **P0** | 脚本子进程超时 | 安全隐患 |
| **P0** | LLM 分类校验+兜底 | 成本极低 |
| **P1** | 全链路超时 | 对外接口必需要 |
| **P1** | 统计意图判断 | 减少不必要开销 |
| **P1** | 文本生成空兜底 | 保证有输出 |
| **P1** | NL 优先于 LLM 评判 | 提高准确率 |
| **P2** | 短期缓存 | 视调用量决定 |
| **P2** | SSE 断开处理 | 资源优化 |

## 建议实施节奏

1. 第一版：基础功能 + **P0 优化** + 全链路超时
2. 后续迭代：P1 优化逐步加上
3. 按需：P2 优化
