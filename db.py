import os
import sqlite3
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
TMP_DIR = Path(os.getenv("TMPDIR", "/tmp"))
DB_PATH = ROOT_DIR / "users.db"
if os.getenv("VERCEL") == "1" or not os.access(ROOT_DIR, os.W_OK):
    DB_PATH = TMP_DIR / "users.db"


def init_db() -> None:
    """Создаёт таблицу для хранения пользователей, которые запустили бота."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS started_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            chat_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def save_started_user(user: Any, chat_id: int | None = None) -> None:
    """Сохраняет пользователя в базу, если он впервые запустил бота."""
    init_db()

    if not user:
        return

    user_id = getattr(user, "id", None)
    if not user_id and isinstance(user, dict):
        user_id = user.get("id")
    if not user_id:
        return

    username = getattr(user, "username", None)
    first_name = getattr(user, "first_name", None)
    last_name = getattr(user, "last_name", None)

    if isinstance(user, dict):
        username = user.get("username")
        first_name = user.get("first_name")
        last_name = user.get("last_name")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO started_users (user_id, username, first_name, last_name, chat_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            chat_id = excluded.chat_id
        """,
        (user_id, username, first_name, last_name, chat_id),
    )
    conn.commit()
    conn.close()


def get_started_users(limit: int = 50) -> list[dict[str, Any]]:
    """Возвращает список сохранённых пользователей."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT user_id, username, first_name, last_name, chat_id, created_at
        FROM started_users
        ORDER BY created_at DESC, user_id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
