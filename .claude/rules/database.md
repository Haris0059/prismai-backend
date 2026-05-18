---
description: Postgres schema, CRUD conventions, and Alembic migrations
paths: ["app/store.py", "app/db/**", "alembic/**", "alembic.ini"]
---

# Database

Postgres on Neon, async SQLAlchemy via asyncpg.

## Schema

- `conversations(id uuid pk, user_id, provider, model, title, created_at, updated_at)` indexed `(user_id, updated_at desc)`.
- `messages(id bigserial pk, conversation_id fk cascade, role, content, created_at)` indexed `(conversation_id, created_at)`.

`gen_random_uuid()` requires `pgcrypto`, created by the initial migration.

## CRUD

Lives in `app/store.py`. Routes never construct SQL directly — go through the store functions.

## Connection URLs

- `DATABASE_URL` — Neon **pooler** endpoint, used at runtime (`postgresql+asyncpg://...?ssl=require`).
- `DATABASE_URL_DIRECT` — Neon **direct** endpoint, used by Alembic. PgBouncer can't run migrations, so this is required.

## Migrations

```bash
alembic revision --autogenerate -m "..."   # uses DATABASE_URL_DIRECT
alembic upgrade head
alembic downgrade -1
```

Autogenerate diffs against the live schema at `DATABASE_URL_DIRECT` — make sure that points at the right branch before running.
