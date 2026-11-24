"""SQLite database layer — stdlib sqlite3, async via run_in_executor."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from . import config

_connection: sqlite3.Connection | None = None


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _get_db_path() -> str:
    return config.settings.db_path


def get_connection() -> sqlite3.Connection:
    """Return (and cache) a long-lived connection with WAL mode enabled."""
    global _connection
    if _connection is not None:
        return _connection

    db_path = _get_db_path()
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _connection = conn
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables and indices if they don't already exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            system_prompt TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, id);
        """
    )
    conn.commit()


def check_db() -> bool:
    """Return True if the database is reachable."""
    try:
        get_connection().execute("SELECT 1")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_session(session_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT session_id, system_prompt, created_at FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def create_session(session_id: str, system_prompt: str | None) -> dict[str, Any]:
    conn = get_connection()
    now = _now_iso()
    conn.execute(
        "INSERT INTO sessions (session_id, system_prompt, created_at) VALUES (?, ?, ?)",
        (session_id, system_prompt, now),
    )
    conn.commit()
    return {"session_id": session_id, "system_prompt": system_prompt, "created_at": now}


def update_session_system_prompt(session_id: str, system_prompt: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET system_prompt = ? WHERE session_id = ?",
        (system_prompt, session_id),
    )
    conn.commit()


def get_messages(session_id: str) -> list[dict[str, Any]]:
    """Return messages for a session, oldest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content, metadata FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for r in rows:
        entry: dict[str, Any] = {"role": r["role"], "content": r["content"]}
        if r["role"] == "assistant" and r["metadata"]:
            entry["metadata"] = json.loads(r["metadata"])
        result.append(entry)
    return result


def get_history_for_llm(session_id: str, system_prompt: str, max_messages: int) -> list[dict[str, str]]:
    """Build the LLM messages list: system + last N messages (no metadata)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    history = [{"role": r["role"], "content": r["content"]} for r in rows]
    # Cap at max_messages (keeping the most recent)
    if len(history) > max_messages:
        history = history[-max_messages:]
    messages = [{"role": "system", "content": system_prompt}] + history
    return messages


def save_exchange(
    session_id: str,
    user_content: str,
    assistant_content: str,
    metadata: dict[str, Any],
) -> None:
    """Persist user + assistant messages in a single transaction."""
    conn = get_connection()
    now = _now_iso()
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, "user", user_content, None, now),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, "assistant", assistant_content, json.dumps(metadata), now),
        )
        conn.commit()
        # Flush WAL pages to main db file so visual SQLite viewers see updates immediately
        try:
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass
    except Exception:
        conn.rollback()
        raise


def close_connection() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
