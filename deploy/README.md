# GraphVI — Neo4j 知识图谱可视化查询系统

## 部署包结构

```
graphvi-deploy/
├── backend/
│   ├── main.py              # FastAPI 应用（含前端静态文件服务）
│   ├── database.py           # Neo4j 连接管理器
│   ├── models.py             # 数据模型
│   └── requirements.txt      # Python 依赖
├── frontend/
│   └── dist/                 # 已构建的 Vue 前端静态文件
├── start.sh                  # 启动脚本
└── README.md                 # 本文件
```

## 系统要求

- **Python 3.10+**（后端运行环境）
- **Neo4j 5.x**（图数据库，需提前安装并运行）
- **Linux / macOS**（Windows 也可运行，见下文）

## 部署步骤

### 第 1 步：安装 Python 依赖

```bash
# （推荐）创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r backend/requirements.txt
```

**离线服务器**：在有网络的机器上提前下载，打包后传输：

```bash
# 在第 1 台机器（有网络）上下载
pip download -r backend/requirements.txt -d ./pip-cache
# 将 pip-cache 文件夹和部署包一起传到目标服务器

# 在目标服务器（离线）上安装
pip install --no-index --find-links ./pip-cache -r backend/requirements.txt
```

### 第 2 步：配置 Neo4j

确保 Neo4j 数据库已启动并可访问。连接信息由前端页面输入，默认：

| 参数 | 默认值 |
|---|---|
| URI | `bolt://localhost:7687` |
| Username | `neo4j` |
| Password | `neo4j@openspg` |
| Database | `kmdevelop` |

### 第 3 步：启动系统

```bash
chmod +x start.sh
./start.sh
```

或直接使用 uvicorn：

```bash
cd graphvi-deploy
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 第 4 步：访问系统

打开浏览器访问 `http://<服务器IP>:8000`

## 验证运行

服务启动后，API 健康检查返回：

```json
GET /api/health → {"status":"ok"}
```

## 常见问题

**Q: 前端页面空白 / 404？**  
确认 `frontend/dist/` 目录存在且包含 `index.html`。若丢失，在有网络的开发机上执行 `cd frontend && npm run build` 重新构建。

**Q: 连接 Neo4j 失败？**  
在页面左侧展开"数据库连接"面板，检查 URI/用户名/密码是否正确，点击"测试连接"验证。

**Q: 如何修改服务端口？**  
```bash
./start.sh 8080          # 修改为 8080 端口
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

## Docker 部署（推荐）

### 构建镜像

```bash
cd graphvi-deploy
docker build -t graphvi:latest .
```

### 离线服务器部署

在**有网络的开发机**上构建并导出镜像：

```bash
# 构建镜像
docker build -t graphvi:latest .

# 导出为 tar 文件
docker save -o graphvi-image.tar graphvi:latest
```

将 `graphvi-image.tar` 拷贝到离线服务器，然后加载并运行：

```bash
# 加载镜像
docker load -i graphvi-image.tar

# 运行容器（Neo4j 需在同一网络或可访问地址）
docker run -d \
  --name graphvi \
  --restart unless-stopped \
  -p 8000:8000 \
  graphvi:latest
```

容器启动后访问 `http://<服务器IP>:8000`，在页面左侧配置 Neo4j 连接信息。

## Windows 部署

```bash
# 安装依赖
pip install -r backend/requirements.txt

# 启动（cmd / PowerShell）
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 或使用 conda
conda run -n base uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
