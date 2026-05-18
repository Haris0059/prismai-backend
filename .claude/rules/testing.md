---
description: Manual probe scripts; there is no pytest suite
paths: ["testing/**"]
---

# Testing

There is **no `pytest` suite**. The `testing/` directory contains ad-hoc probe scripts used for manual security/behavior probing against a running server:

- `auth_fuzz.py` — auth-header fuzzing.
- `authz_cross_user.py` — cross-user authorization checks.
- `sse_disconnect.py` — client-disconnect handling on the SSE stream.
- `run_probes.sh` — orchestrates the above.

Run them against a local `uvicorn` instance (`uvicorn app.main:app --reload`), not in CI.

If you add a real test framework, prefer `pytest-asyncio` for the async stack and keep these probe scripts separate — they're integration smoke tests, not unit tests.
