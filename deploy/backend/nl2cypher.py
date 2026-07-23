"""Natural language to Cypher query using neo4j-graphrag Text2CypherRetriever"""

from neo4j import GraphDatabase
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.retrievers import Text2CypherRetriever

from backend.settings_db import get_all_settings

_schema_cache = None
_schema_cache_db = None


def invalidate_schema_cache():
    global _schema_cache, _schema_cache_db
    _schema_cache = None
    _schema_cache_db = None


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
            ptype = row["propertyTypes"]
            ptype_str = ptype[0].replace(" NOT NULL", "") if ptype else "ANY"
            node_props[labels].append(f"{row['propertyName']}: {ptype_str}")
        for props in node_props.values():
            props.sort()

        rel_rows = list(session.run("CALL db.schema.relTypeProperties()"))
        rel_rows.sort(key=lambda r: str(r["relType"] or ""))
        rel_props = {}
        for row in rel_rows:
            rt = row["relType"]
            if rt not in rel_props:
                rel_props[rt] = []
            ptype = row["propertyTypes"]
            ptype_str = ptype[0].replace(" NOT NULL", "") if ptype else "ANY"
            rel_props[rt].append(f"{row['propertyName']}: {ptype_str}")
        for props in rel_props.values():
            props.sort()

        viz = list(session.run("CALL db.schema.visualization()"))
        rel_patterns = set()
        if viz:
            for rel in viz[0]["relationships"]:
                start = list(rel.start_node.labels)[0] if rel.start_node.labels else "?"
                end = list(rel.end_node.labels)[0] if rel.end_node.labels else "?"
                rel_patterns.add(f"(:{start})-[:{rel.type}]->(:{end})")

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


def _get_llm():
    s = get_all_settings()
    return OpenAILLM(
        model_name=s.get("llm_model", "gpt-4o"),
        model_params={"temperature": 0, "seed": 42},
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


def _fix_unnamed_rels(cypher: str) -> str:
    """Post-process: give variables to unnamed relationships and ensure RETURN
    includes them so the graph renderer gets node+edge data."""
    existing = set(re.findall(r"\[(\w+):", cypher))
    counter = [0]

    def _new_var():
        counter[0] += 1
        v = f"r{counter[0]}"
        while v in existing:
            counter[0] += 1
            v = f"r{counter[0]}"
        existing.add(v)
        return v

    # 1. Give variables to unnamed relationships
    fixed = re.sub(
        r"(?<=[\-(,])-\s*\[\s*:([\w*|]+(?:\s*\|\s*[\w*]+)*)\s*\]\s*->",
        lambda m: f"-[{_new_var()}:{m.group(1)}]->",
        cypher,
    )
    fixed = re.sub(
        r"(?<=[\-(,])<-\s*\[\s*:([\w*|]+(?:\s*\|\s*[\w*]+)*)\s*\]\s*-",
        lambda m: f"<-[{_new_var()}:{m.group(1)}]-",
        fixed,
    )

    # 2. Collect all rel variable names
    rel_vars = re.findall(r"\[(\w+):", fixed)

    # 3. Ensure RETURN includes them
    ret_m = re.search(
        r"RETURN\s+(.+?)(?:\s+(?:LIMIT|ORDER|SKIP|WITH)\b|\s*$)",
        fixed,
        re.IGNORECASE,
    )
    if ret_m and rel_vars:
        ret_cols = [c.strip() for c in re.split(r"\s*,\s*", ret_m.group(1))]
        missing = [v for v in rel_vars if v not in ret_cols]
        if missing:
            after = fixed[ret_m.end(1):]
            fixed = fixed[:ret_m.end(1)] + ", " + ", ".join(missing) + after

    return fixed


async def nl2cypher(question: str) -> dict:
    global _schema_cache, _schema_cache_db
    s = get_all_settings()
    uri = s.get("neo4j_uri", "bolt://localhost:7687")
    user = s.get("neo4j_username", "neo4j")
    pwd = s.get("neo4j_password", "")
    db = s.get("neo4j_database", "neo4j")

    custom_prompt = s.get("nl_query_prompt", "")
    if not custom_prompt:
        custom_prompt = None

    include_samples = s.get("nl_schema_examples", "false") == "true"

    sync_driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        if _schema_cache is None or _schema_cache_db != db:
            _schema_cache = _get_schema(sync_driver, db, include_samples)
            _schema_cache_db = db

        llm = _get_llm()
        examples = _get_examples()

        retriever = Text2CypherRetriever(
            driver=sync_driver,
            llm=llm,
            neo4j_schema=_schema_cache,
            examples=examples,
            custom_prompt=custom_prompt,
            neo4j_database=db,
        )

        result = retriever.search(query_text=question)
        generated_cypher = _fix_unnamed_rels(result.metadata.get("cypher", ""))

        from backend.database import conn_manager
        records, _ = await conn_manager.run_query(cypher=generated_cypher)

        return {"generated_cypher": generated_cypher, "records": records or []}
    finally:
        sync_driver.close()


def generate_cypher_only(question: str) -> str:
    """Generate Cypher from natural language WITHOUT executing.

    Returns the Cypher statement only, for third-party API consumption.
    """
    global _schema_cache, _schema_cache_db
    s = get_all_settings()
    uri = s.get("neo4j_uri", "bolt://localhost:7687")
    user = s.get("neo4j_username", "neo4j")
    pwd = s.get("neo4j_password", "")
    db = s.get("neo4j_database", "neo4j")

    custom_prompt = s.get("nl_query_prompt", "")
    if not custom_prompt:
        custom_prompt = None

    include_samples = s.get("nl_schema_examples", "false") == "true"

    sync_driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        if _schema_cache is None or _schema_cache_db != db:
            _schema_cache = _get_schema(sync_driver, db, include_samples)
            _schema_cache_db = db

        llm = _get_llm()
        examples = _get_examples()

        retriever = Text2CypherRetriever(
            driver=sync_driver,
            llm=llm,
            neo4j_schema=_schema_cache,
            examples=examples,
            custom_prompt=custom_prompt,
            neo4j_database=db,
        )

        result = retriever.search(query_text=question)
        return _fix_unnamed_rels(result.metadata.get("cypher", ""))
    finally:
        sync_driver.close()
