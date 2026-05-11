"""
Chat session + message history storage.
Uses a lightweight SQLite database (no extra infra needed).
Stores per-officer sessions with full message history.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

DB_PATH = Path("chat_history.db")


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                officer_id   TEXT NOT NULL,
                title        TEXT,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT NOT NULL REFERENCES sessions(session_id),
                role         TEXT NOT NULL,         -- 'user' or 'assistant'
                content      TEXT NOT NULL,
                meta_json    TEXT,                  -- confidence, sources, latency etc
                created_at   TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, id);

            CREATE INDEX IF NOT EXISTS idx_sessions_officer
                ON sessions(officer_id, updated_at DESC);
        """)


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ─── Sessions ────────────────────────────────────────────────────────────────

def create_session(officer_id: str, first_message: str) -> str:
    session_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    # Use first 60 chars of first message as session title
    title = first_message[:60] + ("…" if len(first_message) > 60 else "")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, officer_id, title, created_at, updated_at) VALUES (?,?,?,?,?)",
            (session_id, officer_id, title, now, now),
        )
    return session_id


def list_sessions(officer_id: str, limit: int = 30) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT session_id, title, created_at, updated_at
               FROM sessions WHERE officer_id = ?
               ORDER BY updated_at DESC LIMIT ?""",
            (officer_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def touch_session(session_id: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (datetime.utcnow().isoformat(), session_id),
        )


# ─── Messages ────────────────────────────────────────────────────────────────

def add_message(session_id: str, role: str, content: str, meta: dict | None = None):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, meta_json, created_at) VALUES (?,?,?,?,?)",
            (session_id, role, content, json.dumps(meta) if meta else None, datetime.utcnow().isoformat()),
        )
    touch_session(session_id)


def get_messages(session_id: str, limit: int = 50) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content, meta_json, created_at FROM messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    result = []
    for r in rows:
        msg = dict(r)
        if msg["meta_json"]:
            msg["meta"] = json.loads(msg["meta_json"])
        del msg["meta_json"]
        result.append(msg)
    return result


def get_recent_context(session_id: str, max_messages: int = 6) -> list[dict]:
    """Last N messages for LLM context window."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT role, content FROM messages
               WHERE session_id = ?
               ORDER BY id DESC LIMIT ?""",
            (session_id, max_messages),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
