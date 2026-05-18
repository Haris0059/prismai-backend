# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PrismAI Backend — a FastAPI proxy that exposes a unified streaming API in front of multiple LLM providers (Anthropic, OpenAI, Gemini). Persists conversations and messages per user in Postgres (Neon). Firebase ID-token auth is enforced unless `DEV_AUTH_BYPASS=true`.

Entry point is `app/main.py`. FastAPI is constructed with `root_path="/api/v1"` for reverse-proxy deploys — externally-visible paths carry that prefix even though decorators don't.

## Configuration

Copy `.example.env` to `.env`:
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` — missing keys are non-fatal; the adapter is simply skipped at registry-init time (`app/providers/registry.py`).
- `DATABASE_URL` — Neon **pooler** endpoint for runtime, `postgresql+asyncpg://...?ssl=require`.
- `DATABASE_URL_DIRECT` — Neon **direct** endpoint for Alembic (PgBouncer can't run migrations).
- `FIREBASE_SERVICE_ACCOUNT_PATH` — required at startup unless `DEV_AUTH_BYPASS=true`; the lifespan handler in `app/main.py` raises if it's missing.
- `DEV_AUTH_BYPASS` — when true, `get_current_user` returns a fixed `dev-user` and Firebase is not initialized. Local dev only.

## Running

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head           # uses DATABASE_URL_DIRECT
uvicorn app.main:app --reload
```

Deploys must run a **single uvicorn worker** — the in-process `_background_tasks` set used for title generation doesn't survive scale-out.

## Detailed rules (auto-loaded by path)

Detail is split into `.claude/rules/`:

- `endpoints.md` — SSE chat flow, `root_path` prefix, conversation endpoints.
- `database.md` — schema, CRUD conventions, Alembic migrations.
- `providers.md` — adapter Protocol, registry, error normalization, observability.
- `testing.md` — `testing/` probe scripts (no pytest suite).
