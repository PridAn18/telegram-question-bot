import os
import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


class Database:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE
                );

                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY,
                    category_id INTEGER,
                    question TEXT,
                    answer TEXT,
                    is_active INTEGER DEFAULT 1,
                    UNIQUE (category_id, question)
                );

                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    selected_category INTEGER,
                    created_at DATETIME,
                    last_activity DATETIME
                );

                CREATE TABLE IF NOT EXISTS user_progress (
                    user_id INTEGER,
                    question_id INTEGER,
                    shown_at DATETIME,
                    PRIMARY KEY (user_id, question_id)
                );
                """
            )

    def register_user(self, user_id: int, username, first_name) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO users
                    (user_id, username, first_name, created_at, last_activity)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, first_name, now, now),
            )

    def touch_user(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET last_activity = ? WHERE user_id = ?",
                (_now(), user_id),
            )

    def get_or_create_category(self, name: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM categories WHERE name = ?", (name,)
            ).fetchone()
            if row:
                return row["id"]
            cursor = conn.execute(
                "INSERT INTO categories (name) VALUES (?)", (name,)
            )
            return cursor.lastrowid

    def add_question(self, category_id: int, question: str, answer: str) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO questions (category_id, question, answer, is_active) "
                    "VALUES (?, ?, ?, 1)",
                    (category_id, question, answer),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def export_rows(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.name AS category, q.question, q.answer
                FROM questions q
                JOIN categories c ON c.id = q.category_id
                WHERE q.is_active = 1
                ORDER BY c.name, q.id
                """
            ).fetchall()
        return [(row["category"], row["question"], row["answer"]) for row in rows]

    def count_questions(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM questions").fetchone()["n"]

    def count_categories(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"]

    def count_users(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]

    def db_size(self) -> int:
        return os.path.getsize(self.path) if os.path.exists(self.path) else 0