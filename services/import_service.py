import csv
import io


class ImportService:
    def __init__(self, db):
        self.db = db

    def import_bytes(self, data: bytes) -> dict:
        text = data.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        new_categories = set()
        new_questions = 0
        duplicates = 0

        for row in reader:
            category = (row.get("category") or "").strip()
            question = (row.get("question") or "").strip()
            answer = (row.get("answer") or "").strip()
            if not category or not question or not answer:
                continue
            category_id = self.db.get_or_create_category(category)
            new_categories.add(category)
            if self.db.add_question(category_id, question, answer):
                new_questions += 1
            else:
                duplicates += 1

        return {
            "categories_added": len(new_categories),
            "questions_added": new_questions,
            "duplicates": duplicates,
        }