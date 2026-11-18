"""Check alert lifecycle and persistence in an isolated SQLite database."""

import tempfile
import unittest
from pathlib import Path

import app


class AlertLifecycleTest(unittest.TestCase):
    """Exercise the main user path against real SQLite storage."""

    def test_question_reply_and_commitment(self):
        """Close a client question on reply and keep a separate promise open."""
        with tempfile.TemporaryDirectory() as directory:
            original = app.DB_PATH
            app.DB_PATH = Path(directory) / "test.sqlite3"
            try:
                app.initialize()
                with app.connect() as db:
                    app.add_message(db, 1, "client", "Когда будет ответ по заявке?")
                    open_questions = [item for item in app.state(db)["alerts"]
                                      if item["conversation_id"] == 1 and item["kind"] == "question"
                                      and item["status"] == "open"]
                    self.assertEqual(len(open_questions), 2)
                    app.add_message(db, 1, "team", "Отвечаю сейчас. Пришлю детали 2026-11-19")
                    current = [item for item in app.state(db)["alerts"]
                               if item["conversation_id"] == 1]
                    self.assertFalse(any(item["kind"] == "question" and item["status"] == "open"
                                         for item in current))
                    self.assertTrue(any(item["kind"] == "commitment" and item["status"] == "open"
                                        and item["due_date"] == "2026-11-19" for item in current))
                with app.connect() as db:
                    self.assertEqual(len(app.state(db)["messages"]), 6)
            finally:
                app.DB_PATH = original


if __name__ == "__main__":
    unittest.main()
