# AI 总结分析 + 设置页美化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 添加 AI 总结分析功能，支持 LLM 配置与提示词自定义，同时美化系统设置页 UI

**Architecture:** 后端 `settings_db.py` 在 SQLite 中存储 LLM 配置和提示词，`llm_service.py` 通过 OpenAI 兼容 API 调用大模型对图谱数据进行总结；前端设置页使用 `el-card` 分组展示预设管理和 AI 配置，图谱主页侧边栏添加 AI 总结按钮与结果展示

**Tech Stack:** Python httpx, FastAPI, SQLite, Vue 3, Element Plus

---

### Task 1: 后端 — Settings API + LLM 服务

**Files:**
- Create: `backend/settings_db.py`
- Create: `backend/llm_service.py`
- Modify: `backend/models.py`
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 创建 settings_db.py**

```python
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "presets.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_settings_table():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    # Insert defaults if not exist
    defaults = {
        "llm_endpoint": "https://api.openai.com/v1",
        "llm_api_key": "",
        "llm_model": "gpt-4o",
        "summary_prompt": "你是一个知识图谱分析助手。以下是一组知识图谱数据，包含节点和关系。请对数据进行分析总结，提炼关键信息、实体关系模式和数据特征。\n\n节点数量: {node_count}\n关系数量: {rel_count}\n\n节点列表:\n{nodes}\n\n关系列表:\n{rels}\n\n请用中文给出分析总结：",
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()
    conn.close()


def get_all_settings():
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def set_setting(key: str, value: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    conn.close()


def set_multiple_settings(settings: dict):
    conn = get_connection()
    for key, value in settings.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()
    conn.close()
```

- [ ] **Step 2: 创建 llm_service.py**

```python
import httpx

from settings_db import get_all_settings


def _format_graph_data(nodes: list, relationships: list) -> dict:
    """格式化图谱数据为 LLM 友好的文本"""
    node_lines = []
    for n in nodes:
        labels = ", ".join(n.get("labels", []))
        props = ", ".join(f"{k}={v}" for k, v in n.get("properties", {}).items()
                         if not str(v).startswith("http"))
        caption = n.get("caption") or n.get("properties", {}).get("name", "")
        node_lines.append(f"  [{labels}] {caption} ({props})" if props else f"  [{labels}] {caption}")

    rel_lines = []
    for r in relationships:
        rel_lines.append(f"  {r.get('source')} --[{r.get('type')}]--> {r.get('target')}")

    return {
        "node_count": len(nodes),
        "rel_count": len(relationships),
        "nodes": "\n".join(node_lines) if node_lines else "（无节点数据）",
        "rels": "\n".join(rel_lines) if rel_lines else "（无关系数据）",
    }


def _build_prompt(template: str, data: dict) -> str:
    return template.format(**data)


async def call_llm(nodes: list, relationships: list, custom_prompt: str | None = None) -> str:
    """调用 LLM 对图谱数据进行总结"""
    settings = get_all_settings()
    endpoint = settings.get("llm_endpoint", "https://api.openai.com/v1").rstrip("/")
    api_key = settings.get("llm_api_key", "")
    model = settings.get("llm_model", "gpt-4o")
    prompt_template = custom_prompt or settings.get("summary_prompt", "")

    graph_data = _format_graph_data(nodes, relationships)
    prompt = _build_prompt(prompt_template, graph_data)

    messages = [
        {"role": "system", "content": "你是一个知识图谱分析专家，擅长从实体关系数据中发现模式和洞察。"},
        {"role": "user", "content": prompt},
    ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{endpoint}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2048,
            },
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
```

- [ ] **Step 3: 修改 models.py 添加分析相关模型**

添加以下类到 `models.py`（在已有 Preset 模型之后、ErrorResponse 之前）：

```python
class AnalyzeRequest(BaseModel):
    nodes: list[dict] = []
    relationships: list[dict] = []
    custom_prompt: str | None = None


class AnalyzeResponse(BaseModel):
    summary: str


class SettingsUpdate(BaseModel):
    settings: dict[str, str]
```

