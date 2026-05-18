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

## 踩坑记录

### Docker 部署：Import 路径错误
**症状**：`ModuleNotFoundError: No module named 'database'`
**原因**：Docker 中 `CMD` 为 `uvicorn backend.main:app`，Python 运行在 `/app` 目录，模块路径为 `backend.main`。但 `main.py` 中写的是 `from database import ...`（无 `backend.` 前缀）。
**修复**：`deploy/backend/main.py` 使用 `from backend.database import conn_manager`，源文件 `backend/main.py` 保持 `from database import ...`（本地开发从 `backend/` 目录启动）。
**注意**：修改 `deploy/` 目录的文件，不要改源文件。Docker 构建用 `deploy/` 下的代码。

### Docker 部署：前端 404 Not Found
**症状**：访问容器根路径 `/` 返回 404，API 路由正常。
**原因**：`main.py` 缺少静态文件挂载代码 —— 没有 `app.mount("/", StaticFiles(...))`。
**修复**：在 `main.py` 末尾 API 路由之后添加：
```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

dist_path = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="frontend")
```
**注意**：API 路由必须在静态文件挂载之前定义（FastAPI 路由优先匹配）。

### 后端查询返回空关系
**症状**：查询到数据但返回的 `relationships` 为空数组。
**原因**：使用了 `result.data()` 将 Record 转为 dict，导致 Neo4j Node/Relationship 类型信息丢失，`_parse_graph_data()` 无法识别。
**修复**：用 `[record async for record in result]` 保留 Neo4j 类型对象。

### 3D 节点渲染异常（只渲染一个节点）
**原因**：`highlightLinks` 中 `link.source`/`link.target` 在 force-graph 内部被替换为 node 对象引用，与 `graphData()` 后新创建的节点对象引用不匹配。
**修复**：所有高亮比较改用 string ID（`isLinkHovered()` 函数用 `l.source.id`/`l.target.id` 对比 `hoveredNode.value.id`），移除 `highlightLinks` Set。

### 2D 高亮失效
**症状**：操作一段时间后 hover 高亮卡死，不消失或不刷新。
**根因**：`graphData()` 后 force-graph 内部不清除 `state.hoverObj`，且 shadow canvas 有 800ms 节流，加上颜色注册表索引碰撞，导致 `onNodeHover(null)` 不被触发。
**修复**：在 watch 回调中 `graphData()` 前主动 `hoveredNode.value = null; highlightNodes.clear(); hideTooltip();`。

### 首次渲染图谱偏右
**症状**：首次加载图谱偏右，全屏后再退出恢复正常。
**根因**：force-graph 创建 WebGL/Canvas 渲染器时读取 wrapper 的 `clientWidth`，首次挂载时 flex 布局未完成计算，宽度为 0 或偏小，导致 `zoomToFit` 计算偏移。
**修复**：创建实例后显式 `graphInstance.width(containerRef.clientWidth).height(containerRef.clientHeight)`。

### Element Plus 样式不生效
**症状**：Element Plus 组件渲染无样式。
**原因**：只导入了 `element-plus/theme-chalk/dark/css-vars.css`，缺少基础样式 `element-plus/dist/index.css`。
**修复**：`main.js` 中先导入 `element-plus/dist/index.css`，再导入 dark 变量和自定义覆盖。
