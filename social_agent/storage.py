"""SQLite store; every query is tenant-scoped and parameterized."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=10000")
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    memory_enabled INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_user_thread
                    ON messages(user_id, thread_id, id);
                CREATE TABLE IF NOT EXISTS memories (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, key),
                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );
            """)

    def ensure_user(self, user_id: str) -> None:
        with self._connect() as con:
            con.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (user_id,))

    def consent(self, user_id: str) -> bool:
        with self._connect() as con:
            row = con.execute("SELECT memory_enabled FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["memory_enabled"])

    def set_consent(self, user_id: str, enabled: bool) -> None:
        self.ensure_user(user_id)
        with self._connect() as con:
            con.execute("UPDATE users SET memory_enabled=? WHERE user_id=?", (int(enabled), user_id))
            if not enabled:
                con.execute("DELETE FROM memories WHERE user_id=?", (user_id,))

    def save_message(self, user_id: str, thread_id: str, role: str, content: str) -> None:
        self.ensure_user(user_id)
        if role not in {"user", "assistant"}:
            raise ValueError("Invalid message role")
        with self._connect() as con:
            con.execute(
                "INSERT INTO messages(user_id,thread_id,role,content,created_at) VALUES (?,?,?,?,?)",
                (user_id, thread_id, role, content, utc_now()),
            )

    def recent_messages(self, user_id: str, thread_id: str, limit: int) -> list[dict]:
        if limit <= 0:
            return []
        with self._connect() as con:
            rows = con.execute(
                "SELECT role, content FROM messages WHERE user_id=? AND thread_id=? "
                "ORDER BY id DESC LIMIT ?",
                (user_id, thread_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def write_memory(self, user_id: str, key: str, value: str) -> bool:
        if not self.consent(user_id):
            return False
        with self._connect() as con:
            con.execute(
                "INSERT INTO memories(user_id,key,value,updated_at) VALUES (?,?,?,?) "
                "ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (user_id, key, value, utc_now()),
            )
        return True

    def memories(self, user_id: str) -> list[dict]:
        if not self.consent(user_id):
            return []
        with self._connect() as con:
            rows = con.execute(
                "SELECT key,value,updated_at FROM memories WHERE user_id=? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_memory(self, user_id: str, key: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM memories WHERE user_id=? AND key=?", (user_id, key))

    def delete_user(self, user_id: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM users WHERE user_id=?", (user_id,))

    def message_count(self, user_id: str, thread_id: str) -> int:
        with self._connect() as con:
            row = con.execute(
                "SELECT count(*) AS n FROM messages WHERE user_id=? AND thread_id=?",
                (user_id, thread_id),
            ).fetchone()
        return int(row["n"])