- [ ] **Step 4: 修改 main.py 添加新端点**

在 `from database import conn_manager` 附近添加新 import：
```python
from llm_service import call_llm
from settings_db import init_settings_table, get_all_settings, set_multiple_settings
from models import (
    CypherQuery, GraphResponse, NodeDTO, RelationshipDTO,
    PresetCreate, PresetUpdate, PresetResponse,
    AnalyzeRequest, AnalyzeResponse, SettingsUpdate,
)
```

在 `init_db()` 旁边添加 settings 表初始化（在 Presets API 区域）：
```python
from settings_db import init_settings_table

init_settings_table()
```

在 Presets API 端点之后（或文件末尾 /api/health 之前）添加：

```python
# ─── AI Analyse API ──────────────────────────────────────────────────────────
@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_graph(body: AnalyzeRequest):
    if not body.nodes and not body.relationships:
        raise HTTPException(status_code=400, detail="No graph data to analyze")
    try:
        summary = await call_llm(body.nodes, body.relationships, body.custom_prompt)
        return AnalyzeResponse(summary=summary)
    except Exception as e:
        logger.warning("AI analyse failed: %s", e)
        raise HTTPException(status_code=500, detail=f"AI analyse error: {e}")


# ─── Settings API ────────────────────────────────────────────────────────────
@app.get("/api/settings")
async def list_settings():
    return get_all_settings()


@app.put("/api/settings")
async def update_settings(body: SettingsUpdate):
    set_multiple_settings(body.settings)
    return {"status": "ok"}
```

- [ ] **Step 5: 更新 requirements.txt**

添加 httpx：
```
httpx==0.28.1
```

- [ ] **Step 6: 验证**

重启后端并测试：

```bash
# 验证设置 API
curl -s http://localhost:8000/api/settings

# 更新设置
curl -s -X PUT http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"settings":{"llm_model":"deepseek-chat"}}'

# 验证分析 API (需要 LLM 配置正确)
curl -s -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"nodes":[{"id":"1","labels":["Person"],"properties":{"name":"张三"}}],"relationships":[]}'
```

- [ ] **Step 7: 提交**

```bash
git add backend/settings_db.py backend/llm_service.py backend/models.py backend/main.py backend/requirements.txt
git commit -m "feat: add LLM settings and analyze API"
```

---

### Task 2: 前端 — 设置页 AI 配置卡片 + UI 美化

**Files:**
- Create: `frontend/src/components/AiConfigPanel.vue`
- Modify: `frontend/src/views/SettingsPage.vue`
- Modify: `frontend/src/components/PresetManager.vue`
- Modify: `frontend/src/style.css`

- [ ] **Step 1: 创建 AiConfigPanel.vue**

```vue
<script setup>
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";

const SETTINGS_API = "/api/settings";

const config = ref({
  llm_endpoint: "",
  llm_api_key: "",
  llm_model: "",
  summary_prompt: "",
});
const saving = ref(false);

async function fetchSettings() {
  try {
    const res = await fetch(SETTINGS_API);
    const data = await res.json();
    config.value = {
      llm_endpoint: data.llm_endpoint || "",
      llm_api_key: data.llm_api_key || "",
      llm_model: data.llm_model || "",
      summary_prompt: data.summary_prompt || "",
    };
  } catch {
    ElMessage.error("获取配置失败");
  }
}

async function saveSettings() {
  saving.value = true;
  try {
    await fetch(SETTINGS_API, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings: config.value }),
    });
    ElMessage.success("配置已保存");
  } catch {
    ElMessage.error("保存配置失败");
  } finally {
    saving.value = false;
  }
}

onMounted(fetchSettings);
</script>

<template>
  <div class="ai-config">
    <div class="config-section">
      <h3 class="config-section-title">LLM 连接</h3>
      <el-form label-position="top" size="small">
        <el-form-item label="API 地址">
          <el-input v-model="config.llm_endpoint" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="config.llm_api_key" type="password" show-password placeholder="sk-..." />
        </el-form-item>
        <el-form-item label="模型">
          <el-input v-model="config.llm_model" placeholder="gpt-4o / deepseek-chat" />
        </el-form-item>
      </el-form>
    </div>

    <div class="config-section">
      <h3 class="config-section-title">总结提示词</h3>
      <p class="config-section-desc">
        可用变量：<code>{node_count}</code> <code>{rel_count}</code> <code>{nodes}</code> <code>{rels}</code>
      </p>
      <el-input
        v-model="config.summary_prompt"
        type="textarea"
        :rows="8"
        placeholder="输入总结提示词模板"
      />
    </div>

    <el-button type="primary" :loading="saving" @click="saveSettings" style="margin-top: 16px">
      保存配置
    </el-button>
  </div>
</template>

<style scoped>
.config-section {
  margin-bottom: 20px;
}

.config-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px 0;
}

.config-section-desc {
  font-size: 11px;
  color: var(--text-tertiary);
  margin: -8px 0 10px 0;
}

.config-section-desc code {
  font-size: 11px;
  background: var(--input-bg);
  padding: 1px 5px;
  border-radius: 3px;
}
</style>
```

