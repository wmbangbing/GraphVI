import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "presets.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_history_table():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            cypher TEXT NOT NULL,
            type TEXT NOT NULL,
            db_uri TEXT NOT NULL,
            db_name TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def add_history(question: str, cypher: str, type_: str, db_uri: str, db_name: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO query_history (question, cypher, type, db_uri, db_name) VALUES (?, ?, ?, ?, ?)",
        (question, cypher, type_, db_uri, db_name),
    )
    conn.commit()
    conn.close()


def get_history(db_uri: str, db_name: str, limit: int = 50):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM query_history WHERE db_uri = ? AND db_name = ? ORDER BY id DESC LIMIT ?",
        (db_uri, db_name, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_history(history_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM query_history WHERE id = ?", (history_id,))
    conn.commit()
    conn.close()


def clear_history(db_uri: str, db_name: str):
    conn = get_connection()
    conn.execute(
        "DELETE FROM query_history WHERE db_uri = ? AND db_name = ?",
        (db_uri, db_name),
    )
    conn.commit()
    conn.close()
