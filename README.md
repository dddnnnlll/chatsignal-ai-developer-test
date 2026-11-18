# ChatSignal

Small client-server prototype for tracking unanswered questions and unfulfilled commitments in work chats. It was built with an AI coding assistant as requested in the practical assignment. The app itself uses transparent, deterministic rules, so the demo works without API keys or external AI services.

## Run

```bash
python app.py
```

Open `http://localhost:8008`. Set `PORT` for another port and `DB_PATH` for another database file. Python 3.11+ is enough. No packages or build step are required.

## What to try

1. Select an existing conversation and inspect its alert and source message.
2. Add a client question to a conversation; an unanswered-question alert appears.
3. Add a team reply; the question alert closes automatically.
4. Add a promise with a date, for example `Я пришлю отчёт 2026-11-19`; a commitment alert appears.
5. Mark an alert done; refresh the page to confirm persistence.

## API

- `GET /api/health`
- `GET /api/state`
- `POST /api/messages` with `{"conversation_id":1,"author":"client","text":"Когда будет ответ?"}`
- `PATCH /api/alerts/{id}` with `{"status":"done"}` or `{"status":"open"}`

`app.py` contains the backend and rule engine. `static/` contains the browser client. The SQLite database is created automatically and seeded with anonymous synthetic conversations.

## Scope and limitations

This prototype demonstrates the client-server flow and reviewable alert lifecycle. Its rule engine is deliberately simple; production quality would require an evaluated local LLM, human review of low-confidence cases, account-scoped authorization, Telegram MTProto ingestion, encryption, and monitoring. No real chat data are included.

## Hosted demo

`render.yaml` defines a free Render web service for this repository. The application already binds to `0.0.0.0` and reads Render's `PORT` environment variable. The free service can sleep when idle and its SQLite database is ephemeral, so demo edits may reset after a restart. The initial synthetic conversations are seeded again automatically.

See `INITIAL_PROMPT.md` and `AI_USAGE.md` for the required AI development record.
