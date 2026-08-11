"""Natural language to Cypher query using neo4j-graphrag Text2CypherRetriever"""

import asyncio
from neo4j import GraphDatabase
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.retrievers import Text2CypherRetriever

from backend.settings_db import get_all_settings

_schema_cache = None       # with samples (for nl2cypher)
_schema_cache_db = None
_schema_cache_ns = None    # without samples (for semantic_nl)
_schema_cache_db_ns = None
_sync_driver = None
_sync_driver_key = ""


def invalidate_schema_cache():
    global _schema_cache, _schema_cache_db, _schema_cache_ns, _schema_cache_db_ns, _sync_driver
    _schema_cache = None
    _schema_cache_db = None
    _schema_cache_ns = None
    _schema_cache_db_ns = None
    if _sync_driver is not None:
        try:
            _sync_driver.close()
        except Exception:
            pass
        _sync_driver = None


def _get_cached_driver(uri: str, user: str, pwd: str):
    """Get or create a cached sync Neo4j driver, reused across requests."""
    global _sync_driver, _sync_driver_key
    key = f"{uri}|{user}|{pwd}"
    if _sync_driver is None or _sync_driver_key != key:
        if _sync_driver is not None:
            try:
                _sync_driver.close()
            except Exception:
                pass
        _sync_driver = GraphDatabase.driver(
            uri, auth=(user, pwd),
            max_connection_lifetime=3600,
            max_connection_pool_size=10,
        )
        _sync_driver_key = key
    return _sync_driver


def _get_label_samples(session, label_name: str) -> dict:
    try:
        query = f"MATCH (n) WHERE n:`{label_name}` RETURN n ORDER BY elementId(n) LIMIT 2"
        rows = list(session.run(query))
        samples = {}
        for row in rows:
            node = row["n"]
            for k, v in sorted(dict(node).items()):
                if k not in samples and v is not None and not str(v).startswith("http"):
                    val_str = str(v)[:40]
                    if len(val_str) > 3:
                        samples[k] = val_str
        return samples
    except Exception:
        return {}


def _get_schema(driver, database: str, include_samples: bool = False) -> str:
    with driver.session(database=database) as session:
        node_rows = list(session.run("CALL db.schema.nodeTypeProperties()"))
        node_rows.sort(key=lambda r: ".".join(r["nodeLabels"] or [""]))
        node_props = {}
        for row in node_rows:
            labels = tuple(row["nodeLabels"])
            if labels not in node_props:
                node_props[labels] = []
            pname = row["propertyName"]
            if pname == "embedding":
                continue
            ptype = row["propertyTypes"]
            ptype_str = ptype[0].replace(" NOT NULL", "") if ptype else "ANY"
            node_props[labels].append(f"{pname}: {ptype_str}")
        for props in node_props.values():
            props.sort()
        rel_rows = list(session.run("CALL db.schema.relTypeProperties()"))
        rel_rows.sort(key=lambda r: str(r["relType"] or ""))
        rel_props = {}
        for row in rel_rows:
            rt = row["relType"]
            if rt not in rel_props:
                rel_props[rt] = []
            pname = row["propertyName"]
            if pname is None:
                continue
            ptype = row["propertyTypes"]
            ptype_str = ptype[0].replace(" NOT NULL", "") if ptype else "ANY"
            rel_props[rt].append(f"{pname}: {ptype_str}")
        for props in rel_props.values():
            props.sort()

        viz = list(session.run("CALL db.schema.visualization()"))
        rel_patterns = set()
        s_all = get_all_settings()
        _ignored = s_all.get("ignored_label", "_Embeddable")
        _keep_rels = set()

        # Apply schema_include filter (reuse s_all to avoid extra DB read)
        import json as _json
        _si = (s_all.get("schema_include") or "")
        if _si:
            try:
                _inc = _json.loads(_si)
                _keep_nodes = set(_inc.get("node_types", []))
                _keep_rels = set(_inc.get("rel_types", []))
                if _keep_nodes:
                    node_props = {k: v for k, v in node_props.items() if any(l in _keep_nodes for l in k)}
                if _keep_rels:
                    rel_props = {k: v for k, v in rel_props.items() if k in _keep_rels}
            except (_json.JSONDecodeError, TypeError):
                pass

        if viz:
            for rel in viz[0]["relationships"]:
                rt = rel.type.strip(":`")
                if _keep_rels and rt not in _keep_rels:
                    continue
                start_labels = list(rel.start_node.labels) if rel.start_node.labels else ["?"]
                end_labels = list(rel.end_node.labels) if rel.end_node.labels else ["?"]
                start = next((l for l in start_labels if l != _ignored), start_labels[0])
                end = next((l for l in end_labels if l != _ignored), end_labels[0])
                rel_patterns.add(f"(:{start})-[:{rt}]->(:{end})")
        lines = ["Node properties:"]
        for labels, props in node_props.items():
            if not labels:
                continue
            label_name = labels[-1] if len(labels) > 1 else labels[0]
            lines.append(f"{label_name} {{{', '.join(props)}}}")
            if include_samples:
                samples = _get_label_samples(session, label_name)
                if samples:
                    sample_str = ", ".join(f'{k}="{v}"' for k, v in samples.items())
                    lines.append(f"  Sample: {sample_str}")
        lines.append("\nRelationship properties:")
        for rt, props in rel_props.items():
            if not rt:
                continue
            clean_rt = rt.strip(":`")
            lines.append(f"{clean_rt} {{{', '.join(props)}}}")
        lines.append("\nThe relationships:")
        lines.extend(sorted(rel_patterns))
        return "\n".join(lines)