- [ ] **Step 2: 修改 SettingsPage.vue — 使用 el-card 包裹**

```vue
<script setup>
import PresetManager from "../components/PresetManager.vue";
import AiConfigPanel from "../components/AiConfigPanel.vue";
</script>

<template>
  <div class="settings-page">
    <header class="settings-header">
      <router-link to="/" class="settings-back">← 返回图谱</router-link>
      <h1>系统设置</h1>
    </header>
    <div class="settings-body">
      <el-card class="settings-card">
        <template #header>
          <span>预设问题</span>
        </template>
        <PresetManager />
      </el-card>

      <el-card class="settings-card">
        <template #header>
          <span>AI 配置</span>
        </template>
        <AiConfigPanel />
      </el-card>
    </div>
  </div>
</template>
```

- [ ] **Step 3: 修改 PresetManager.vue — 去掉内边距，表格占满**

移除 PresetManager.vue 中 `<style scoped>` 里的 `.preset-manager-header` 内边距和外边距限制，让表格自然占满 el-card 宽度。修改 css 为：

```css
.preset-manager-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.preset-manager-header h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.no-cypher {
  color: var(--text-muted);
  font-style: italic;
}
```

并移除 `preset-manager` 类上可能限制宽度的样式。

- [ ] **Step 4: 添加设置页卡片样式到 style.css**

在 settings-page 样式区域添加：
```css
.settings-body {
  max-width: 1000px;
  margin: 0 auto;
}

.settings-card {
  margin-bottom: 20px;
}

.settings-card .el-card__header {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  padding: 14px 20px;
}

.settings-card .el-card__body {
  padding: 20px;
}
```

- [ ] **Step 5: 构建验证**

```bash
cd frontend && npx vite build
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/AiConfigPanel.vue frontend/src/views/SettingsPage.vue frontend/src/components/PresetManager.vue frontend/src/style.css
git commit -m "feat: add AI config panel and polish settings page UI"
```

---

### Task 3: 前端 — 图谱主页 AI 总结按钮与结果展示

**Files:**
- Create: `frontend/src/components/AiSummaryPanel.vue`
- Modify: `frontend/src/views/GraphPage.vue`
- Modify: `frontend/src/style.css`

- [ ] **Step 1: 创建 AiSummaryPanel.vue**

