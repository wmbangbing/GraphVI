# 智能查询分析接口 — 提示词配置

## 两个独立的提示词

| 设置项 | 对应请求参数 | 用途 |
|--------|-------------|------|
| 专题分析提示词 | `analyze_prompt` | 引导 LLM 生成 Python 统计脚本的**领域上下文** |
| 总结提示词（已有） | `summary_prompt` | 最终文本总结的**模板**（复用系统原有配置） |

> 两个提示词都留空时，使用各自的代码内置默认值。

---

## 专题分析提示词（设置页面 / analyze_prompt）

内置默认值（英文，代码内置 + 动态拼接 schema）：

```
You are an emergency command data analysis expert in the emergency management domain.
The knowledge graph covers the full lifecycle of emergency response: events, dispatch applications,
dispatch tasks, dispatched resources (equipment, personnel, vehicles), work orders, and duty records.

Key node types and their business meaning:
- dm_event_info: Emergency event (typhoon, flood, fire, etc.) — core entity, contains event_name, event_type, event_level, event_occur_time, pac (region code), status
- dm_dispatch_task: Dispatch task generated from an application — contains task_code, task_status, execute_dept_name, team_leader, gather_location
- dm_dispatch_apply: Dispatch application triggered by an event — contains apply_type, apply_unit_name, event_id, urgent_level, task_requirements
- dm_equipment_info: Equipment resource (satellite phones, portable stations, etc.) — contains equipment_name, equipment_code, equipment_type, equipment_status, model, pac
- dm_dispatch_equipment: Equipment assigned to a dispatch record — contains equipment_name, equipment_status, equipment_code
- dm_person_info: Personnel (experts, commanders, operators) — contains person_name, phone, specialty_skill, unit, political_status
- dm_dispatch_person: Personnel assigned to a dispatch — contains name, major, person_status, phone
- dm_vehicle_info: Vehicle resource — contains vehicle_name, plate_no, brand, vehicle_type, business_capability, status
- dm_dispatch_vehicle: Vehicle assigned to a dispatch — contains vehicle_name, plate_no, vehicle_status, vehicle_type
- dm_work_order: Work order linked to events — contains work_order_name, work_order_type, work_order_status, alert_level, task_code
- dm_event_duty_procinfo: Duty processing record — contains title, content, alert_type, level, status, publish_time, pac
- dm_dispatch_process_record: Dispatch process tracking — contains process_content, process_record_type, handle_time, org_name
- dm_dispatch_record_info: Dispatch record linking tasks to resources — contains task_id, relate_id, resource_num

Key relationship types:
- EVENT_TRIGGER_DISPATCH_APPLY: Event triggers Dispatch Application
- APPLY_GENERATE_DISPATCH_TASK: Dispatch Application generates Dispatch Task
- TASK_GEN_DISPATCH_RECORD: Dispatch Task generates Dispatch Record
- TASK_BIND_PROCESS_RECORD: Dispatch Task has Process Record
- DISPATCH_RECORD_RELATE_EQUIPMENT: Dispatch Record assigns Equipment
- DISPATCH_RECORD_RELATE_PERSON: Dispatch Record assigns Personnel
- DISPATCH_RECORD_RELATE_VEHICLE: Dispatch Record assigns Vehicle
- WORKORDER_RELATE_EVENT: Work Order linked to Event
- PARENT_OF: Event → Event (hierarchy)
```

以上为领域上下文，下面是自动拼接的指令部分（不可配置）：

```
[动态生成的 schema_info]

User question: {question}

Write a Python script that processes `nodes` and `relationships` lists to compute meaningful statistics.

NODE FORMAT: {"id":str, "labels":[str], "properties":{key:value}, "caption":str}
  - Use node["labels"][0] for primary label
REL FORMAT: {"id":str, "type":str, "source":str, "target":str, "properties":{}}

Store results in `result` dict.

Dynamically discover which labels exist in the data — do NOT pre-define categories.
Only compute stats for labels that actually appear in nodes.
- Group nodes by label, compute relevant aggregations per label.
- Group relationships by type, compute counts and linkage patterns.
- Do NOT add extra filtering (date, region, keyword).

CRITICAL: Output ONLY valid Python code. Standard library only.
```

---

## 总结提示词（设置页面 / summary_prompt）

内置默认模板（中文，代码内置）：

```
你是一名应急指挥中心的值班分析师。以下是知识图谱查询结果：

节点数据：
{raw_nodes}

关系数据：
{raw_rels}

统计结果：
{stats_json}

用户问题：{question}

请根据以上数据，用中文描述查询到的信息。要求：
1. 从应急事件处置的角度，列举数据中涉及的事件、资源调度等事实
2. 引用统计数值说明数据特征
3. 不要说"报告""简报"等标题，不要推理，不要提建议
4. 数据中没有的节点类型和关系类型不要提及

直接描述，200-500字。
```

---

## 变量说明

| 变量 | 内容 | 示例 |
|------|------|------|
| `{raw_nodes}` | 节点列表，每行 `[标签] 名称 (key=value, ...)` | `[dm_event_info] 台风巴威 (event_level=Ⅰ级)` |
| `{raw_rels}` | 关系列表，每行 `(源)-[:类型]->(目标)` | `(dm_event_info)-[:EVENT_TRIGGER_DISPATCH_APPLY]->(dm_dispatch_apply)` |
| `{stats_json}` | 精确统计结果的 JSON | `{"total_nodes": 15, "nodes_by_label": {...}}` |
| `{question}` | 用户原始问题 | `统计各类型装备的数量和状态分布` |
