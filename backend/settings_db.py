import sqlite3
import os

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
