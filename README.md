# PrismAI Backend

A FastAPI proxy that exposes a single streaming API in front of multiple LLM providers (Anthropic, OpenAI, Gemini), with per-user conversation persistence in Postgres.

- **Live API:** `https://prismai.haris.rip/api/v1/`
- **Interactive docs (Swagger):** [`/api/v1/docs`](https://prismai.haris.rip/api/v1/docs)
- **OpenAPI spec:** [`/api/v1/openapi.json`](https://prismai.haris.rip/api/v1/openapi.json)
- **Endpoint reference:** see [API.md](./API.md)

## What it does

- **Unified chat endpoint** — `POST /chat/{provider}` streams tokens from Anthropic, OpenAI, or Gemini via Server-Sent Events. The same request shape works across all providers.
- **Conversation persistence** — every user message and assistant reply is stored in Postgres so the client doesn't need to maintain chat history. LLMs are stateless; the backend replays prior messages on each turn.
- **Automatic title generation** — on the first exchange of a new conversation, a short title is generated in the background using the same provider.
- **Per-user isolation** — every conversation is scoped to a Firebase user ID; users cannot read or modify each other's data.

## Tech stack

- FastAPI + Uvicorn (ASGI)
- SQLAlchemy 2 (async) + asyncpg
- Postgres on [Neon](https://neon.tech)
- Alembic migrations
- Firebase Admin SDK for ID-token verification
- structlog for structured JSON logging

## Local setup

```bash
git clone git@github.com:Haris0059/prismai-backend.git
cd prismai-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .example.env .env   # then fill in real values
alembic upgrade head
uvicorn app.main:app --reload
```

The dev server listens on `http://127.0.0.1:8000`. To match the production URL shape, hit it at `http://127.0.0.1:8000/...` (no `/api/v1` prefix locally — that prefix is only added by the reverse proxy in production).

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | Async asyncpg URL for runtime, e.g. Neon **pooler** endpoint. Format: `postgresql+asyncpg://user:pass@host/db?ssl=require` |
| `DATABASE_URL_DIRECT` | yes | Direct (non-pooler) URL used by Alembic. PgBouncer cannot run migrations. |
| `ANTHROPIC_API_KEY` | optional | If missing, the Anthropic adapter is skipped at startup. |
| `OPENAI_API_KEY` | optional | If missing, the OpenAI adapter is skipped at startup. |
| `GEMINI_API_KEY` | optional | If missing, the Gemini adapter is skipped at startup. |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | required unless `DEV_AUTH_BYPASS=true` | Filesystem path to the Firebase Admin SDK service account JSON. |
| `DEV_AUTH_BYPASS` | optional | When `true`, all requests are treated as a fixed `dev-user` and Firebase is not initialized. **Local development only.** |

## Database migrations

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
alembic downgrade -1
```

Alembic uses `DATABASE_URL_DIRECT` (the non-pooled endpoint) because PgBouncer in transaction-pooling mode cannot run DDL.

## Project layout

```
app/
  main.py                  # FastAPI app, lifespan, middleware
  api/
    chat.py                # POST /chat/{provider} (SSE streaming)
    conversations.py       # GET/PATCH/DELETE /conversations
  providers/
    base.py                # LLMProvider Protocol + error types
    registry.py            # PROVIDERS dict, built at import time
    anthropic.py
    openai.py
    gemini.py
  db/
    models.py              # Conversation, Message ORM models
    session.py             # async engine + session factory
  core/
    auth.py                # Firebase ID-token verification + bypass
    logging.py             # structlog config + RequestIDMiddleware
    settings.py            # pydantic-settings env loader
  store.py                 # CRUD; routes never construct SQL directly
alembic/                   # migrations
requirements.txt
```

## Deployment

The production instance runs on an Ubuntu VPS via CloudPanel:

- Uvicorn under **systemd** as a dedicated site user, bound to `127.0.0.1:8000`, single worker.
- CloudPanel-managed nginx reverse proxy on `prismai.haris.rip`:
  - Strips the `/api/v1` prefix before forwarding (FastAPI is mounted with `root_path="/api/v1"` so OpenAPI docs reflect the public URL shape).
  - `proxy_buffering off` and `proxy_cache off` so SSE chunks reach the client live.
- Postgres on Neon (pooler endpoint at runtime, direct endpoint for migrations).
- Let's Encrypt TLS managed by CloudPanel; Cloudflare in front of the zone.

Single worker is intentional: the title-generation background task (`asyncio.create_task` in `app/api/chat.py`) is held in an in-process set, so multiple workers would fragment task tracking.

### Access during development

Firebase authentication is part of a later assignment, so this deployment currently runs with `DEV_AUTH_BYPASS=true`. To prevent abuse of the upstream provider API keys, a Cloudflare WAF custom rule blocks every source IP except the developer's machine. `/api/v1/docs` and `/api/v1/openapi.json` are excepted so the API surface remains publicly browsable. The rule is removed when real auth is in place.

## Observability

- `RequestIDMiddleware` (`app/core/logging.py`) attaches a `request_id` to every request's log context.
- Each upstream LLM call logs a `provider_call` event with `latency_ms`, `prompt_tokens`, `completion_tokens`, and `status` (`success` / `error` / `timeout`).
- All logs go to stdout as JSON; in production they are captured by `journalctl -u prismai`.

## Testing

There is no automated test suite yet. The `testing/` directory contains ad-hoc probe scripts (auth fuzz, cross-user authorization, SSE disconnect behavior) intended to be run manually against a running server.

## License

Private — coursework assignment.
