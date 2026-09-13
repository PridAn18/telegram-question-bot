from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


class QuestionService:
    def __init__(self, db):
        self.db = db

    def get_next_question(self, user_id: int):
        with self.db._connect() as conn:
            selected = conn.execute(
                "SELECT selected_category FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            category_id = selected["selected_category"] if selected else None

            active_count = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM questions
                WHERE is_active = 1 AND (? IS NULL OR category_id = ?)
                """,
                (category_id, category_id),
            ).fetchone()["n"]

            seen_count = conn.execute(
                "SELECT COUNT(*) AS n FROM user_progress WHERE user_id = ?",
                (user_id,),
            ).fetchone()["n"]

            if active_count and seen_count >= active_count:
                conn.execute(
                    "DELETE FROM user_progress WHERE user_id = ?", (user_id,)
                )

            row = conn.execute(
                """
                SELECT q.id, q.question, q.answer, c.name AS category
                FROM questions q
                LEFT JOIN categories c ON c.id = q.category_id
                WHERE q.is_active = 1
                  AND (? IS NULL OR q.category_id = ?)
                  AND q.id NOT IN (
                      SELECT question_id FROM user_progress WHERE user_id = ?
                  )
                ORDER BY RANDOM()
                LIMIT 1
                """,
                (category_id, category_id, user_id),
            ).fetchone()

        if row is None:
            return None
        return dict(row)

    def mark_answered(self, user_id: int, question_id: int) -> None:
        with self.db._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO user_progress (user_id, question_id, shown_at)
                VALUES (?, ?, ?)
                """,
                (user_id, question_id, _now()),
            )