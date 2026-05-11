"""
SQLite persistence for generated intelligence reports.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

DB_PATH = Path("reports.db")


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id   TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                from_date   TEXT,
                to_date     TEXT,
                trigger     TEXT DEFAULT 'manual',
                status      TEXT DEFAULT 'pending',
                html        TEXT,
                json_data   TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                notified_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at DESC);
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


def create_report(title: str, from_date: str, to_date: str, trigger: str = "manual") -> str:
    report_id = f"RPT{str(uuid4())[:6].upper()}"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO reports (report_id, title, from_date, to_date, trigger) VALUES (?,?,?,?,?)",
            (report_id, title, from_date, to_date, trigger),
        )
    return report_id


def save_report(report_id: str, html: str, json_data: dict, status: str = "completed"):
    with _conn() as conn:
        conn.execute(
            "UPDATE reports SET html=?, json_data=?, status=? WHERE report_id=?",
            (html, json.dumps(json_data, ensure_ascii=False), status, report_id),
        )


def get_report(report_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM reports WHERE report_id=?", (report_id,)).fetchone()
        return dict(row) if row else None


def list_reports(limit: int = 30) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT report_id, title, from_date, to_date, trigger, status, created_at
               FROM reports ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_notified(report_id: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE reports SET notified_at=CURRENT_TIMESTAMP WHERE report_id=?",
            (report_id,),
        )
