# 预设问题管理功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 添加预设问题管理功能，支持后端 CRUD、前端独立设置页管理、图谱主页快捷选择执行

**Architecture:** 后端使用 Python 内置 sqlite3 存储预设数据，提供 RESTful CRUD API；前端使用 Vue Router 实现 `/` 图谱主页和 `/settings` 设置页路由，`PresetManager.vue` 在设置页中管理预设，图谱主页侧边栏展示预设列表供快速执行

**Tech Stack:** Python sqlite3, FastAPI, Vue Router, Element Plus

---

### Task 1: 后端 SQLite 数据库 + Pydantic 模型 + CRUD API

**Files:**
- Create: `backend/presets_db.py`
- Modify: `backend/models.py`
- Modify: `backend/main.py`
- Create: `docs/curl-test.sh`

- [ ] **Step 1: 创建 presets_db.py — SQLite 数据管理**

```python
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "presets.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            cypher TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def get_all():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM presets ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create(question: str, cypher: str | None = None):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO presets (question, cypher) VALUES (?, ?)",
        (question, cypher),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM presets WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)


def update(preset_id: int, question: str | None = None, cypher: str | None = None):
    conn = get_connection()
    fields = []
    values = []
    if question is not None:
        fields.append("question = ?")
        values.append(question)
    if cypher is not None:
        fields.append("cypher = ?")
        values.append(cypher)
    if fields:
        fields.append("updated_at = datetime('now')")
        values.append(preset_id)
        conn.execute(
            f"UPDATE presets SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
    row = conn.execute("SELECT * FROM presets WHERE id = ?", (preset_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete(preset_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
    conn.commit()
    conn.close()
```

- [ ] **Step 2: 修改 models.py — 添加 Preset Pydantic 模型**

```python
class PresetCreate(BaseModel):
    question: str
    cypher: str | None = None


class PresetUpdate(BaseModel):
    question: str | None = None
    cypher: str | None = None


class PresetResponse(BaseModel):
    id: int
    question: str
    cypher: str | None = None
    created_at: str
    updated_at: str
```

添加到文件末尾已有的 `ErrorResponse` 之前。

- [ ] **Step 3: 修改 main.py — 添加预设 API 路由**

在 `app` 定义之后、端点定义之前添加 `init_db()` 初始化（在 lifespan 中或模块级别）：

在 `@asynccontextmanager async def lifespan` 中，`yield` 之前添加：
```python
from presets_db import init_db, get_all, create, update, delete as delete_preset
```
(放在文件顶部现有 import 之后)

然后在 `_parse_graph_data` 之后、`@app.post("/api/query")` 之前添加：

```python
# ─── Presets API ─────────────────────────────────────────────────────────────
from presets_db import init_db, get_all, create, update as update_preset, delete as delete_preset

init_db()


@app.get("/api/presets", response_model=list[PresetResponse])
async def list_presets():
    return get_all()


@app.post("/api/presets", response_model=PresetResponse, status_code=201)
async def create_preset(body: PresetCreate):
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    return create(body.question.strip(), body.cypher)


@app.put("/api/presets/{preset_id}", response_model=PresetResponse)
async def update_preset_endpoint(preset_id: int, body: PresetUpdate):
    result = update_preset(preset_id, body.question, body.cypher)
    if not result:
        raise HTTPException(status_code=404, detail="Preset not found")
    return result


@app.delete("/api/presets/{preset_id}", status_code=204)
async def delete_preset_endpoint(preset_id: int):
    delete_preset(preset_id)
```

同时添加对应的 import：
```python
from models import CypherQuery, GraphResponse, NodeDTO, RelationshipDTO, PresetCreate, PresetUpdate, PresetResponse
```

- [ ] **Step 4: 验证后端 API**

重启后端，执行 curl 测试：

