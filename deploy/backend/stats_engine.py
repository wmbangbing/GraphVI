"""Statistical script generation and execution for auto query analyze.

Generates Python scripts via LLM, executes them via PythonREPLTool,
and falls back to pre-computed aggregation on failure.
"""

import asyncio
import json
import os

from backend.models import GraphResponse
from backend.llm_service import _aggregate_stats, _safe_exec, _call_llm_async


def _build_stats_prompt(graph_data: GraphResponse, question: str, user_prompt: str | None = None) -> str:
    """Build prompt for LLM script generation."""
    # Build schema info from actual data
    labels = {}
    for n in graph_data.nodes:
        for lbl in n.labels:
            labels.setdefault(lbl, {})
            for k, v in n.properties.items():
                labels[lbl].setdefault(k, type(v).__name__)

    schema_lines = ["Data structure:"]
    for lbl, props in sorted(labels.items()):
        schema_lines.append(
            f"  {lbl}: {{{', '.join(f'{k}: {t}' for k, t in sorted(props.items()))}}}"
        )
    schema_lines.append(
        f"\nTotal: {len(graph_data.nodes)} nodes, {len(graph_data.relationships)} relationships"
    )
    schema_info = "\n".join(schema_lines)

    domain_context = user_prompt if user_prompt else (
        "You are an emergency command data analysis expert in the emergency management domain. "
        "The knowledge graph covers the full lifecycle of emergency response: events, dispatch applications, "
        "dispatch tasks, dispatched resources (equipment, personnel, vehicles), work orders, and duty records.\n\n"
        "Key node types and their business meaning:\n"
        "- dm_event_info: Emergency event (typhoon, flood, fire, etc.) — core entity, contains event_name, event_type, event_level, event_occur_time, pac (region code), status\n"
        "- dm_dispatch_task: Dispatch task generated from an application — contains task_code, task_status, execute_dept_name, team_leader, gather_location\n"
        "- dm_dispatch_apply: Dispatch application triggered by an event — contains apply_type, apply_unit_name, event_id, urgent_level, task_requirements\n"
        "- dm_equipment_info: Equipment resource (satellite phones, portable stations, etc.) — contains equipment_name, equipment_code, equipment_type, equipment_status, model, pac\n"
        "- dm_dispatch_equipment: Equipment assigned to a dispatch record — contains equipment_name, equipment_status, equipment_code\n"
        "- dm_person_info: Personnel (experts, commanders, operators) — contains person_name, phone, specialty_skill, unit, political_status\n"
        "- dm_dispatch_person: Personnel assigned to a dispatch — contains name, major, person_status, phone\n"
        "- dm_vehicle_info: Vehicle resource — contains vehicle_name, plate_no, brand, vehicle_type, business_capability, status\n"
        "- dm_dispatch_vehicle: Vehicle assigned to a dispatch — contains vehicle_name, plate_no, vehicle_status, vehicle_type\n"
        "- dm_work_order: Work order linked to events — contains work_order_name, work_order_type, work_order_status, alert_level, task_code\n"
        "- dm_event_duty_procinfo: Duty processing record — contains title, content, alert_type, level, status, publish_time, pac\n"
        "- dm_dispatch_process_record: Dispatch process tracking — contains process_content, process_record_type, handle_time, org_name\n"
        "- dm_dispatch_record_info: Dispatch record linking tasks to resources — contains task_id, relate_id, resource_num\n\n"
        "Key relationship types:\n"
        "- EVENT_TRIGGER_DISPATCH_APPLY: Event triggers Dispatch Application\n"
        "- APPLY_GENERATE_DISPATCH_TASK: Dispatch Application generates Dispatch Task\n"
        "- TASK_GEN_DISPATCH_RECORD: Dispatch Task generates Dispatch Record\n"
        "- TASK_BIND_PROCESS_RECORD: Dispatch Task has Process Record\n"
        "- DISPATCH_RECORD_RELATE_EQUIPMENT: Dispatch Record assigns Equipment\n"
        "- DISPATCH_RECORD_RELATE_PERSON: Dispatch Record assigns Personnel\n"
        "- DISPATCH_RECORD_RELATE_VEHICLE: Dispatch Record assigns Vehicle\n"
        "- WORKORDER_RELATE_EVENT: Work Order linked to Event\n"
        "- PARENT_OF: Event → Event (hierarchy)"
    )

    return f"""{domain_context}

{schema_info}

User question: {question}

Write a Python script that processes `nodes` and `relationships` lists to compute meaningful statistics relevant to the user question.

NODE FORMAT: {{"id":str, "labels":[str], "properties":{{key:value}}, "caption":str}}
  - Use node["labels"][0] for primary label
  - Use node["properties"] for attribute values
REL FORMAT: {{"id":str, "type":str, "source":str, "target":str, "properties":{{}}}}

Store results in `result` dict (already defined). Use defaultdict from collections if needed.

Dynamically discover which labels exist in the data — do NOT pre-define categories. Only compute stats for labels that actually appear in nodes.
- Group nodes by label, compute relevant aggregations per label.
- Group relationships by type, compute counts and linkage patterns.
- Do NOT add extra filtering (date, region, keyword).
- Store results in `result` dict.

CRITICAL: Output ONLY valid Python code. Standard library only (collections, math, statistics, itertools, re, datetime)."""


async def generate_and_execute(
    graph_data: GraphResponse,
    question: str,
    user_prompt: str | None = None,
    ignored_label: str = "",
) -> dict:
    """LLM 生成统计脚本 → 执行 → 返回统计结果。失败时降级到预计算统计。"""
    # Convert GraphResponse to dict format for existing functions
    nodes_dict = [
        {
            "id": n.id,
            "labels": n.labels,
            "properties": n.properties,
            "caption": n.caption,
        }
        for n in graph_data.nodes
    ]
    rels_dict = [
        {
            "id": r.id,
            "type": r.type,
            "source": r.source,
            "target": r.target,
            "properties": r.properties,
        }
        for r in graph_data.relationships
    ]

    # Pre-computed stats as fallback
    fallback = _aggregate_stats(nodes_dict, rels_dict, ignored_label)

    if not graph_data.nodes:
        return fallback

    try:
        # Step 1: Build prompt from data schema + question
        prompt = _build_stats_prompt(graph_data, question, user_prompt)

        # Step 2: LLM generates script (async, non-blocking)
        script = await _call_llm_async(prompt, max_tokens=8192)

        # Strip markdown fences
        script = script.strip()
        if script.startswith("```"):
            first_nl = script.find("\n")
            if first_nl > 0:
                script = script[first_nl + 1 :]
            end = script.rfind("```")
            if end >= 0:
                script = script[:end]
        script = script.strip()
        if not script:
            raise RuntimeError("empty script after stripping")

        # Save for debugging
        script_path = os.path.join(os.path.dirname(__file__), "_generated_stats.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        # Step 3: Execute via PythonREPLTool (run in thread to avoid blocking)
        computed = await asyncio.to_thread(_safe_exec, script, nodes_dict, rels_dict)
        if computed:
            return computed

        raise RuntimeError("script returned empty")
    except Exception as e:
        print(f"[stats_engine] script failed, fallback to pre-computed: {e}", flush=True)
        return fallback
