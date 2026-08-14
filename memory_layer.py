"""
AUBIEETERNAL — Persistent Memory Layer
File: /home/aubieeternal/AUBIEETERNAL/memory_layer.py

Drop this file next to assistant_server.py and import from it.
On first run it creates ~/aubie_storage/conversations/debug_memory.db
automatically.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / "aubie_storage" / "conversations" / "debug_memory.db"


# ─── DB init ──────────────────────────────────────────────────────────────────

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS crash_log (
            id          INTEGER PRIMARY KEY,
            timestamp   TEXT    NOT NULL,
            source_file TEXT,
            error_text  TEXT,
            root_cause  TEXT,
            fix_applied TEXT,
            resolved    BOOLEAN DEFAULT 0
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS hardware_log (
            id                 INTEGER PRIMARY KEY,
            timestamp          TEXT NOT NULL,
            device_name        TEXT,
            vendor_id          TEXT,
            product_id         TEXT,
            integration_notes  TEXT,
            code_location      TEXT
        )
    """)
    # Session memory: one row per turn, scoped by session_id
    con.execute("""
        CREATE TABLE IF NOT EXISTS session_memory (
            id         INTEGER PRIMARY KEY,
            session_id TEXT    NOT NULL,
            timestamp  TEXT    NOT NULL,
            role       TEXT    NOT NULL,   -- 'user' or 'assistant'
            content    TEXT    NOT NULL
        )
    """)
    con.commit()
    con.close()


# ─── Crash log helpers ────────────────────────────────────────────────────────

def log_crash(source_file: str, error_text: str) -> int:
    """Insert a new crash entry; returns its id."""
    con = sqlite3.connect(DB_PATH)
    cur = con.execute(
        "INSERT INTO crash_log (timestamp, source_file, error_text) VALUES (?,?,?)",
        (datetime.utcnow().isoformat(), source_file, error_text)
    )
    con.commit()
    row_id = cur.lastrowid
    con.close()
    return row_id


def find_similar_crashes(error_text: str, limit: int = 3) -> list[dict]:
    """Return up to `limit` past crashes whose error_text overlaps the current one."""
    # Simple keyword overlap — upgrade to FTS5 or Chroma later if needed
    keywords = [w for w in error_text.split() if len(w) > 5][:10]
    if not keywords:
        return []
    placeholders = " OR ".join(["error_text LIKE ?" for _ in keywords])
    params = [f"%{k}%" for k in keywords]
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        f"SELECT * FROM crash_log WHERE ({placeholders}) ORDER BY timestamp DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def resolve_crash(crash_id: int, root_cause: str, fix_applied: str):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "UPDATE crash_log SET root_cause=?, fix_applied=?, resolved=1 WHERE id=?",
        (root_cause, fix_applied, crash_id)
    )
    con.commit()
    con.close()


# ─── Hardware log helpers ─────────────────────────────────────────────────────

def log_hardware(device_name: str, vendor_id: str, product_id: str,
                 integration_notes: str = "", code_location: str = "") -> int:
    con = sqlite3.connect(DB_PATH)
    cur = con.execute(
        """INSERT INTO hardware_log
           (timestamp, device_name, vendor_id, product_id, integration_notes, code_location)
           VALUES (?,?,?,?,?,?)""",
        (datetime.utcnow().isoformat(), device_name, vendor_id,
         product_id, integration_notes, code_location)
    )
    con.commit()
    row_id = cur.lastrowid
    con.close()
    return row_id


def find_hardware(vendor_id: str = "", product_id: str = "") -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM hardware_log WHERE vendor_id=? OR product_id=? ORDER BY timestamp DESC",
        (vendor_id, product_id)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


# ─── Session memory helpers ───────────────────────────────────────────────────

def append_turn(session_id: str, role: str, content: str):
    """Add one turn (user or assistant) to session history."""
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO session_memory (session_id, timestamp, role, content) VALUES (?,?,?,?)",
        (session_id, datetime.utcnow().isoformat(), role, content)
    )
    con.commit()
    con.close()


def get_history(session_id: str, max_turns: int = 20) -> list[dict]:
    """
    Return the last `max_turns` messages as a list of {role, content} dicts,
    ready to drop straight into an Ollama messages list.
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """SELECT role, content FROM session_memory
           WHERE session_id=?
           ORDER BY timestamp DESC LIMIT ?""",
        (session_id, max_turns)
    ).fetchall()
    con.close()
    # reverse so oldest first
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_session(session_id: str):
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM session_memory WHERE session_id=?", (session_id,))
    con.commit()
    con.close()


# ─── Auto-init on import ──────────────────────────────────────────────────────
init_db()
