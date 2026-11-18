"""Serve the ChatSignal prototype and persist chat alerts in SQLite."""

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DB_PATH", str(ROOT / "chatsignal.sqlite3")))
STATIC = ROOT / "static"
QUESTION_RE = re.compile(r"\?|\b(когда|почему|где|как|можете|подскажите)\b", re.I)
PROMISE_RE = re.compile(r"\b(пришлю|отправлю|подготовлю|сделаю|проверю|обновлю|вернусь)\b", re.I)
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def utc_now():
    """Return an ISO timestamp for new records."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    """Open a SQLite connection with dictionary-like rows."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    """Create the schema and seed anonymous demo data once."""
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                context TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                author TEXT NOT NULL CHECK (author IN ('client','team')),
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                message_id INTEGER NOT NULL REFERENCES messages(id),
                kind TEXT NOT NULL CHECK (kind IN ('question','commitment')),
                status TEXT NOT NULL CHECK (status IN ('open','done')),
                due_date TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(message_id, kind)
            );
        """)
        if db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]:
            return
        rows = [
            ("Поддержка игрока", "Запрос о бонусе", [
                ("client", "Здравствуйте! Когда начислится бонус за турнир?")]),
            ("Релиз мобильной игры", "Рабочий чат команды", [
                ("team", "Я пришлю обновлённый билд 2026-11-19")]),
            ("Партнёрская интеграция", "Запуск API", [
                ("client", "Подскажите, тестовый ключ уже готов?"),
                ("team", "Да, отправили ключ в защищённом канале.")]),
        ]
        for title, context, messages in rows:
            cid = db.execute(
                "INSERT INTO conversations(title, context) VALUES (?, ?)",
                (title, context),
            ).lastrowid
            for author, body in messages:
                add_message(db, cid, author, body)


def add_message(db, conversation_id, author, body):
    """Store a message and update the alerts it creates or answers."""
    stamp = utc_now()
    mid = db.execute(
        "INSERT INTO messages(conversation_id, author, text, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, author, body, stamp),
    ).lastrowid
    if author == "team":
        db.execute("""
            UPDATE alerts SET status='done'
            WHERE conversation_id=? AND kind='question' AND status='open'
        """, (conversation_id,))
    if author == "client" and QUESTION_RE.search(body):
        db.execute("""
            INSERT INTO alerts(conversation_id, message_id, kind, status, created_at)
            VALUES (?, ?, 'question', 'open', ?)
        """, (conversation_id, mid, stamp))
    if author == "team" and PROMISE_RE.search(body):
        match = DATE_RE.search(body)
        due_date = match.group() if match else None
        if due_date:
            try:
                date.fromisoformat(due_date)
            except ValueError:
                due_date = None
        db.execute("""
            INSERT INTO alerts(conversation_id, message_id, kind, status, due_date, created_at)
            VALUES (?, ?, 'commitment', 'open', ?, ?)
        """, (conversation_id, mid, due_date, stamp))
    return mid


def state(db):
    """Return the dashboard as a single API response."""
    conversations = [dict(row) for row in db.execute(
        "SELECT * FROM conversations ORDER BY id")]
    messages = [dict(row) for row in db.execute(
        "SELECT * FROM messages ORDER BY id")]
    alerts = [dict(row) for row in db.execute(
        "SELECT * FROM alerts ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END, id DESC")]
    return {"conversations": conversations, "messages": messages, "alerts": alerts}


class Handler(BaseHTTPRequestHandler):
    """Handle static files and the small JSON API."""

    def respond(self, status, payload):
        """Write a JSON response with an HTTP status."""
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        """Read a bounded JSON request body."""
        size = int(self.headers.get("Content-Length", "0"))
        if size < 1 or size > 8192:
            raise ValueError("Размер запроса должен быть от 1 до 8192 байт")
        return json.loads(self.rfile.read(size))

    def do_GET(self):
        """Serve health, dashboard state, and static client assets."""
        path = urlparse(self.path).path
        if path == "/api/health":
            return self.respond(HTTPStatus.OK, {"ok": True})
        if path == "/api/state":
            with connect() as db:
                return self.respond(HTTPStatus.OK, state(db))
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/style.css": ("style.css", "text/css; charset=utf-8")}
        if path not in files:
            return self.respond(HTTPStatus.NOT_FOUND, {"error": "Не найдено"})
        name, content_type = files[path]
        data = (STATIC / name).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        """Add a message to an existing conversation."""
        if urlparse(self.path).path != "/api/messages":
            return self.respond(HTTPStatus.NOT_FOUND, {"error": "Не найдено"})
        try:
            body = self.read_json()
            cid = int(body["conversation_id"])
            author = body["author"]
            content = body["text"].strip()
            if author not in ("client", "team") or not 1 <= len(content) <= 2000:
                raise ValueError("Проверьте автора и текст сообщения")
            with connect() as db:
                if not db.execute("SELECT 1 FROM conversations WHERE id=?", (cid,)).fetchone():
                    return self.respond(HTTPStatus.NOT_FOUND, {"error": "Чат не найден"})
                mid = add_message(db, cid, author, content)
            return self.respond(HTTPStatus.CREATED, {"id": mid})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return self.respond(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_PATCH(self):
        """Mark a detected alert done or reopen it."""
        match = re.fullmatch(r"/api/alerts/(\d+)", urlparse(self.path).path)
        if not match:
            return self.respond(HTTPStatus.NOT_FOUND, {"error": "Не найдено"})
        try:
            body = self.read_json()
            status = body["status"]
            if status not in ("open", "done"):
                raise ValueError("Недопустимый статус")
            with connect() as db:
                cur = db.execute("UPDATE alerts SET status=? WHERE id=?", (status, int(match.group(1))))
                if not cur.rowcount:
                    return self.respond(HTTPStatus.NOT_FOUND, {"error": "Сигнал не найден"})
            return self.respond(HTTPStatus.OK, {"ok": True})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return self.respond(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


if __name__ == "__main__":
    initialize()
    port = int(os.environ.get("PORT", "8008"))
    print(f"ChatSignal listening on http://localhost:{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