```bash
# 新增预设
curl -s -X POST http://localhost:8000/api/presets \
  -H "Content-Type: application/json" \
  -d '{"question":"查看所有实体关系","cypher":"MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 50"}'

# 获取预设列表
curl -s http://localhost:8000/api/presets

# 更新预设
curl -s -X PUT http://localhost:8000/api/presets/1 \
  -H "Content-Type: application/json" \
  -d '{"question":"查看所有实体关系(已更新)"}'

# 删除预设
curl -s -X DELETE http://localhost:8000/api/presets/1
```

- [ ] **Step 5: 提交后端改动**

```bash
git add backend/presets_db.py backend/models.py backend/main.py
git commit -m "feat: add preset questions backend with SQLite CRUD API"
```

---

### Task 2: 前端路由重构 — vue-router + App.vue 改造

**Files:**
- Modify: `package.json` (已存在，需安装依赖)
- Create: `frontend/src/router/index.js`
- Modify: `frontend/src/main.js`
- Create: `frontend/src/views/GraphPage.vue`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: 安装 vue-router**

```bash
cd frontend && npm install vue-router
```

- [ ] **Step 2: 创建 router/index.js**

```javascript
import { createRouter, createWebHistory } from "vue-router";
import GraphPage from "../views/GraphPage.vue";
import SettingsPage from "../views/SettingsPage.vue";

const routes = [
  {
    path: "/",
    name: "graph",
    component: GraphPage,
  },
  {
    path: "/settings",
    name: "settings",
    component: SettingsPage,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
```

- [ ] **Step 3: 修改 main.js — 注册 Router**

```javascript
import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import "element-plus/theme-chalk/dark/css-vars.css";
import "./style.css";
import "./element-theme.css";
import App from "./App.vue";
import router from "./router";

const app = createApp(App);
app.use(ElementPlus);
app.use(router);
app.mount("#app");
```

- [ ] **Step 4: 创建 GraphPage.vue**

从当前 `App.vue` 完整提取图谱主页内容（包含所有状态管理、executeQuery、模板中的侧边栏和 GraphView）。GraphPage.vue 内容与原 App.vue 相同，只是删除 `ConnectionConfig` 相关代码（已删）。

```vue
<script setup>
import { ref, reactive, watch } from "vue";
import QueryEditor from "../components/QueryEditor.vue";
import GraphView from "../components/GraphView.vue";
import StatusBar from "../components/StatusBar.vue";

const isDark = ref(localStorage.getItem("theme") !== "light");
document.documentElement.classList.toggle("dark", isDark.value);

function toggleTheme() {
  isDark.value = !isDark.value;
  document.documentElement.classList.toggle("dark", isDark.value);
  localStorage.setItem("theme", isDark.value ? "dark" : "light");
}

const API_BASE = "/api/query";

const graphData = ref({ nodes: [], relationships: [] });
const loading = ref(false);
const status = reactive({ type: "info", message: "" });
const labelProps = ref({});

watch(
  () => graphData.value.nodes,
  (nodes) => {
    const defaults = { ...labelProps.value };
    let changed = false;
    nodes.forEach((n) => {
      const label = (n.labels?.length > 1 ? n.labels.find(l => l !== "Entity") : null) || n.labels?.[0] || "Node";
      if (!label || defaults[label]) return;
      const keys = Object.keys(n.properties || {});
      const preferred = keys.find((k) => k === "name" || k === "title");
      defaults[label] = preferred || keys[0] || "";
      changed = true;
    });
    if (changed) labelProps.value = defaults;
  }
);

async function executeQuery(cypher) {
  loading.value = true;
  status.type = "info";
  status.message = "查询执行中...";
  try {
    const res = await fetch(API_BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cypher }),
    });
    if (!res.ok) {
      const err = await res.json();
      status.type = "error";
      status.message = err.detail || `请求失败 (${res.status})`;
      graphData.value = { nodes: [], relationships: [] };
      return;
    }
    const data = await res.json();
    if (data.nodes.length === 0 && data.relationships.length === 0) {
      status.type = "info";
      status.message = "查询成功，但未找到匹配的图谱数据";
    } else {
      status.type = "success";
      status.message = `查询成功`;
    }
    graphData.value = { nodes: data.nodes, relationships: data.relationships };
  } catch (e) {
    status.type = "error";
    status.message = `网络错误: ${e.message}`;
    graphData.value = { nodes: [], relationships: [] };
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="app">
    <div class="side-panel">
      <div class="side-scroll">
        <div class="logo">
          <span class="logo-text">Graph<span>VI</span></span>
          <div class="logo-actions">
            <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '切换亮色主题' : '切换暗色主题'">
              {{ isDark ? "☀️" : "🌙" }}
            </button>
            <router-link to="/settings" class="settings-link" title="系统设置">
              ⚙️
            </router-link>
          </div>
        </div>
        <!-- Preset quick list (Task 4 will add here) -->
        <QueryEditor :loading="loading" @execute="executeQuery" />
      </div>
      <StatusBar
        :status="status"
        :nodes="graphData.nodes.length"
        :relationships="graphData.relationships.length"
      />
    </div>
    <GraphView
      :nodes="graphData.nodes"
      :relationships="graphData.relationships"
      :label-props="labelProps"
      :dark="isDark"
      @update:label-props="labelProps = $event"
    />
  </div>
</template>
```

