# Schema 配置功能设计

## 目标
用户可以在设置页选择需要的节点类型和关系类型，`_get_schema` 只返回勾选的类型，减少 LLM 提示词大小。

## 存储

settings_db 新增 key `schema_include`，value 为 JSON 字符串：

```json
{"node_types": ["dm_event_info", "dm_dispatch_apply"], "rel_types": ["EVENT_TRIGGER_DISPATCH_APPLY"]}
```

空字符串或无效 JSON → 不过滤（兼容旧版本）。

## API

### 获取完整类型列表（前端刷新用）

```
GET /api/schema/types
→ {"node_types": ["dm_event_info", ...], "rel_types": ["EVENT_TRIGGER_DISPATCH_APPLY", ...]}
```

### 保存过滤配置

```
PUT /api/settings
→ {"settings": {"schema_include": "{\"node_types\":[...],\"rel_types\":[...]}"}}
```

保存后需调用 `invalidate_schema_cache()` 清空缓存。

## `_get_schema` 改动

读取 `schema_include` 配置，过滤 `node_props` 和 `rel_props`：

```python
include = json.loads(s.get("schema_include", "") or "{}")
keep_nodes = set(include.get("node_types", []))
keep_rels = set(include.get("rel_types", []))
if keep_nodes:
    node_props = {k: v for k, v in node_props.items() if k[-1] in keep_nodes}
if keep_rels:
    rel_props = {k: v for k, v in rel_props.items() if k in keep_rels}
```

## 前端

在设置页新增「Schema 配置」区块：
- 刷新按钮 → 获取完整列表
- 节点类型 / 关系类型 两组 checkbox
- 全选/取消全选 快捷按钮
- 节点和关系类型统一使用英文名

## 缓存

`schema_include` 变更后必须使缓存失效，否则过滤不生效。

## 兼容性

- 旧 settings 没有 `schema_include` → `get("schema_include", "")` → 空 → 不过滤
- `invalidate_schema_cache()` 两个缓存（`_schema_cache` + `_schema_cache_ns`）都清空
