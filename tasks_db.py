"""
タスクの永続化を担当するモジュール。
SQLiteはファイル1つで完結して、EC2再起動やBot再起動でもデータが消えないので採用。
接続はリクエストのたびに開いて閉じる(Botの利用規模ならこれで十分軽い)。
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import NamedTuple

import config


class Task(NamedTuple):
    id: int
    description: str
    created_at: str


@contextmanager
def _connect():
    conn = sqlite3.connect(config.DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def add_task(description: str) -> Task:
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (description, created_at) VALUES (?, ?)",
            (description, now),
        )
        return Task(id=cur.lastrowid, description=description, created_at=now)


def remove_task(task_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cur.rowcount > 0


def list_tasks() -> list[Task]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, description, created_at FROM tasks ORDER BY id ASC"
        ).fetchall()
        return [Task(*row) for row in rows]