注意：logo 区增加了 `logo-actions` 包裹 theme-toggle 和 settings-link，需要对应 CSS 样式。

- [ ] **Step 5: 重写 App.vue — 简化为布局壳**

```vue
<script setup>
import { watch } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

// Sync theme class on route changes (theme stored in localStorage)
const isDark = localStorage.getItem("theme") !== "light";
document.documentElement.classList.toggle("dark", isDark);

router.afterEach(() => {
  const dark = localStorage.getItem("theme") !== "light";
  document.documentElement.classList.toggle("dark", dark);
});
</script>

<template>
  <router-view />
</template>
```

- [ ] **Step 6: 修改 style.css — 添加 logo-actions 样式**

在 logo 相关样式后添加：
```css
.logo-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.settings-link {
  text-decoration: none;
  font-size: 16px;
  opacity: 0.5;
  transition: opacity 0.15s;
  line-height: 1;
}

.settings-link:hover {
  opacity: 1;
}
```

- [ ] **Step 7: 验证路由**

```bash
cd frontend && npx vite build
```
确认构建无错误。访问 `http://localhost:5173/` 应正常显示图谱主页，访问 `http://localhost:5173/settings` 应显示设置页（目前空白）。

- [ ] **Step 8: 提交**

```bash
git add frontend/src/router/ frontend/src/views/ frontend/src/main.js frontend/src/App.vue frontend/package.json frontend/package-lock.json frontend/src/style.css
git commit -m "feat: add vue-router, graph page, and settings page shell"
```

---

### Task 3: PresetManager.vue — 设置页预设管理

**Files:**
- Create: `frontend/src/views/SettingsPage.vue`
- Create: `frontend/src/components/PresetManager.vue`
- Modify: `frontend/src/style.css` (添加设置页样式)

- [ ] **Step 1: 创建 SettingsPage.vue**

```vue
<script setup>
import PresetManager from "../components/PresetManager.vue";
</script>

<template>
  <div class="settings-page">
    <header class="settings-header">
      <router-link to="/" class="settings-back">← 返回图谱</router-link>
      <h1>系统设置</h1>
    </header>
    <div class="settings-body">
      <PresetManager />
    </div>
  </div>
</template>
```

- [ ] **Step 2: 创建 PresetManager.vue**

完整功能：el-table 展示预设列表，新增/编辑使用 el-dialog，删除使用 el-popconfirm，有 Cypher 的行可点击执行测试。

