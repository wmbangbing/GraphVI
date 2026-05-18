# CLAUDE.md

本文档指导 Claude Code (claude.ai/code) 在本仓库中工作时遵循的规范。

## 沟通规范

使用中文对话，专业术语使用英文（API、library、concept 等）。

## 项目架构

```
graphvi/
├── backend/                    # FastAPI + Neo4j（未修改）
│   ├── main.py                 # API endpoints: POST /api/query, GET /api/health, POST /api/connect
│   ├── database.py             # Neo4j 连接管理器（按配置动态创建）
│   ├── models.py               # Pydantic schemas (CypherQuery, GraphResponse, NodeDTO, RelationshipDTO)
│   ├── .env                    # （不再使用，连接信息由前端传入）
│   └── requirements.txt
├── frontend/                   # Vue 3 + Vite + Element Plus
│   ├── src/
│   │   ├── main.js             # Vue app 入口 + Element Plus 注册
│   │   ├── App.vue             # 根组件：状态管理 + 布局 + 主题切换
│   │   ├── style.css           # 全局样式 + CSS 变量主题系统 (:root / .dark)
│   │   ├── element-theme.css   # Element Plus 主题变量覆盖（亮色/暗色）
│   │   └── components/
│   │       ├── ConnectionConfig.vue    # Neo4j 连接配置面板 (el-collapse + el-input)
│   │       ├── LabelDisplayConfig.vue  # 节点属性显示选择 (el-select)
│   │       ├── QueryEditor.vue         # Cypher 输入 + 执行按钮 (el-input + el-button)
│   │       ├── GraphView.vue           # 2D/3D 力导向图谱 (force-graph / 3d-force-graph)
│   │       └── StatusBar.vue           # 查询状态提示 (el-alert)
│   ├── vite.config.js          # Proxy /api -> localhost:8000
│   └── package.json
└── 系统需求.md                  # 需求文档
```

### 数据流
用户输入 Cypher → `App.vue` POST 到 `/api/query` → `main.py` 在 Neo4j 上执行 → 解析 Node/Relationship 对象 → 返回 `{nodes, relationships}` → `GraphView.vue` 渲染

### Neo4j 连接机制
连接信息不再在后端硬编码，而是**由前端通过 ConnectionConfig 面板输入**，随每个 `/api/query` 请求一起发送（uri, username, password, database）。后端 `Neo4jConnectionManager` 按配置缓存 driver 实例。

### 后端关键点（未修改）
- `database.py`: `Neo4jConnectionManager` 管理动态连接，按 `uri|username|password` 做 key 缓存 driver，pool 10 个连接
- `main.py` `_parse_graph_data()`: 递归遍历 Neo4j Record 值，提取 Node/Relationship 对象。必须用 `async for record in result`（不用 `result.data()`）以保留 Neo4j 类型
- `models.py`: `NodeDTO` (id, labels, properties, caption), `RelationshipDTO` (id, type, source, target, properties), `GraphResponse`

### 前端关键点
- `App.vue` 持有全部状态：`graphData`, `loading`, `status`, `config`, `labelProps`, `isDark`。子组件均为展示型
- **主题系统**：CSS 变量 (`:root` / `.dark`) + Element Plus dark class 切换，localStorage 持久化。画布背景和节点标签颜色跟随主题
- **Element Plus**：所有表单组件使用 Element Plus（el-input, el-select, el-button, el-collapse, el-alert），通过 `element-theme.css` 覆盖主题变量匹配暗色/亮色风格
- **GraphView.vue** 管理 2D/3D 实例：
  - 使用 `force-graph` (2D Canvas) 和 `3d-force-graph` (3D WebGL)
  - 2D/3D 切换时销毁当前实例并创建另一个
  - 数据隔离：`buildFreshData()` 每次创建新对象防止 d3 mutation 泄漏
- **3D 高亮系统**：
  - `nodeObjects3D` Map 追踪所有 Three.js 节点对象
  - `refresh3DHighlights()` 动态更新材质（hover 白色发光 + 光环圈，dimmed 变暗）
  - `UnrealBloomPass` 后期处理（threshold 0.9，仅白色 hover 元素 bloom）
  - 3D 节点名称通过 `three-spritetext` 的 `SpriteText` 显示，N 按钮切换
- **2D 渲染**：
  - `nodeCanvasObject` 每帧重绘，支持 hover 高亮（悬停节点 + 关联节点亮，其余变暗）
  - 三种布局模式：compact（紧密）/ default / spread（松散）
  - 节点显示属性选择（LabelDisplayConfig 浮动面板，P 按钮切换）
- **节点搜索**：S 按钮弹出搜索栏，`el-input` 实时过滤节点名，点击结果调用 `focusNode()`（2D: centerAt+zoom, 3D: cameraPosition）
- **属性面板**（tooltip）：
  - 悬停/点击节点显示，持久化（鼠标离开不隐藏）
  - 左上角定位，Vue 模板渲染（非 innerHTML）
  - ✕ 按钮关闭，点击空白区域关闭
  - 属性值智能渲染：图片 URL→`<img>`，视频 URL→`<video controls>`，Markdown 格式兼容
- **Hover 高亮 bug 修复**：`graphData()` 调用前清空 `hoveredNode`/`highlightNodes`，避免 force-graph 内部 800ms 阴影画布节流导致 `onNodeHover(null)` 不触发
- **首次渲染偏右修复**：创建实例后显式设置 `graphInstance.width(containerWidth)` / `height()`
- **zoomToFit 优化**：通过 `onEngineStop` 回调触发，布局稳定后自动适配
- **Glow sprite** 通过 Three.js `CanvasTexture` + `AdditiveBlending` 创建，Canvas 渐变纹理

## 常用命令

### 本地开发启动

**后端**（conda base 环境）：
```bash
# 安装
pip install -r backend/requirements.txt

# 启动（--reload 自动重启）
export PATH="/d/ProgramData/miniconda3:/d/ProgramData/miniconda3/Scripts:$PATH"
cd D:/project/sjzl/graphvi/backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**前端**（Vite）：
```bash
cd D:/project/sjzl/graphvi/frontend
npx vite --host 0.0.0.0 --port 5173
```

### 生产构建
```bash
cd frontend && npm run build
```
