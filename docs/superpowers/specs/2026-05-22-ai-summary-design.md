# AI 总结分析 + 系统设置页美化 设计

## 概述

为知识图谱系统添加 AI 总结分析功能。后端对接 OpenAI 兼容接口的大模型，对当前查询到的图谱数据进行总结分析。前端提供 LLM 连接配置和总结提示词配置功能。同时优化系统设置页的 UI 布局。

## 架构

```
前端                                             后端
┌──────────────────────┐         ┌──────────────────────────┐
│ GraphPage            │         │ POST /api/analyze        │
│  ┌─ 预设问题列表 ─┐  │ ←────→ │  body: {nodes, rels,     │
│  │  AI总结 按钮   │  │         │    prompt}               │
│  └─ 结果展示区域 ─┘  │         │  → LLM Service → 总结    │
│                      │         │                          │
│ SettingsPage         │         │ GET/PUT /api/settings    │
│  ┌─ 预设管理卡片 ─┐  │ ←────→ │  {key: value}            │
│  │               │  │         │  → SQLite settings表     │
│  └─ AI配置卡片 ──┘  │         └──────────────────────────┘
└──────────────────────┘
```

## 后端设计

### SQLite 新增 settings 表

```sql
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

存储以下配置项：

| key | 说明 | 默认值 |
|-----|------|--------|
| `llm_endpoint` | API 地址 | `https://api.openai.com/v1` |
| `llm_api_key` | API 密钥 | `""` |
| `llm_model` | 模型名 | `gpt-4o` |
| `summary_prompt` | 总结提示词模板 | `你是一个知识图谱分析助手。以下是一组知识图谱数据，包含节点和关系。请对数据进行分析总结，提炼关键信息、实体关系模式和数据特征。\n\n节点数量: {node_count}\n关系数量: {rel_count}\n\n节点列表:\n{nodes}\n\n关系列表:\n{rels}\n\n请用中文给出分析总结：` |

### 新增 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 获取所有设置 |
| PUT | `/api/settings` | 批量保存设置 `{key: value, ...}` |
| POST | `/api/analyze` | 执行 AI 分析 `{nodes, relationships, prompt?}` |

### LLM 服务 (`llm_service.py`)

```python
async def call_llm(messages: list, endpoint: str, api_key: str, model: str) -> str:
    """调用 OpenAI 兼容 API"""
    # 使用 httpx 发送 POST 请求
    # 返回响应中的 content
```

- 使用 `httpx` 异步 HTTP 客户端（或 `openai` Python SDK）
- 支持 OpenAI 兼容接口（任意 endpoint）
- 请求时从 SQLite 读取当前配置（endpoint, key, model）
- 如果请求体中没有传入 prompt_template，使用数据库中存储的默认模板

### POST /api/analyze 处理流程

1. 接收前端发送的 `{nodes, relationships, custom_prompt?}`
2. 从 settings 表读取 `llm_endpoint`, `llm_api_key`, `llm_model`
3. 如果 `custom_prompt` 为空，从 settings 读 `summary_prompt`
4. 将节点/关系数据格式化为文本
5. 调用 `call_llm()`
6. 返回 `{summary: "..."}`

## 前端设计

### SettingsPage - 设置页改造

设置页使用 `max-width: 960px`，原有 `settings-body` 保留。每个功能区块使用 `el-card` 包裹：

```
┌─ el-card: 预设问题 ────────────────────────────┐
│  (现有 PresetManager，表格占满 card 宽度)       │
└─────────────────────────────────────────────────┘

┌─ el-card: AI 配置 ────────────────────────────┐
│  ┌─ el-form: LLM 连接 ──────────────────┐     │
│  │  el-input: endpoint                   │     │
│  │  el-input: API Key (password 类型)    │     │
│  │  el-input: model                      │     │
│  └───────────────────────────────────────┘     │
│  ┌─ el-form: 总结提示词 ────────────────┐     │
│  │  el-input type="textarea" rows="6"    │     │
│  └───────────────────────────────────────┘     │
│  [保存配置] el-button                           │
└─────────────────────────────────────────────────┘
```

### GraphPage - AI 总结区域

在侧边栏 QueryEditor 下方添加：

```
┌─ 侧边栏 ──────────────────────────┐
│  预设问题列表                       │
│  ────────────────────────────────  │
│  Cypher 查询编辑器                  │
│  ────────────────────────────────  │
│  [AI 总结] el-button               │
│  ┌─ 总结结果 ──────────────────┐   │
│  │  (markdown 渲染的文本内容)    │   │
│  │  [重新生成] [收起]           │   │
│  └────────────────────────────┘   │
└─────────────────────────────────────┘
```

- 点击"AI 总结"按钮 → 发送当前 graphData 到 `/api/analyze`
- 加载中显示 loading 状态
- 结果使用 markdown 渲染展示（可用 `markdown-it` 或简单处理）
- 每次新查询后清空之前的总结结果
- 无数据时按钮置灰

### 样式调整

- 设置页 `settings-body` 去除 `max-width: 960px` 限制，改用 `max-width: 1000px` + `margin: 0 auto`
- `el-card` 内边距统一
- 预设表格宽度占满
- AI 配置表单使用 `label-position="top"`
- 侧边栏总结结果区域使用滚动 + `max-height` 限制

## 依赖

**后端新增依赖：**
- `httpx` — 异步 HTTP 客户端（或使用 `openai` SDK）
- 添加到 `backend/requirements.txt` 和 `deploy/backend/requirements.txt`

## 验证

1. 设置页可填写/保存/读取 LLM 配置和提示词
2. 图谱主页点击"AI 总结"后调用后端，返回总结文本
3. 总结结果在侧边栏正确渲染（markdown）
4. 新查询后总结结果自动清空
5. 设置页 UI 美观、卡片占满、预设表格整齐
6. 无数据时"AI 总结"按钮置灰
7. 构建无错误
