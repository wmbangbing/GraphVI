# AI 总结流式展示 Implementation Plan

**Goal:** 将 AI 总结改为右侧浮动面板 + 流式 SSE 响应 + markdown 渲染

**Architecture:** 后端 `POST /api/analyze` 改为 SSE 流式返回，前端右侧面板使用 `vue-element-plus-x` Bubble + `markdown-it` 渲染

---

### Task 1: 后端流式 API

**Files:**
- Modify: `backend/llm_service.py`
- Modify: `backend/main.py`

将 `call_llm` 改为 async generator，逐 token yield。端点返回 `StreamingResponse`。

### Task 2: 前端右侧面板 + 流式 + markdown

**Files:**
- Modify: `frontend/src/components/AiSummaryPanel.vue`
- Modify: `frontend/src/views/GraphPage.vue`
- Modify: `frontend/src/style.css`
- Install: `markdown-it`

移除旧 AiSummaryPanel，新建右侧浮动面板实现。

### Task 3: 同步 deploy 目录

**Files:**
- Modify: `deploy/backend/llm_service.py`
- Modify: `deploy/backend/main.py`
