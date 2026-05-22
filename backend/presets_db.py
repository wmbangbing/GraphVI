import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "presets.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            cypher TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def get_all():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM presets ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create(question: str, cypher: str | None = None):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO presets (question, cypher) VALUES (?, ?)",
        (question, cypher),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM presets WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)


def update(preset_id: int, question: str | None = None, cypher: str | None = None):
    conn = get_connection()
    fields = []
    values = []
    if question is not None:
        fields.append("question = ?")
        values.append(question)
    if cypher is not None:
        fields.append("cypher = ?")
        values.append(cypher)
    if fields:
        fields.append("updated_at = datetime('now')")
        values.append(preset_id)
        conn.execute(
            f"UPDATE presets SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
    row = conn.execute("SELECT * FROM presets WHERE id = ?", (preset_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete(preset_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
    conn.commit()
    conn.close()