```vue
<script setup>
import { ref, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

const API_BASE = "/api/presets";

const presets = ref([]);
const dialogVisible = ref(false);
const dialogTitle = ref("");
const form = ref({ question: "", cypher: "" });
const editingId = ref(null);
const loading = ref(false);

async function fetchPresets() {
  try {
    const res = await fetch(API_BASE);
    presets.value = await res.json();
  } catch {
    ElMessage.error("获取预设列表失败");
  }
}

function openCreate() {
  dialogTitle.value = "新增预设";
  editingId.value = null;
  form.value = { question: "", cypher: "" };
  dialogVisible.value = true;
}

function openEdit(preset) {
  dialogTitle.value = "编辑预设";
  editingId.value = preset.id;
  form.value = { question: preset.question, cypher: preset.cypher || "" };
  dialogVisible.value = true;
}

async function handleSave() {
  if (!form.value.question.trim()) {
    ElMessage.warning("请输入问题");
    return;
  }
  try {
    if (editingId.value) {
      await fetch(`${API_BASE}/${editingId.value}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: form.value.question,
          cypher: form.value.cypher || null,
        }),
      });
      ElMessage.success("更新成功");
    } else {
      await fetch(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: form.value.question,
          cypher: form.value.cypher || null,
        }),
      });
      ElMessage.success("新增成功");
    }
    dialogVisible.value = false;
    await fetchPresets();
  } catch {
    ElMessage.error("保存失败");
  }
}

async function handleDelete(preset) {
  try {
    await fetch(`${API_BASE}/${preset.id}`, { method: "DELETE" });
    ElMessage.success("删除成功");
    await fetchPresets();
  } catch {
    ElMessage.error("删除失败");
  }
}

async function testExecute(preset) {
  if (!preset.cypher) return;
  loading.value = true;
  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cypher: preset.cypher }),
    });
    if (res.ok) {
      ElMessage.success("查询执行成功");
    } else {
      const err = await res.json();
      ElMessage.error(err.detail || "查询失败");
    }
  } catch (e) {
    ElMessage.error(`网络错误: ${e.message}`);
  } finally {
    loading.value = false;
  }
}

onMounted(fetchPresets);
</script>

<template>
  <div class="preset-manager">
    <div class="preset-manager-header">
      <h2>预设问题</h2>
      <el-button type="primary" size="small" @click="openCreate">新增预设</el-button>
    </div>

    <el-table :data="presets" stripe style="width: 100%" size="small">
      <el-table-column prop="question" label="问题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="cypher" label="Cypher 语句" min-width="250" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="{ 'no-cypher': !row.cypher }">{{ row.cypher || "（无语句）" }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm title="确定删除该预设？" @confirm="handleDelete(row)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
          <el-button
            size="small"
            type="primary"
            :disabled="!row.cypher"
            :loading="loading"
            @click="testExecute(row)"
          >执行</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" label-position="top">
        <el-form-item label="问题（必填）" required>
          <el-input v-model="form.question" placeholder="输入问题文本" />
        </el-form-item>
        <el-form-item label="Cypher 语句（选填）">
          <el-input
            v-model="form.cypher"
            type="textarea"
            :rows="4"
            placeholder="输入关联的 Cypher 查询语句"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
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

.cypher-preview {
  font-size: 11px;
  color: var(--text-tertiary);
  background: var(--input-bg);
  padding: 2px 6px;
  border-radius: 3px;
}
</style>
```

注意：有两个重复的 el-table，我只应该保留一个。让我修正这个设计：

修正：PresetManager.vue 只有一个 el-table，列合并为 question, cypher, created_at, 操作。

- [ ] **Step 3: 添加设置页样式到 style.css**

```css
/* --- Settings Page --- */
.settings-page {
  min-height: 100vh;
  background: var(--app-bg);
  padding: 24px 32px;
}

.settings-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--panel-border);
}

.settings-header h1 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.settings-back {
  font-size: 14px;
  color: var(--text-secondary);
  text-decoration: none;
  padding: 6px 12px;
  border-radius: 6px;
  transition: background 0.15s;
}

.settings-back:hover {
  background: var(--ctrl-hover-bg);
  color: var(--ctrl-hover-color);
}

.settings-body {
  max-width: 960px;
}
```

- [ ] **Step 4: 构建验证**

```bash
cd frontend && npx vite build
```
确认无错误。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/SettingsPage.vue frontend/src/components/PresetManager.vue frontend/src/style.css
git commit -m "feat: add PresetManager with CRUD in settings page"
```

---