```vue
<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  graphData: { type: Object, default: () => ({ nodes: [], relationships: [] }) },
});

const summary = ref("");
const loading = ref(false);
const error = ref("");

// Clear summary when graph data changes
watch(() => props.graphData, () => {
  summary.value = "";
  error.value = "";
}, { deep: true });

async function analyze() {
  if (!props.graphData.nodes.length && !props.graphData.relationships.length) return;

  loading.value = true;
  error.value = "";
  summary.value = "";

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nodes: props.graphData.nodes,
        relationships: props.graphData.relationships,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      error.value = err.detail || "分析失败";
      return;
    }
    const data = await res.json();
    summary.value = data.summary;
  } catch (e) {
    error.value = `网络错误: ${e.message}`;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="ai-summary">
    <el-button
      class="btn-analyze"
      type="primary"
      size="small"
      :disabled="graphData.nodes.length === 0 && graphData.relationships.length === 0"
      :loading="loading"
      @click="analyze"
    >
      {{ loading ? "分析中..." : "AI 总结" }}
    </el-button>

    <div v-if="error" class="ai-summary-error">
      <el-alert :title="error" type="error" show-icon :closable="false" />
    </div>

    <div v-if="summary" class="ai-summary-result">
      <div class="ai-summary-content">{{ summary }}</div>
      <el-button size="small" text @click="summary = ''">收起</el-button>
    </div>
  </div>
</template>

<style scoped>
.ai-summary {
  margin-top: 12px;
}

.btn-analyze {
  width: 100%;
}

.ai-summary-error {
  margin-top: 8px;
}

.ai-summary-result {
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--input-bg);
  border-radius: 8px;
  max-height: 360px;
  overflow-y: auto;
}

.ai-summary-content {
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 8px;
}
</style>
```

- [ ] **Step 2: 修改 GraphPage.vue — 添加 AI 总结区域**

在 `<script setup>` 中添加 import：
```javascript
import AiSummaryPanel from "../components/AiSummaryPanel.vue";
```

在 `<template>` 中 QueryEditor 之后的适当位置（side-scroll 底部）添加：
```html
        <AiSummaryPanel :graph-data="graphData" />
```

完整的侧边栏模板结构变为：
```html
<div class="side-scroll">
  <div class="logo">...</div>
  <div v-if="presets.length > 0" class="preset-list">...</div>
  <QueryEditor ... />
  <AiSummaryPanel :graph-data="graphData" />
</div>
```

- [ ] **Step 3: 构建验证**

```bash
cd frontend && npx vite build
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/AiSummaryPanel.vue frontend/src/views/GraphPage.vue frontend/src/style.css
git commit -m "feat: add AI summary button and result display on graph page"
```

---

### Task 4: 同步 deploy 目录

**Files:**
- Create: `deploy/backend/settings_db.py`
- Create: `deploy/backend/llm_service.py`
- Modify: `deploy/backend/models.py`
- Modify: `deploy/backend/main.py`
- Modify: `deploy/backend/requirements.txt`

与 Task 1 相同的改动，deploy 版本使用 `from backend.xxx` 导入前缀。

- [ ] **Step 1: 复制 settings_db.py**

内容同 `backend/settings_db.py`，无需改导入（无本地模块引用）。

- [ ] **Step 2: 复制 llm_service.py**

将 `from settings_db import get_all_settings` 改为 `from backend.settings_db import get_all_settings`。

- [ ] **Step 3: 修改 deploy/backend/models.py**

添加 AnalyzeRequest, AnalyzeResponse, SettingsUpdate（同 Task 1 Step 3）。

- [ ] **Step 4: 修改 deploy/backend/main.py**

- 更新 imports（`from backend.llm_service import call_llm`，`from backend.settings_db import ...`）
- 添加分析端点和设置端点（同 Task 1 Step 4）

- [ ] **Step 5: 修改 requirements.txt**

添加 `httpx==0.28.1`

- [ ] **Step 6: 提交**

```bash
git add deploy/backend/settings_db.py deploy/backend/llm_service.py deploy/backend/models.py deploy/backend/main.py deploy/backend/requirements.txt
git commit -m "feat: sync AI analyze backend to deploy directory"
```

---

## 验证清单

1. `GET /api/settings` 返回所有 LLM 配置和提示词（含默认值）
2. `PUT /api/settings` 保存配置后再次 GET 确认更新
3. 设置页 AI 配置卡片可填写 endpoint/key/model/提示词并保存
4. 设置页两个 el-card 布局美观，表格占满
5. 图谱主页"AI 总结"按钮在有数据时可点击
6. 点击后加载中状态，完成后显示总结内容
7. 新查询后总结结果自动清空
8. 无数据时按钮置灰
9. 前端构建无错误