def _strip_sample_lines(schema: str) -> str:
    """Remove `Sample:` lines from a with-samples schema string."""
    return "\n".join(l for l in schema.splitlines() if not l.lstrip().startswith("Sample:"))


async def get_schema(sync_driver, database: str, include_samples: bool = False) -> str:
    """Shared schema cache for nl2cypher AND semantic_nl_search.

    A single underlying fetch is reused: the with-samples variant is fetched
    once, and the without-samples variant is derived from it by stripping the
    `Sample:` lines — so the schema is never fetched from Neo4j twice.
    """
    global _schema_cache, _schema_cache_db, _schema_cache_ns, _schema_cache_db_ns
    if include_samples:
        if _schema_cache is None or _schema_cache_db != database:
            _schema_cache = await asyncio.to_thread(_get_schema, sync_driver, database, True)
            _schema_cache_db = database
        return _schema_cache
    # Without samples: derive from the with-samples cache when available.
    if _schema_cache_ns is None or _schema_cache_db_ns != database:
        if _schema_cache is not None and _schema_cache_db == database:
            _schema_cache_ns = _strip_sample_lines(_schema_cache)
        else:
            _schema_cache_ns = await asyncio.to_thread(_get_schema, sync_driver, database, False)
        _schema_cache_db_ns = database
    return _schema_cache_ns


def _get_llm():
    s = get_all_settings()
    # extra_body disables reasoning mode on deepseek models — without it the
    # reasoning content can exhaust tokens and return an empty Cypher.
    return OpenAILLM(
        model_name=s.get("llm_model", "gpt-4o"),
        model_params={"temperature": 0, "seed": 42,
                      "extra_body": {"thinking": {"type": "disabled"}}},
        api_key=s.get("llm_api_key", ""),
        base_url=s.get("llm_endpoint", "https://api.openai.com/v1") + "/",
    )


def _get_examples() -> list[str]:
    try:
        from backend.presets_db import get_all as get_all_presets
        presets = get_all_presets()
        examples = []
        for p in presets:
            if p.get("cypher"):
                examples.append(
                    f"USER INPUT: '{p['question']}'\nQUERY: {p['cypher']}"
                )
        return examples[:10]
    except Exception:
        return []


import re


def _apoc_map_expr(var: str) -> str:
    """Cypher expression wrapping a NODE into {id, labels, props} without embedding."""
    return (f"(CASE WHEN {var} IS NULL THEN null ELSE "
            f"{{id: elementId({var}), labels: labels({var}), "
            f"props: apoc.map.removeKeys({var}, ['embedding'])}} END)")


