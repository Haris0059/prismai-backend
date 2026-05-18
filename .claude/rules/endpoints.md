---
description: API surface, SSE chat flow, and routing conventions
paths: ["app/api/**", "app/main.py"]
---

# Endpoints

FastAPI is constructed with `root_path="/api/v1"` for reverse-proxy deploys, so externally-visible paths are `/api/v1/chat/{provider}`, `/api/v1/conversations`, etc. Route decorators in the code are written without that prefix.

Lifespan in `app/main.py` initializes Firebase, middleware adds a per-request ID, then two routers are mounted: `app/api/chat.py` and `app/api/conversations.py`.

## `POST /chat/{provider}` — SSE-streaming, not JSON

Flow:
1. Resolve user via `get_current_user` (Firebase or bypass).
2. Either create a new `Conversation` row (no `conversation_id` in body) or load the existing one + all prior messages and replay them — LLMs are stateless, the backend is the source of truth.
3. Append the user message and commit *before* opening the upstream stream.
4. Open a `StreamingResponse` that emits:
   - First event: `{"conversation_id": "..."}` so the client can correlate before any tokens arrive.
   - Then `{"text": "..."}` events per chunk yielded by `adapter.stream()`.
   - Final `[DONE]` sentinel.
5. After the stream closes, the accumulated assistant text is persisted in a fresh DB session (the original session is long-closed by then), and `updated_at` is bumped.
6. On the **first** exchange only, an `asyncio.create_task` fires `_generate_title` — asks the same provider for a ≤6-word title and updates `conversations.title`. Task handles are kept in a module-level set (`_background_tasks`) so the GC doesn't collect mid-flight; this is best-effort and will be lost on process restart. Because the set is in-process, deploys must run a **single uvicorn worker** (or move to a real job queue) — otherwise scale-out drops in-flight title generations.

Provider errors in the streaming path are emitted as `{"error": ...}` SSE events, not HTTP status codes — the response is already committed by the time upstream fails. See [providers rule](providers.md) for the error taxonomy.

## Other endpoints

- `GET /conversations` — current user's conversations, newest `updated_at` first.
- `GET /conversations/{id}` — metadata + ordered messages.
- `PATCH /conversations/{id}` — body `{title}` for manual rename.
- `DELETE /conversations/{id}` — cascades to messages.
