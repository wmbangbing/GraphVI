# GraphVI Docker 构建指南

## 前置条件

- **Docker Desktop**（Windows）或 Docker Engine（Linux）
- **Node.js**（构建前端 dist）
- **Python 3.10+**（开发环境）

## 构建步骤

### 1. 构建前端

```bash
cd frontend
npx vite build
```

产物：`frontend/dist/`
同步到 deploy：`cp -r frontend/dist deploy/frontend/dist`

### 2. 检查 deploy 代码

> **重要**：Docker 运行路径为 `uvicorn backend.main:app`，模块路径带 `backend.` 前缀。
> 所有对项目内部模块的 import 必须使用 `backend.` 前缀。

**需要添加 `backend.` 前缀的 import：**

| 文件 | import 写法 |
|---|---|
| `main.py` | `from backend.database import ...` |
| `main.py` | `from backend.models import ...` |
| `main.py` | `from backend.settings_db import ...` |
| `main.py` | `from backend.presets_db import ...` |
| `main.py` | `from backend.history_db import ...` |
| `main.py` | `from backend.llm_service import ...` |
| `main.py` | `from backend.nl2cypher import ...` |
| `main.py` | `from backend.semantic_search import ...` |
| `llm_service.py` | `from backend.settings_db import ...` |
| `semantic_search.py` | `from backend.settings_db import ...` |
| `semantic_search.py` | `from backend.database import ...` |
| `semantic_search.py` | `from backend.models import ...` |
| `semantic_search.py` | `from backend.nl2cypher import ...` |
| `auto_analyzer.py` | `from backend.cache import ...` |
| `auto_analyzer.py` | `from backend.models import ...` |
| `auto_analyzer.py` | `from backend.settings_db import ...` |
| `strategy_selector.py` | `from backend.settings_db import ...` |
| `strategy_selector.py` | `from backend.models import ...` |
| `stats_engine.py` | `from backend.models import ...` |
| `stats_engine.py` | `from backend.llm_service import ...` |
| `tree_builder.py` | `from backend.utils import ...` |
| `nl2cypher.py` | `from backend.settings_db import ...` |
| `database.py` | `from backend.settings_db import ...` |

> **注意**：`backend/` 目录下的源文件保持**不带** `backend.` 前缀（本地开发从 `backend/` 目录启动）。
> 修改 `deploy/` 目录的文件，不要改源文件。

### 3. 构建 Docker 镜像

```bash
# 在项目根目录执行
docker build -f deploy/Dockerfile -t graphvi:latest .
```

Dockerfile 路径：`deploy/Dockerfile`

```
FROM python:3.12-slim
WORKDIR /app
COPY deploy/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY deploy/backend/ backend/
COPY frontend/dist/ frontend/dist/
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4. 导出离线包

```bash
# 导出为 tar 文件
docker save -o graphvi-image.tar graphvi:latest
```

产物：`graphvi-image.tar`（约 493MB）

### 5. 启动容器

```bash
# 使用挂载 presets.db（推荐）
docker run -d \
  --name graphvi \
  --restart unless-stopped \
  -p 8000:8000 \
  -e GRAPHVI_DB_PATH=/data/presets.db \
  -v /absolute/path/to/deploy/data:/data \
  graphvi:latest
```

> **Windows 路径格式**：使用 PowerShell 执行，挂载路径用绝对路径格式：
> ```powershell
> docker run -v "D:\project\graphvi\deploy\data:/data" ...
> ```
> Git Bash 中需要 `MSYS_NO_PATHCONV=1` 前缀或使用 PowerShell。

## 离线服务器部署

```bash
# 1. 加载镜像
docker load -i graphvi-image.tar

# 2. 运行容器
docker run -d \
  --name graphvi \
  --restart unless-stopped \
  -p 8000:8000 \
  -e GRAPHVI_DB_PATH=/data/presets.db \
  -v /path/to/data:/data \
  graphvi:latest

# 3. 验证
curl http://<服务器IP>:8000/api/health
# → {"status":"ok"}
```

容器启动后访问 `http://<服务器IP>:8000`，在页面左侧配置 Neo4j 连接信息。

## 常见问题

### ModuleNotFoundError: No module named 'xxx'

**原因**：`deploy/` 下的文件 import 缺少 `backend.` 前缀。
**修复**：在 `deploy/` 文件中，`from xxx import ...` 改为 `from backend.xxx import ...`。

### presets.db 数据不显示

**原因**：`GRAPHVI_DB_PATH` 环境变量未设置，或 volume 挂载路径不正确。
**修复**：启动时加 `-e GRAPHVI_DB_PATH=/data/presets.db -v <本地data目录>:/data`。

### Windows 下 volume 挂载不生效

**原因**：Git Bash 的 MSYS2 路径转换导致路径格式错误。
**解决**：使用 PowerShell 执行 `docker run`，或加 `MSYS_NO_PATHCONV=1` 前缀。