def _wrap_return_apoc(cypher: str) -> str:
    """v2: wrap top-level RETURN node collections as APOC maps to exclude embedding.

    Only the FINAL RETURN is wrapped (internal CALLs keep real nodes so UNWIND
    reuse works). Generic: detects node-collection aliases via
    `collect(DISTINCT node_var) AS alias` where node_var is a node (from `(v:`).
    """
    if "RETURN" not in cypher:
        return cypher

    # Anchor on the FINAL (main) RETURN so node_vars covers ALL CALL subquery
    # variables. Using the FIRST RETURN would only see the first CALL's vars,
    # leaving later aliases (e.g. parent_events) unwrapped and leaking embedding.
    _main_ret = cypher.rindex("RETURN")
    match_section = cypher[:_main_ret]
    node_vars = set(re.findall(r"\((\w+):", match_section)) | set(re.findall(r"\((\w+)\)", match_section))
    rel_vars = set(re.findall(r"\[(\w+):", match_section))
    all_aliases = set(re.findall(r"\bAS\s+(\w+)", cypher))

    # Which aliases are node collections? collect(DISTINCT node_var) AS alias.
    # Skip `_path_N` aliases — the fix-generated mixed collections (nodes + rels)
    # that cannot be wrapped as pure node maps.
    node_aliases = set()
    for m in re.finditer(r"collect\(\s*DISTINCT\s+(\w+)\s*\)\s*AS\s+(\w+)", cypher):
        var, alias = m.group(1), m.group(2)
        if var in node_vars and var not in rel_vars and not alias.startswith("_path_"):
            node_aliases.add(alias)

    ret_pos = cypher.rindex("RETURN")
    main_ret = cypher[ret_pos:]
    lim_split = main_ret.split("LIMIT")
    ret_cols = lim_split[0][len("RETURN"):]
    rest = " LIMIT" + lim_split[1] if len(lim_split) > 1 else ""

    cols = [c.strip() for c in ret_cols.split(",")]
    new_cols = []
    for c in cols:
        if not c:
            continue
        # Column may be a bare alias (semantic-nl CALL: `child_events`) or a
        # full expression (nl2cypher: `collect(DISTINCT child) AS children`).
        alias = c.split()[-1].rstrip(",") if c.strip() else ""
        if c in node_aliases:
            new_cols.append(f"[x IN {c} | {_apoc_map_expr('x')}]")
        elif alias in node_aliases:
            new_cols.append(f"[x IN {alias} | {_apoc_map_expr('x')}]")
        elif c in node_vars and c not in all_aliases and not c.startswith("_path_"):
            new_cols.append(_apoc_map_expr(c))
        else:
            new_cols.append(c)
    return cypher[:ret_pos] + "RETURN " + ", ".join(new_cols) + rest


