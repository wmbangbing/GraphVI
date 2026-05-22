# 预设问题管理功能设计

## 概述

为知识图谱系统添加预设问题管理功能。预设包含问题文本和关联的 Cypher 查询语句，用户可以选取预设一键执行图谱查询。预设管理作为系统设置的一部分，独立页面维护，未来可扩展其他配置项。

## 架构

```
前端 (Vue Router)                 后端 (FastAPI)
┌──────────────────────┐         ┌──────────────────┐
│  / (图谱主页)         │         │ GET  /api/presets │
│  └─ GraphPage.vue    │ ←────→  │ POST /api/presets │ ←→ SQLite
│  └─ QueryEditor      │         │ PUT  /api/presets │    (presets表)
│                       │         │ DEL  /api/presets│
│  /settings (设置页)   │         └──────────────────┘
│  └─ SettingsPage.vue  │
│     └─ PresetManager  │
└──────────────────────┘
```

## 后端设计

### 数据表 (SQLite)

```sql
CREATE TABLE presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    cypher TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/presets` | 获取所有预设（降序排列） |
| POST | `/api/presets` | 新增预设 `{question, cypher?}` |
| PUT | `/api/presets/{id}` | 更新预设 `{question, cypher?}` |
| DELETE | `/api/presets/{id}` | 删除预设 |

### Pydantic 模型 (`models.py`)

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
    cypher: str | None
    created_at: str
    updated_at: str
```

### SQLite 管理 (`presets_db.py`)

使用 Python 内置 `sqlite3`，数据库文件位于 `backend/presets.db`。
提供 `init_db()`、`get_all()`、`create()`、`update()`、`delete()` 函数。

## 前端设计

### 路由

```
/           → GraphPage.vue    (图谱主页面)
/settings   → SettingsPage.vue  (系统设置页)
```

### 组件结构

```
App.vue (布局壳, <router-view>, 顶部导航)
├── router/index.js (路由配置)
├── views/
│   ├── GraphPage.vue (从原 App.vue 提取)
│   └── SettingsPage.vue (设置页框架)
├── components/
│   ├── QueryEditor.vue (不变)
│   ├── GraphView.vue (不变)
│   ├── StatusBar.vue (不变)
│   └── PresetManager.vue (新建 - 预设管理)
```

### 导航

- **图谱主页**：logo 区右侧增加齿轮图标 ⚙️，点击跳转到 `/settings`
- **设置页**：左上角返回箭头 ←，点击回到图谱主页 `/`
- 未来其他配置项在设置页内以卡片/分栏形式扩展

### PresetManager.vue

- 置于 SettingsPage 内
- **预设列表**：el-table 展示（列：question, cypher, created_at, 操作）
- **新增**：el-button → el-dialog 表单（question 必填 + cypher 选填）
- **编辑**：每行编辑按钮 → el-dialog 预填表单
- **删除**：每行删除按钮 → el-popconfirm 确认
- **测试执行**：有 Cypher 的行可点击"执行"直接调 `/api/query`，结果在设置页内展示

### 预设列表与图谱主页联动

- 图谱主页侧边栏增加预设列表区域（es-srollbar 或 el-collapse）
- 展示预设的问题列表，有 Cypher 的预设可点击直接执行图谱查询
- 无 Cypher 的预设置灰显示，不可点击（为后续 NLP 预留）

## 验证

1. 导航到 `/settings` 能看到预设管理页面
2. 新增预设（含 question + cypher）后列表刷新
3. 编辑预设后数据正确更新
4. 删除预设后列表刷新
5. 图谱主页侧栏能看到预设列表
6. 点击有 Cypher 的预设 → 自动执行查询 → 图谱渲染
7. 无 Cypher 的预设不可点击
