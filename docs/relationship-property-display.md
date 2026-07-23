# 关系属性展示优化备忘录

## 现状

后端已完整提取关系属性（`RelationshipDTO.properties`），前端 `buildFreshData()` 也传递了 `link.properties`，但前端没有任何交互入口查看关系属性。

| 交互功能 | 节点 | 关系边 |
|---|---|---|
| 点击弹出属性面板 | ✅ 已有 | ❌ 无 |
| onClick 处理 | ✅ 已有 | ❌ 无 |
| label 显示 | ✅ name | ✅ type |
| 属性面板渲染 | ✅ 图片/视频/链接/Markdown | ❌ 无 |

## 候选方案

### A. 点击边弹出属性面板

新增 `tooltipLink` ref + `onLinkClick` 回调，复用现有 tooltip 布局渲染关系属性和类型。

- 改动量：`GraphView.vue` 约 30 行
- 依赖：3d-force-graph 已有 `onLinkClick` API

### B. 节点面板中显示关联边

点击节点时，在现有属性表格下方列出该节点参与的所有关系边（类型、目标节点、属性）。

- 改动量：`GraphView.vue` 约 50 行 + 模板扩展

### C. 边上 Label 显示关键属性

利用 `linkLabel` 显示边的关键属性值（如 `amount`, `year` 等）。

- 改动量：`GraphView.vue` 少量代码
