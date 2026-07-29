"""Build tree-structured text from graph data for structured display."""

import os
import json
from utils import primary_label as _primary_label

_TEMPLATES = None


def _load_templates():
    global _TEMPLATES
    if _TEMPLATES is not None:
        return _TEMPLATES
    path = os.path.join(os.path.dirname(__file__), "node_templates.json")
    try:
        with open(path, encoding="utf-8") as f:
            _TEMPLATES = json.load(f)
    except Exception:
        _TEMPLATES = {"node_templates": {}, "rel_names": {}}
    return _TEMPLATES


def _node_summary(node, ignored_label="") -> str:
    """Format a node using template from node_templates.json."""
    lbl = _primary_label(node.labels, ignored_label)
    props = {k: str(v) for k, v in node.properties.items() if v is not None}
    templates = _load_templates()
    tpl = templates["node_templates"].get(lbl, templates["node_templates"].get("_default", "[{label}]"))

    # Build format args: label + all properties
    fmt_args = {"label": lbl}
    fmt_args.update(props)

    # Replace {key} with value or empty string if missing
    import re
    result = re.sub(r"\{(\w+)\}", lambda m: str(fmt_args.get(m.group(1), "")), tpl)
    return f"[{lbl}] {result}"


def _rel_name(rel_type: str) -> str:
    """Get Chinese name for a relationship type."""
    templates = _load_templates()
    return templates["rel_names"].get(rel_type, templates["rel_names"].get("_default", "{type}")).format(type=rel_type)


def build_tree_text(graph_data, ignored_label: str = "") -> str:
    """Build tree-structured text from graph data, fully data-driven."""
    if not graph_data.nodes:
        return "（无数据）"

    node_map = {n.id: n for n in graph_data.nodes}
    outgoing = {}
    for r in graph_data.relationships:
        outgoing.setdefault(r.source, []).append((r.type, r.target))

    all_with_rels = {r.source for r in graph_data.relationships} | {r.target for r in graph_data.relationships}
    all_targets = {r.target for r in graph_data.relationships}
    isolated_ids = {n.id for n in graph_data.nodes} - all_with_rels
    roots = [n for n in graph_data.nodes
             if (n.id in all_with_rels and n.id not in all_targets) or n.id in isolated_ids]

    lines = []
    visited = set()

    def _traverse(node_id, depth):
        if node_id in visited or depth > 5:
            return
        visited.add(node_id)
        node = node_map.get(node_id)
        if not node:
            return

        indent = "  " * depth
        summary = _node_summary(node, ignored_label)
        lines.append(f"{indent}{summary}")

        for rel_type, target_id in outgoing.get(node_id, []):
            if target_id not in visited:
                tgt_node = node_map.get(target_id)
                tgt_lbl = _primary_label(tgt_node.labels, ignored_label) if tgt_node else "?"
                cn = _rel_name(rel_type)
                lines.append(f"{indent}  └─{cn}─({tgt_lbl})")
                _traverse(target_id, depth + 1)

    first_node = True
    for root in roots:
        if not first_node:
            lines.append("")
        first_node = False
        _traverse(root.id, 0)

    return "\n".join(lines)