def _fix_unnamed_rels(cypher: str) -> str:
    """Post-process Cypher for graph rendering completeness.
    - Names anonymous nodes and relationships in MATCH/OPTIONAL MATCH
    - Converts directed relationships to undirected
    - Ensures RETURN includes all variables from MATCH clauses
    - Handles CALL { ... } subqueries (name + orphan collection)
    """
    # ── Naming engine ──────────────────────────────────────────────────────
    existing_vars = {m for match in re.findall(r"\((\w+):|\[(\w+):", cypher) for m in match if m}
    rel_idx, node_idx = [0], [0]

    def _unique_name(prefix, idx_list):
        while True:
            idx_list[0] += 1
            name = f"{prefix}{idx_list[0]}"
            if name not in existing_vars:
                existing_vars.add(name)
                return name

    def _name_node(text):
        return re.sub(r"\(:(\w+)\)", lambda m: f"({_unique_name('n', node_idx)}:{m.group(1)})", text)

    def _name_rels(text):
        for pat in [
            r"-\[\s*:([\w|*:]+(?:\s*\|\s*:?[\w|*:]+)*)\s*\]\s*->",
            r"<-\s*\[\s*:([\w|*:]+(?:\s*\|\s*:?[\w|*:]+)*)\s*\]\s*-",
            r"-\[\s*:([\w|*:]+(?:\s*\|\s*:?[\w|*:]+)*)\s*\]\s*-",
        ]:
            text = re.sub(pat, lambda m, p=pat: f"-[{_unique_name('r', rel_idx)}:{m.group(1)}]-" if "->" not in p else
                          f"-[{_unique_name('r', rel_idx)}:{m.group(1)}]->" if p.startswith("-") else
                          f"<-[{_unique_name('r', rel_idx)}:{m.group(1)}]-", text)
        return text

    def _undirect(text):
        t = re.sub(r"(\[[\w]+:[^\]]*\])\s*->", r"\1-", text)
        t = re.sub(r"<-\s*(\[[\w]+:[^\]]*\])", r"-\1", t)
        return t

    def _fix_block(text):
        """Run naming + undirect on a text block."""
        t = _name_node(text)
        t = _name_rels(t)
        t = _undirect(t)
        return t

    # ── Step 0: Safety limit on unbounded variable-length paths ─────────
    # Replace [:REL*0..] with bounded [:REL*1..3] to prevent exponential
    # path explosion (common LLM-generated anti-pattern).
    cypher = re.sub(r'\[([^:]*):(\w+)\*0\.\.\]', r'[\1:\2*1..3]', cypher)

    # ── Step 1: Handle CALL subqueries (must be processed first) ──────────
    print("=== [Cypher before fix] ===", flush=True)
    print(cypher, flush=True)

    # Support both `CALL { ... }` (implicit scope) and `CALL (entry) { ... }`
    # (Neo4j 5.26 explicit scope) forms.
    _CALL_RE = r"\bCALL\s*(?:\(\s*[A-Za-z_]\w*\s*\))?\s*\{"
    has_call = bool(re.search(_CALL_RE, cypher))

    if has_call:
        # Extract CALL blocks
        call_blocks = []
        work = cypher
        while True:
            m = re.search(_CALL_RE, work)
            if not m: break
            depth, pos = 1, m.end()
            while pos < len(work) and depth > 0:
                if work[pos] == '{': depth += 1
                elif work[pos] == '}': depth -= 1
                pos += 1
            call_blocks.append(work[m.start():pos])
            work = work[:m.start()] + f"__CALL_BLOCK_{len(call_blocks)-1}__" + work[pos:]

        # Fix non-CALL outer parts (naming/undirect)
        fixed = _fix_block(work)

        # Fix each CALL block independently
        _KW = {'WITH','OPTIONAL','MATCH','RETURN','LIMIT','ORDER','BY','SKIP','WHERE',
               'AND','OR','NOT','IN','AS','DISTINCT','COLLECT','collect','UNWIND','CASE',
               'WHEN','THEN','ELSE','END','NULL','TRUE','FALSE','entries','entry','ALL',
               'REDUCE','acc','lst'}

        fixed_bodies = []
        for idx, body in enumerate(call_blocks):
            brace_s = body.index('{')
            brace_e = body.rindex('}') + 1
            prefix = body[:brace_s]
            inner = body[brace_s:brace_e]

            inner_fixed = _fix_block(inner)

            # Add orphan vars to this CALL's RETURN
            ret_m = re.search(r"(\bRETURN\s+)(.+?)(?:\s*(?:$|(?=\})))",
                              inner_fixed, re.IGNORECASE | re.DOTALL)
            if ret_m:
                # Collect all orphan node/rel variables and pack into ONE alias per CALL
                mv = set(re.findall(r"\((\w+):", inner_fixed[:ret_m.start()]))
                mv |= set(re.findall(r"\[(\w+):", inner_fixed[:ret_m.start()]))
                ret_cols = [c.strip() for c in re.split(r"\s*,\s*", ret_m.group(2))]
                ret_aliases = set()
                for c in ret_cols:
                    p = c.strip().split()
                    if p: ret_aliases.add(p[-1].rstrip(','))
                wm = re.search(r"\bWITH\s+(.+?)(?=\b(?:OPTIONAL|MATCH|RETURN|UNWIND)\b)",
                               inner_fixed, re.IGNORECASE)
                wv = set(re.findall(r'\b([a-zA-Z_]\w*)\b', wm.group(1))) if wm else set()
                # Vars already consumed by collect(DISTINCT v) AS alias — skip them,
                # so e.g. `collect(DISTINCT child_event) AS child_events` isn't packed
                # again into the _path_N orphan collection. Scan the WHOLE CALL block
                # (collect() lives inside RETURN, after ret_m.start()).
                collected_vars = set(re.findall(r"collect\(\s*DISTINCT\s+(\w+)",
                                                inner_fixed))
                orphans = sorted(v for v in mv if v not in wv and v not in ret_aliases
                                 and v not in collected_vars and v not in _KW)
                if orphans:
                    # Pack all orphans into ONE collect per CALL block to reduce RETURN columns
                    packed = " + ".join(f"collect(DISTINCT {v})" for v in orphans)
                    adds = f"{packed} AS _path_{idx}"
                    inner_fixed = inner_fixed[:ret_m.end()] + ",\n" + adds + inner_fixed[ret_m.end():]

            fixed_bodies.append(prefix + inner_fixed)

        # Put CALL blocks back
        for idx, body in enumerate(fixed_bodies):
            fixed = fixed.replace(f"__CALL_BLOCK_{idx}__", body, 1)

        # Propagate aliases through post-CALL WITH
        all_aliases = set(re.findall(r'\b(_[a-zA-Z]\w*_\d+)\b', fixed))
        if "}" in fixed:
            after_calls = fixed[fixed.rindex("}")+1:]
            wm = re.search(r"\bWITH\b", after_calls)
            if wm and all_aliases:
                abs_pos = fixed.index(after_calls) + wm.start()
                after_w = fixed[abs_pos+4:]
                wce = re.search(r"(?=\b(?:OPTIONAL|MATCH|RETURN|LIMIT|ORDER|SKIP|WITH|CALL|UNWIND)\b)",
                                after_w, re.IGNORECASE)
                wc_end = abs_pos + 4 + (wce.start() if wce else len(after_w))
                existing = set(re.findall(r'\b([a-zA-Z_]\w*)\b', fixed[abs_pos:wc_end])) - _KW
                missing = sorted(a for a in all_aliases if a not in existing)
                if missing:
                    fixed = fixed[:wc_end] + ",\n" + ",\n".join(missing) + fixed[wc_end:]

        # Add aliases to main RETURN
        if all_aliases and "LIMIT" in fixed and "RETURN" in fixed:
            ret_section = fixed[fixed.rindex("RETURN"):fixed.rindex("LIMIT")]
            aliases_in_ret = set(re.findall(r'\b(_[a-zA-Z]\w*_\d+)\b', ret_section))
            still_missing = sorted(all_aliases - aliases_in_ret)
            if still_missing:
                fixed = (fixed[:fixed.rindex("LIMIT")] + ",\n" + ",\n".join(still_missing) + "\n" +
                         fixed[fixed.rindex("LIMIT"):])

        # Ensure entry node is in RETURN (entry always exists in outer scope after MATCH)
        if "LIMIT" in fixed and "RETURN" in fixed:
            main_ret = fixed[fixed.rindex("RETURN"):fixed.rindex("LIMIT")]
            has_entry = bool(re.search(r'\b(?<![a-zA-Z_])entry(?![a-zA-Z_.])', main_ret))
            has_entries = bool(re.search(r'\bentries\b', main_ret))
            if not has_entry and not has_entries:
                fixed = fixed[:fixed.rindex("LIMIT")] + ",\nentry\n" + fixed[fixed.rindex("LIMIT"):]

    else:
        # ── Step 2-6: Non-CALL processing (original logic) ────────────────
        ret_pos = -1
        m = re.search(r"\bRETURN\b", cypher)
        if m: ret_pos = m.start()
        before_return = cypher[:ret_pos] if ret_pos > 0 else cypher

        fixed = cypher

        if before_return:
            match_area = fixed[:ret_pos] if ret_pos > 0 else fixed
            fixed = _name_node(match_area) + fixed[ret_pos:] if ret_pos > 0 else _name_node(match_area)

        match_area_end = ret_pos if ret_pos > 0 else len(fixed)
        match_text = fixed[:match_area_end]
        fixed = _name_rels(match_text) + fixed[match_area_end:]

        only_match = fixed[:match_area_end]
        fixed = _undirect(only_match) + fixed[match_area_end:]

        # Collect all match variables
        match_vars = set(re.findall(r"\((\w+):", fixed[:match_area_end]))
        match_vars |= set(re.findall(r"\[(\w+):", fixed[:match_area_end]))

        has_with = bool(re.search(r"\bWITH\b", re.sub(
            r"\b(STARTS|ENDS|CONTAINS)\s+WITH\b", "", before_return, flags=re.IGNORECASE)))

        if has_with and match_vars:
            _KW = {'WITH','OPTIONAL','MATCH','RETURN','LIMIT','ORDER','BY','SKIP','WHERE',
                   'AND','OR','NOT','IN','AS','DISTINCT','COLLECT','collect','UNWIND','CASE',
                   'WHEN','THEN','ELSE','END','NULL','TRUE','FALSE', 'CALL','YIELD'}
            # Find non-"STARTS WITH" WITH clauses
            with_starts = []
            for m in re.finditer(r"\bWITH\b", fixed):
                before = fixed[max(0, m.start()-12):m.start()]
                if not re.search(r"\b(STARTS|ENDS|CONTAINS)\s*$", before, re.IGNORECASE):
                    with_starts.append(m.start())

            carried = {}
            for i, ws in enumerate(with_starts):
                anchor = with_starts[i-1] if i > 0 else 0
                seg_text = fixed[anchor:ws]
                seg_vars = set(re.findall(r"\((\w+):", seg_text)) | set(re.findall(r"\[(\w+):", seg_text))
                seg_vars.discard("entry")

                after_with = fixed[ws+4:]
                wce = re.search(r"(?=\b(?:OPTIONAL|MATCH|RETURN|LIMIT|ORDER|SKIP|WITH|CALL|UNWIND)\b)",
                                after_with, re.IGNORECASE)
                wc_end = ws + 4 + (wce.start() if wce else len(after_with))
                with_ids = set(re.findall(r'\b([a-zA-Z_]\w*)\b', fixed[ws:wc_end])) - _KW
                orphans = {v for v in (seg_vars - with_ids) if f"_{v}" not in carried}

                if orphans:
                    adds = sorted(f"collect(DISTINCT {v}) AS _{v}" for v in orphans)
                    insert = ",\n" + ",\n".join(adds) + "\n"
                    fixed = fixed[:wc_end] + insert + fixed[wc_end:]
                    for v in orphans:
                        carried[f"_{v}"] = v
                    offset = len(insert)
                    for j in range(i+1, len(with_starts)):
                        with_starts[j] += offset

            # Add carried aliases to RETURN
            ret_match = re.search(r"(RETURN\s+)(.+?)(?:\s+(?:LIMIT|ORDER|SKIP|WITH)\b|\s*$)",
                                  fixed, re.IGNORECASE)
            if ret_match and carried:
                ret_cols = [c.strip() for c in re.split(r"\s*,\s*", ret_match.group(2))]
                now_ret = {c.split()[-1] for c in ret_cols}
                missing_aliases = sorted(a for a in carried if a not in now_ret)
                if missing_aliases:
                    fixed = (fixed[:ret_match.start(2)] + ", ".join(ret_cols + missing_aliases) +
                             fixed[ret_match.end(2):])

        elif not has_with:
            ret_match = re.search(r"(RETURN\s+)(.+?)(?:\s+(?:LIMIT|ORDER|SKIP|WITH)\b|\s*$)",
                                  fixed, re.IGNORECASE)
            if ret_match and match_vars:
                ret_cols = [c.strip() for c in re.split(r"\s*,\s*", ret_match.group(2))]
                missing = sorted(v for v in match_vars if v not in ret_cols)
                if missing:
                    fixed = (fixed[:ret_match.start(2)] + ", ".join(ret_cols + missing) +
                             fixed[ret_match.end(2):])

    # ── Step 7 (v2): wrap top-level RETURN node collections as APOC maps ──
    # Excludes the embedding field from network transfer. Keeps internal CALLs
    # with real nodes (so UNWIND reuse still works); only the FINAL RETURN wraps.
    # Generic: detects node-collection aliases via `collect(DISTINCT node) AS a`.
    if "RETURN" in fixed:
        fixed = _wrap_return_apoc(fixed)

    print("=== [Cypher after fix] ===", flush=True)
    print(fixed, flush=True)
    return fixed