### Task 4: 图谱主页侧边栏预设快捷列表

**Files:**
- Modify: `frontend/src/views/GraphPage.vue`

在 GraphPage.vue 的 logo 和 QueryEditor 之间插入预设快捷列表。

- [ ] **Step 1: 在 GraphPage.vue 中添加预设列表**

在 `<script setup>` 中添加：
```javascript
import { ref, onMounted } from "vue";

const presets = ref([]);

async function fetchPresets() {
  try {
    const res = await fetch("/api/presets");
    presets.value = await res.json();
  } catch {}
}

function executePreset(preset) {
  if (!preset.cypher) return;
  executeQuery(preset.cypher);
}

onMounted(fetchPresets);
```

在 `<template>` 中 logo 之后、QueryEditor 之前添加：
```html
<div v-if="presets.length > 0" class="preset-list">
  <div class="preset-list-header">预设问题</div>
  <div
    v-for="p in presets"
    :key="p.id"
    class="preset-item"
    :class="{ disabled: !p.cypher }"
    :title="p.cypher || '暂无可执行的查询语句'"
    @click="executePreset(p)"
  >
    <span class="preset-question">{{ p.question }}</span>
    <span v-if="!p.cypher" class="preset-badge">待配置</span>
  </div>
</div>
```

- [ ] **Step 2: 添加预设列表样式到 style.css**

```css
/* --- Preset Quick List --- */
.preset-list {
  margin-top: 4px;
  margin-bottom: 8px;
}

.preset-list-header {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
}

.preset-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s;
  gap: 8px;
}

.preset-item:hover:not(.disabled) {
  background: var(--ctrl-hover-bg);
}

.preset-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.preset-question {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.preset-item:not(.disabled):hover .preset-question {
  color: var(--ctrl-hover-color);
}

.preset-badge {
  font-size: 10px;
  color: var(--text-muted);
  background: var(--input-bg);
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}
```

- [ ] **Step 3: 构建验证**

```bash
cd frontend && npx vite build
```
确认无错误。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/GraphPage.vue frontend/src/style.css
git commit -m "feat: add preset quick list to graph page sidebar"
```

---

### Task 5: 同步 deploy 目录（Docker 部署）

**Files:**
- Create: `deploy/backend/presets_db.py`
- Modify: `deploy/backend/models.py`
- Modify: `deploy/backend/main.py`

与 Task 1 相同的改动，但 deploy 版本使用 `from backend.xxx` 导入前缀。

- [ ] **Step 1: 复制/创建 deploy/backend/presets_db.py**（内容同 backend/presets_db.py，不需要改导入）

- [ ] **Step 2: 修改 deploy/backend/models.py**（添加 PresetCreate, PresetUpdate, PresetResponse，同 Task 1 Step 2）

- [ ] **Step 3: 修改 deploy/backend/main.py**（添加 import + 路由）

import 使用 `from backend.presets_db import ...` 前缀：
```python
from backend.presets_db import init_db, get_all, create, update as update_preset, delete as delete_preset
init_db()
```
路由代码与 Task 1 Step 3 相同。

- [ ] **Step 4: 提交**

```bash
git add deploy/backend/presets_db.py deploy/backend/models.py deploy/backend/main.py
git commit -m "feat: sync preset backend to deploy directory"
```

---

## 验证清单

完成后完整验证：

1. `http://localhost:5173/` — 图谱主页正常显示，logo 区有 ⚙️ 设置入口
2. 点击 ⚙️ → 跳转到 `/settings`，显示"系统设置"页面
3. 设置页预设列表为空，点击"新增预设"弹出对话框
4. 新增预设（填写 question + cypher）→ 列表刷新显示新条目
5. 编辑预设 → 数据更新
6. 删除预设 → 确认后消失
7. 点击有 Cypher 预设的"执行"按钮 → 查询成功提示
8. 返回图谱主页 → 侧边栏显示预设列表
9. 点击有 Cypher 的预设 → 自动执行 → 图谱渲染
10. 无 Cypher 的预设置灰不可点击
11. 构建无错误
