# Neo4j 连接配置迁移到前端设置页

## 概述
将 Neo4j 连接配置从 `backend/.env` 文件迁移到前端系统设置页中管理，配置存储在后端 `settings` 表中。

## 改动

### 后端
- `database.py`: 改为从 `settings_db` 读取 Neo4j 配置，新增 `reconnect()` 方法
- `settings_db.py`: 添加默认配置项（`neo4j_uri`, `neo4j_username`, `neo4j_password`, `neo4j_database`）
- `main.py`: `/api/connect` 接收配置参数 → 测试连接 → 写入 settings → 重建 driver
- `config.py` / `.env`: 不再需要，删除或保留为后备

### 前端
- 设置页 `SettingsPage.vue`: 新增"数据库连接"卡片
- 新组件 `Neo4jConfigPanel.vue`: 配置表单 + 测试连接 + 保存

### 数据流
设置页填写 → 测试连接 → 保存 → 后端写入 settings → 重建 driver → 后续查询用新配置