async def nl2cypher(question: str) -> dict:
    global _schema_cache, _schema_cache_db
    import time as _time
    _t_start = _time.monotonic()
    from datetime import datetime as _dt
    question = f"[Current time: {_dt.now().strftime('%Y-%m-%d %H:%M')}] {question}"
    s = get_all_settings()
    uri = s.get("neo4j_uri", "bolt://localhost:7687")
    user = s.get("neo4j_username", "neo4j")
    pwd = s.get("neo4j_password", "")
    db = s.get("neo4j_database", "neo4j")
    custom_prompt = s.get("nl_query_prompt", "")
    if not custom_prompt:
        custom_prompt = None
    include_samples = s.get("nl_schema_examples", "false") == "true"
    sync_driver = _get_cached_driver(uri, user, pwd)
    _schema_cache = await get_schema(sync_driver, db, include_samples)
    llm = _get_llm()
    examples = _get_examples()
    retriever = Text2CypherRetriever(
        driver=sync_driver, llm=llm, neo4j_schema=_schema_cache,
        examples=examples, custom_prompt=custom_prompt, neo4j_database=db,
    )
    _t_llm_start = _time.monotonic()
    result = await asyncio.to_thread(retriever.search, query_text=question)
    _t_llm_end = _time.monotonic()
    print(f"=== [NL] LLM 调用耗时: {_t_llm_end - _t_llm_start:.2f}s ===", flush=True)
    generated_cypher = result.metadata.get("cypher", "")
    generated_cypher = _fix_unnamed_rels(generated_cypher)
    from backend.database import conn_manager
    _t_cypher_start = _time.monotonic()
    records, _ = await conn_manager.run_query(cypher=generated_cypher)
    _t_cypher_end = _time.monotonic()
    print(f"=== [NL] Neo4j 查询耗时: {_t_cypher_end - _t_cypher_start:.2f}s ===", flush=True)
    print(f"=== [NL] 总耗时: {_t_cypher_end - _t_start:.2f}s ===", flush=True)
    return {"generated_cypher": generated_cypher, "records": records or []}


async def generate_cypher_only(question: str) -> str:
    global _schema_cache, _schema_cache_db
    from datetime import datetime as _dt
    question = f"[Current time: {_dt.now().strftime('%Y-%m-%d %H:%M')}] {question}"
    s = get_all_settings()
    uri = s.get("neo4j_uri", "bolt://localhost:7687")
    user = s.get("neo4j_username", "neo4j")
    pwd = s.get("neo4j_password", "")
    db = s.get("neo4j_database", "neo4j")
    custom_prompt = s.get("nl_query_prompt", "")
    if not custom_prompt:
        custom_prompt = None
    include_samples = s.get("nl_schema_examples", "false") == "true"
    sync_driver = _get_cached_driver(uri, user, pwd)
    _schema_cache = await get_schema(sync_driver, db, include_samples)
    llm = _get_llm()
    examples = _get_examples()
    retriever = Text2CypherRetriever(
        driver=sync_driver, llm=llm, neo4j_schema=_schema_cache,
        examples=examples, custom_prompt=custom_prompt, neo4j_database=db,
    )
    result = await asyncio.to_thread(retriever.search, query_text=question)
    return _fix_unnamed_rels(result.metadata.get("cypher", ""))
