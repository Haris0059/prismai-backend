# PrismAI Backend — API Reference

## Overview

PrismAI Backend is a streaming proxy in front of multiple LLM providers. It exposes a single chat endpoint that fans out to Anthropic, OpenAI, or Gemini, plus a small set of conversation-management endpoints.

- **Base URL:** `https://prismai.haris.rip/api/v1`
- **Interactive docs:** [`/api/v1/docs`](https://prismai.haris.rip/api/v1/docs)
- **OpenAPI spec:** [`/api/v1/openapi.json`](https://prismai.haris.rip/api/v1/openapi.json)
- **Response format:** JSON for every endpoint **except** `POST /chat/{provider}`, which returns `text/event-stream` (SSE).
- **Rate limits:** none enforced at the application layer.

---

## Authentication

Every endpoint requires a Firebase ID token in the `Authorization` header:

```
Authorization: Bearer <firebase-id-token>
```

The token is verified server-side via the Firebase Admin SDK. On success, the decoded `uid` is used as the owner of every read/write — users only see their own conversations.

### Obtaining a token

Firebase ID tokens are produced by your client SDK (web, Android, iOS) after a user signs in. They are short-lived (~1 hour). The client is responsible for refreshing them.

### Errors

| Code | Cause |
|---|---|
| 401 `Missing authentication credentials` | No `Authorization` header was sent. |
| 401 `Invalid authentication credentials` | Token signature invalid, expired, revoked, or user disabled. |

### Development mode

When the server is started with `DEV_AUTH_BYPASS=true`, the `Authorization` header is ignored and every request is processed as a fixed `dev-user`. This is for local development only and is never enabled in production once Firebase auth is in place.

---

## Quick start

```bash
# 1. List your conversations (replace TOKEN with a real Firebase ID token)
curl -sS https://prismai.haris.rip/api/v1/conversations \
  -H "Authorization: Bearer TOKEN"

# 2. Start a new chat (SSE stream)
curl -N https://prismai.haris.rip/api/v1/chat/openai \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","message":"Hello in three words"}'
```

The second call streams the response token-by-token. The first event contains the new `conversation_id`; subsequent events contain `text` chunks; a final `[DONE]` sentinel closes the stream.

---

## Endpoints

### `POST /chat/{provider}`

Send a user message and stream the assistant's response. Creates a new conversation if no `conversation_id` is given; otherwise appends to the existing one.

**Path parameters:**

| Name | Type | Description |
|---|---|---|
| `provider` | string | One of `anthropic`, `openai`, `gemini`. Providers without a configured API key are unavailable. |

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `model` | string | yes | Provider-specific model identifier, e.g. `gpt-4o-mini`, `claude-haiku-4-5-20251001`, `gemini-1.5-pro`. |
| `message` | string | yes | The user message. 1–32 000 characters. |
| `conversation_id` | uuid | no | Append to an existing conversation. Omit to start a new one. The conversation must belong to the authenticated user. |

**Request example:**

```bash
curl -N -X POST https://prismai.haris.rip/api/v1/chat/openai \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "message": "Write a haiku about caching."
  }'
```

**Response — Server-Sent Events (`text/event-stream`):**

Each line is an SSE `data:` frame. Frames arrive in this order:

```
data: {"conversation_id": "0e85cd96-1897-439c-b96a-9ccdead5214b"}

data: {"text": "Silent"}

data: {"text": " bytes"}

data: {"text": " in"}

data: {"text": " RAM"}

data: [DONE]
```

| Event | Meaning |
|---|---|
| `{"conversation_id": "<uuid>"}` | Always the first event. Lets the client correlate a streaming request to its conversation before any tokens arrive. For an existing conversation this echoes the `conversation_id` from the request body. |
| `{"text": "<chunk>"}` | One delta token (or short run of tokens, depending on provider). Concatenate all `text` fields in order to reconstruct the full assistant reply. |
| `{"error": "<message>"}` | An upstream or internal error occurred mid-stream. No further frames will be sent. |
| `[DONE]` | The stream ended successfully. Always the final frame on a successful response. |

**Persistence:** the user message is saved before the upstream call; the assistant reply is saved after the stream closes. If the client disconnects mid-stream, the partial reply received so far is **not** persisted.

**HTTP status codes:**

| Code | Cause |
|---|---|
| 200 | Stream opened (errors during streaming arrive as SSE `error` events, not HTTP errors — the response is already committed). |
| 400 | Unknown provider, malformed body, or message length out of range. |
| 401 | Missing/invalid authentication. |
| 404 | `conversation_id` does not exist or does not belong to the caller. |
| 422 | Pydantic validation failure (e.g. `model` is not a string). |

---

### `GET /conversations`

List the authenticated user's conversations, newest activity first.

**Request example:**

```bash
curl -sS https://prismai.haris.rip/api/v1/conversations \
  -H "Authorization: Bearer TOKEN"
```

**Response (`application/json`):**

```json
[
  {
    "id": "0e85cd96-1897-439c-b96a-9ccdead5214b",
    "title": "Haiku about caching",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "updated_at": "2026-05-17T14:36:50.437390+00:00"
  },
  {
    "id": "a62e8f44-be25-4498-81bd-2a2dd95568fb",
    "title": "New chat",
    "provider": "anthropic",
    "model": "claude-haiku-4-5-20251001",
    "updated_at": "2026-05-16T09:12:04.001000+00:00"
  }
]
```

**HTTP status codes:**

| Code | Cause |
|---|---|
| 200 | Success (an empty array is returned if the user has no conversations). |
| 401 | Missing/invalid authentication. |

---

### `GET /conversations/{conversation_id}`

Retrieve a single conversation with all of its messages in chronological order.

**Path parameters:**

| Name | Type | Description |
|---|---|---|
| `conversation_id` | uuid | Identifier returned by `POST /chat/{provider}` or `GET /conversations`. |

**Request example:**

```bash
curl -sS https://prismai.haris.rip/api/v1/conversations/0e85cd96-1897-439c-b96a-9ccdead5214b \
  -H "Authorization: Bearer TOKEN"
```

**Response (`application/json`):**

```json
{
  "id": "0e85cd96-1897-439c-b96a-9ccdead5214b",
  "title": "Haiku about caching",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "created_at": "2026-05-17T14:36:43.000000+00:00",
  "updated_at": "2026-05-17T14:36:50.437390+00:00",
  "messages": [
    {
      "role": "user",
      "content": "Write a haiku about caching.",
      "created_at": "2026-05-17T14:36:43.500000+00:00"
    },
    {
      "role": "assistant",
      "content": "Silent bytes in RAM\nWhispering yesterday's truth\nUntil TTL fades",
      "created_at": "2026-05-17T14:36:50.430000+00:00"
    }
  ]
}
```

**HTTP status codes:**

| Code | Cause |
|---|---|
| 200 | Success. |
| 401 | Missing/invalid authentication. |
| 404 | Conversation does not exist or belongs to another user. |
| 422 | `conversation_id` is not a valid UUID. |

---

### `PATCH /conversations/{conversation_id}`

Rename a conversation. The title generated automatically after the first exchange can be overwritten with this endpoint at any time.

**Path parameters:**

| Name | Type | Description |
|---|---|---|
| `conversation_id` | uuid | The conversation to rename. |

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string | yes | New title. 1–200 characters. |

**Request example:**

```bash
curl -sS -X PATCH https://prismai.haris.rip/api/v1/conversations/0e85cd96-1897-439c-b96a-9ccdead5214b \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Caching poetry"}'
```

**Response (`application/json`):**

```json
{
  "id": "0e85cd96-1897-439c-b96a-9ccdead5214b",
  "title": "Caching poetry"
}
```

**HTTP status codes:**

| Code | Cause |
|---|---|
| 200 | Renamed. |
| 401 | Missing/invalid authentication. |
| 404 | Conversation not found or owned by another user. |
| 422 | `title` empty, missing, or longer than 200 characters. |

---

### `DELETE /conversations/{conversation_id}`

Permanently delete a conversation and all of its messages. Cascades at the database level.

**Path parameters:**

| Name | Type | Description |
|---|---|---|
| `conversation_id` | uuid | The conversation to delete. |

**Request example:**

```bash
curl -sS -X DELETE https://prismai.haris.rip/api/v1/conversations/0e85cd96-1897-439c-b96a-9ccdead5214b \
  -H "Authorization: Bearer TOKEN"
```

**Response (`application/json`):**

```json
{
  "deleted": true
}
```

**HTTP status codes:**

| Code | Cause |
|---|---|
| 200 | Deleted. |
| 401 | Missing/invalid authentication. |
| 404 | Conversation not found or owned by another user. |

---

## Error reference

### Standard JSON endpoints

| HTTP code | When it happens | What to do |
|---|---|---|
| 400 | Unknown provider in `POST /chat/{provider}`, or malformed request body. | Check the provider name and request shape against this reference. |
| 401 | `Authorization` header missing, or the Firebase token is invalid/expired/revoked. | Acquire a fresh token from your client SDK and retry. |
| 404 | The requested `conversation_id` does not exist, or it belongs to a different user. | Verify the ID. Cross-user access returns 404 by design (no information leak). |
| 422 | Pydantic validation failed: missing field, wrong type, value outside allowed bounds. | Inspect the `detail` array in the response — it lists each invalid field. |
| 500 | Unhandled server error. | Retry. If persistent, check server logs (`journalctl -u prismai`). |

### Errors during SSE streaming

Once `POST /chat/{provider}` begins streaming (HTTP 200 sent), upstream failures cannot change the HTTP status. They are surfaced as SSE `data: {"error": "..."}` frames instead. Common cases:

| Error message (substring) | Underlying cause |
|---|---|
| `Rate limited` | The upstream provider returned 429. Back off and retry. |
| `Bad request` | The upstream provider rejected the body (e.g. unknown model id, invalid role sequence). |
| `Timeout` | The upstream provider did not respond within the configured connect timeout. |
| `Upstream error` | The upstream provider returned 5xx. |
| `Internal server error` | Unexpected exception in the proxy itself. Check server logs. |

After any `error` frame, no further `text` frames will arrive and no `[DONE]` sentinel will be sent.

---

## Conventions

- **Timestamps** are ISO 8601 with explicit UTC offset (`+00:00`).
- **UUIDs** are RFC 4122 v4, lowercase.
- **Roles** in stored messages are exactly `user` or `assistant`. The backend currently does not handle `system` messages.
- **Provider mid-conversation switch:** because Anthropic and OpenAI both accept the same `{role, content}` shape, a single conversation can switch model or provider between turns. Gemini's adapter rewrites roles internally, so a conversation that started on OpenAI/Anthropic will replay correctly on Gemini.
