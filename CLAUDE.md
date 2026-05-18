# CLAUDE.md

本文档指导 Claude Code (claude.ai/code) 在本仓库中工作时遵循的规范。

## 沟通规范

使用中文对话，专业术语使用英文（API、library、concept 等）。

## 项目架构

```
graphvi/
├── backend/                    # FastAPI + Neo4j
│   ├── main.py                 # API endpoints: POST /api/query, GET /api/health, POST /api/connect
│   ├── database.py             # Neo4j 连接管理器（按配置动态创建）
│   ├── models.py               # Pydantic schemas (CypherQuery, GraphResponse, NodeDTO, RelationshipDTO)
│   ├── .env                    # （不再使用，连接信息由前端传入）
│   └── requirements.txt
├── frontend/                   # Vue 3 + Vite
│   ├── src/
│   │   ├── main.js             # Vue app 入口
│   │   ├── App.vue             # 根组件：状态管理 + 布局（侧栏 | 图谱）
│   │   ├── style.css           # 全局暗色主题
│   │   └── components/
│   │       ├── ConnectionConfig.vue  # Neo4j 连接配置面板
│   │       ├── LabelDisplayConfig.vue # 节点属性显示选择
│   │       ├── QueryEditor.vue       # Cypher 输入 + 执行/清空按钮
│   │       ├── GraphView.vue         # 2D/3D 力导向图谱 (force-graph / 3d-force-graph)
│   │       └── StatusBar.vue         # 查询状态 + 节点/关系计数
│   ├── vite.config.js          # Proxy /api -> localhost:8000
│   └── package.json
└── 系统需求.md                  # 需求文档
```

### 数据流
用户输入 Cypher → `App.vue` POST 到 `/api/query` → `main.py` 在 Neo4j 上执行 → 解析 Node/Relationship 对象 → 返回 `{nodes, relationships}` → `GraphView.vue` 渲染

### Neo4j 连接机制
连接信息不再在后端硬编码，而是**由前端通过 ConnectionConfig 面板输入**，随每个 `/api/query` 请求一起发送（uri, username, password, database）。后端 `Neo4jConnectionManager` 按配置缓存 driver 实例。

### 后端关键点
- `database.py`: `Neo4jConnectionManager` 管理动态连接，按 `uri|username|password` 做 key 缓存 driver，pool 10 个连接
- `main.py` `_parse_graph_data()`: 递归遍历 Neo4j Record 值，提取 Node/Relationship 对象。必须用 `async for record in result`（不用 `result.data()`）以保留 Neo4j 类型
- `models.py`: `NodeDTO` (id, labels, properties, caption), `RelationshipDTO` (id, type, source, target, properties), `GraphResponse`

### 前端关键点
- `App.vue` 持有全部状态：`graphData`, `loading`, `status`, `config`, `labelProps`。子组件均为展示型
- `GraphView.vue` 管理自己的 2D/3D 实例。使用 `force-graph` (2D Canvas) 和 `3d-force-graph` (3D WebGL) + `<div class="graph-wrapper">` 隔离挂载点防止 Vue DOM 冲突
- 2D/3D 切换时销毁当前实例并创建另一个
- Glow sprite 通过 Three.js `CanvasTexture` + `AdditiveBlending` 创建
- Hover 高亮通过 `linkColor` 覆盖赋值来变暗非关联节点/边
- 2D 场景下支持节点显示属性选择（LabelDisplayConfig）+ 三种布局切换（compact/default/spread）
- 连接配置面板（ConnectionConfig）可展开折叠，支持"测试连接"

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
