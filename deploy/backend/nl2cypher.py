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


def _get_schema(driver, database: str) -> str:
    with driver.session(database=database) as session:
        node_rows = list(session.run("CALL db.schema.nodeTypeProperties()"))
        node_props = {}
        for row in node_rows:
            labels = tuple(row["nodeLabels"])
            if labels not in node_props:
                node_props[labels] = []
            node_props[labels].append(
                f"{row['propertyName']}: {row['propertyTypes'][0].replace(' NOT NULL', '')}"
            )

        rel_rows = list(session.run("CALL db.schema.relTypeProperties()"))
        rel_props = {}
        for row in rel_rows:
            rt = row["relType"]
            if rt not in rel_props:
                rel_props[rt] = []
            rel_props[rt].append(
                f"{row['propertyName']}: {row['propertyTypes'][0].replace(' NOT NULL', '')}"
            )

        viz = list(session.run("CALL db.schema.visualization()"))
        rel_patterns = set()
        if viz:
            for rel in viz[0]["relationships"]:
                start = list(rel.start_node.labels)[0] if rel.start_node.labels else "?"
                end = list(rel.end_node.labels)[0] if rel.end_node.labels else "?"
                rel_patterns.add(f"(:{start})-[:{rel.type}]->(:{end})")

    lines = ["Node properties:"]
    for labels, props in node_props.items():
        label_name = labels[-1] if len(labels) > 1 else labels[0]
        lines.append(f"{label_name} {{{', '.join(props)}}}")

    lines.append("\nRelationship properties:")
    for rt, props in rel_props.items():
        clean_rt = rt.strip(":`")
        lines.append(f"{clean_rt} {{{', '.join(props)}}}")

    lines.append("\nThe relationships:")
    lines.extend(sorted(rel_patterns))

    return "\n".join(lines)


def _get_llm():
    s = get_all_settings()
    return OpenAILLM(
        model_name=s.get("llm_model", "gpt-4o"),
        model_params={"temperature": 0},
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


async def nl2cypher(question: str) -> dict:
    global _schema_cache
    s = get_all_settings()
    uri = s.get("neo4j_uri", "bolt://localhost:7687")
    user = s.get("neo4j_username", "neo4j")
    pwd = s.get("neo4j_password", "")
    db = s.get("neo4j_database", "neo4j")

    custom_prompt = s.get("nl_query_prompt", "")
    if not custom_prompt:
        custom_prompt = None

    sync_driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        if _schema_cache is None or _schema_cache_db != db:
            _schema_cache = _get_schema(sync_driver, db)
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
        generated_cypher = result.metadata.get("cypher", "")

        from backend.database import conn_manager
        records, _ = await conn_manager.run_query(cypher=generated_cypher)

        return {"generated_cypher": generated_cypher, "records": records or []}
    finally:
        sync_driver.close()
