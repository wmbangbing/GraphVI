import sqlite3
import os

_env_db = os.environ.get("GRAPHVI_DB_PATH")
if _env_db:
    os.makedirs(os.path.dirname(_env_db), exist_ok=True)
    DB_PATH = _env_db
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "presets.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_settings_table():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    defaults = {
        "llm_endpoint": "https://api.openai.com/v1",
        "llm_api_key": "",
        "llm_model": "gpt-4o",
        "summary_prompt": "你是一个知识图谱分析助手。以下是一组知识图谱数据，包含节点和关系。请对数据进行分析总结，提炼关键信息、实体关系模式和数据特征。\n\n节点数量: {node_count}\n关系数量: {rel_count}\n\n节点列表:\n{nodes}\n\n关系列表:\n{rels}\n\n请用中文给出分析总结：",
        "neo4j_uri": "bolt://localhost:7687",
        "neo4j_username": "neo4j",
        "neo4j_password": "adminadmin",
        "neo4j_database": "kmdevelop",
        "nl_query_prompt": "Task: Generate a Cypher statement for querying a Neo4j knowledge graph.\n\nSchema:\n{schema}\n\nExamples:\n{examples}\n\nUser question:\n{query_text}\n\nRules:\n1. When the user asks for \"all information\" or \"detailed info\" about a specific entity, use variable-length matching [*1..2] to include connected nodes and relationships.\n2. When using variable-length matching, RETURN individual node and relationship variables instead of a path.\n   Example: MATCH (n:Label {{prop: 'value'}})-[*1..2]-(m) RETURN n, m  — NOT RETURN path\n3. When the user asks about relationships between specific entities, use specific relationship patterns.\n4. For simple listing queries, use basic MATCH with appropriate labels.\n5. ONLY use read-only statements: MATCH, RETURN, WHERE, LIMIT, ORDER BY, SKIP.\n6. NEVER use CREATE, DELETE, SET, MERGE, REMOVE, DETACH.\n7. Use node labels and relationship types from the schema only. Do not invent labels.\n8. Always add LIMIT (default 100).\n9. Return only the Cypher statement, no explanations or markdown.\n10. ALWAYS give each relationship a variable name in MATCH and include all\n    relationship variables in RETURN.\n    Correct: MATCH (n)-[r:REL]->(m) RETURN n, r, m\n    Incorrect: MATCH (n)-[:REL]->(m) RETURN n, m\n11. NEVER use datetime() function. Date/time fields are strings — use string comparison (STARTS WITH, CONTAINS, >=, <=) instead.\n\nCypher query:\n",
        "nl_schema_examples": "false",
        "embedding_endpoint": "https://api.openai.com/v1",
        "embedding_api_key": "",
        "embedding_model": "text-embedding-3-small",
        "vector_index_name": "entity_vector",
        "semantic_query_hops": "1",
        "enable_script_stats": "false",
        "semantic_score_threshold": "0.6",
        "semantic_top_k": "10",
        # --- auto analyze ---
        "auto_default_strategy": "auto",
        "auto_analyze_prompt": "",
        "auto_parallel_timeout": "40",
        "auto_semantic_top_k": "10",
        "auto_semantic_score_threshold": "0.6",
        # --- global ---
        "ignored_label": "_Embeddable",
        "cache_ttl": "300",
        "schema_include": "",
        "schema_types": "",
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()
    conn.close()


def get_all_settings():
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def set_multiple_settings(settings: dict):
    conn = get_connection()
    for key, value in settings.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()
    conn.close()
