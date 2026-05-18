---
description: LLM provider adapter Protocol, registry, and error normalization
paths: ["app/providers/**"]
---

# Providers

Each adapter in `app/providers/` exposes two methods:
- `complete(model, messages) -> (raw, text)`
- `stream(model, messages) -> AsyncIterator[str]`

The shape is declared as a `Protocol` in `app/providers/base.py`. `registry.py` instantiates adapters at import time and stores them in `PROVIDERS: dict[str, LLMProvider]`. Missing API keys are non-fatal — the adapter is simply skipped at registry-init.

**Adding a provider** = new adapter class + one entry in `registry.py`.

## Message shape

Anthropic and OpenAI both consume `[{role, content}]` with roles `user`/`assistant`, so the stored message shape works for both and a conversation can switch model/provider mid-thread.

**Gemini** is different — its adapter transforms `assistant` → `model` and wraps content in `parts`.

None of the adapters currently handle `system` messages correctly:
- Anthropic needs a top-level `system` field.
- Gemini uses `systemInstruction`.

Keep this in mind before introducing system prompts.

## Error normalization

Provider errors are normalized via `app/providers/base.py`:

| Exception | Maps to |
|-----------|---------|
| `RateLimited` | 429 |
| `BadRequest` | 4xx |
| `ProviderTimeout` | 504 |
| `UpstreamError` | 5xx |

In the SSE streaming path these are caught and emitted as `{"error": ...}` events rather than HTTP status codes — the response is already committed by the time upstream fails.

## Observability

Provider adapters log a `provider_call` event on every call with fields: `provider`, `model`, `latency_ms`, `prompt_tokens`, `completion_tokens`, and `status` (`success`/`error`/`timeout`). Structlog is configured in `app/core/logging.py`; `RequestIDMiddleware` adds `request_id` to the log context.
