# AI 总结流式展示优化设计

## 概述
将 AI 总结从左侧面板移到图谱右侧浮动面板，改为流式（SSE）响应 + markdown 渲染。

## 改动方案

### 后端 — 流式响应
`POST /api/analyze` 改为返回 SSE 流，使用 FastAPI `StreamingResponse`。`llm_service.call_llm` 使用 `httpx` 的 `stream=True` 逐个 token yield。

### 前端 — 右侧浮动面板
图谱画布右侧贴边竖条标签 "AI 总结"，点击滑出 360px 面板。

**技术选型：**
- `vue-element-plus-x` 的 `useXStream` + `Bubble` 处理流式展示
- `markdown-it` 渲染 markdown 内容

### 交互流程
1. 图谱画布右侧边缘显示竖条标签"AI 总结"
2. 点击标签 → 面板从右侧滑出 (360px)
3. 面板内有"生成总结"按钮
4. 点击后发起 SSE 请求，流式接收 token 实时渲染
5. 面板有 ✕ 关闭按钮
6. 新查询自动清空上次结果
