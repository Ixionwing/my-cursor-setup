---
name: python-api-conventions
description: Implements and reviews Python HTTP APIs with FastAPI. Use for FastAPI/Python services — not for React UI or Node.
---

# Python API conventions

Default stack: Python + FastAPI.

- Type request/response models with Pydantic. Return HTTPException for 4xx; let unhandled errors become 500 without leaking internals.
- Depend on `Depends()` for DB/session/auth. Do not create ad-hoc globals in request handlers.
- Tests: `TestClient` (or equivalent) for status and payload. Isolate DB with fixtures.
- Layout: package modules (`routers/`, `models/`), not notebooks and not frontend trees.

## Lint and types

If the repo already has these tools configured, run them. If bootstrapping, add them with the official presets below. Write config in the app repo. Do not add a parallel stack.

- Ruff: defaults plus `I` (isort) and `UP` (pyupgrade). Use Ruff format, not Black.
- Pyright: `typeCheckingMode: "standard"`.
