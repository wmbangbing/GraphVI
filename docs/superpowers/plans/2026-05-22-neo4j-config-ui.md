# Neo4j 配置迁移到前端设置页 Implementation Plan

**Goal:** Neo4j 连接配置从前端设置页管理，存入后端 settings 表，保存即重连

**Architecture:** 设置页新增数据库配置卡片 → 测试连接 → 保存到 settings 表 → database.py 从 settings 读取并重建 driver

---

### Task 1: 后端 — database.py 改从 settings 表读配置 + reconnect

**Files:**
- Modify: `backend/settings_db.py` (添加默认 neo4j 配置)
- Modify: `backend/database.py` (read from settings, add reconnect)
- Modify: `backend/main.py` (connect endpoint uses settings)

### Task 2: 前端 — Neo4jConfigPanel + 设置页卡片

**Files:**
- Create: `frontend/src/components/Neo4jConfigPanel.vue`
- Modify: `frontend/src/views/SettingsPage.vue`

### Task 3: 同步 deploy 目录
