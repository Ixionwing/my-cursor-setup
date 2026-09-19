---
name: pydantic-ai-rag
description: Query-time RAG with Pydantic AI over an existing Postgres/pgvector store. Use when implementing retrieval or answers — not for LlamaIndex ingest, FastAPI CRUD, or graph databases.
---

# Pydantic AI RAG (pgvector)

Default query path: Pydantic AI over the same pgvector tables `llamaindex-ingest` wrote.

- Pydantic AI is the retriever/agent. Do not use LlamaIndex query engines for this path.
- Answers must include source ids or citations from retrieved rows.
- If the app also exposes MCP, this skill owns retrieve/agent behavior; `fastmcp` owns the server wrapper.
- App tests: fixture store. Do not hit the network in unit tests.

## Lint and types

If the repo already has these tools configured, run them. If bootstrapping, add them with the official presets below. Write config in the app repo. Do not add a parallel stack.

- Ruff: defaults plus `I` (isort) and `UP` (pyupgrade). Use Ruff format, not Black.
- Pyright: `typeCheckingMode: "standard"`.
