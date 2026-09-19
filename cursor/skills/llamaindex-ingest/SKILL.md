---
name: llamaindex-ingest
description: Ingests documents into Postgres/pgvector with LlamaIndex. Use when writing or changing the ingest pipeline — not for query-time RAG, FastAPI HTTP, or graph databases.
---

# LlamaIndex ingest (pgvector)

Default store: PostgreSQL + pgvector via LlamaIndex `PGVectorStore`.

- LlamaIndex **writes** the index. It is not the query agent (that is `pydantic-ai-rag`).
- Schema and `CREATE EXTENSION vector` go through `python-db-conventions` (Alembic). Do not add a second ORM.
- Local Docker Postgres is the default runtime. Do not choose serverless Postgres for this path.
- Not PropertyGraph, not Qdrant, not LlamaCloud. Do not require LlamaParse.
- Embeddings: use the app’s configured model if set; otherwise `text-embedding-3-small`. Fail closed if no API key or model is configured. Do not default to `text-embedding-3-large` or a local model.
- Ingest must be idempotent: a re-run must not duplicate chunks.
- App tests: fixture corpus. Do not hit the network in unit tests.

## Lint and types

If the repo already has these tools configured, run them. If bootstrapping, add them with the official presets below. Write config in the app repo. Do not add a parallel stack.

- Ruff: defaults plus `I` (isort) and `UP` (pyupgrade). Use Ruff format, not Black.
- Pyright: `typeCheckingMode: "standard"`.
