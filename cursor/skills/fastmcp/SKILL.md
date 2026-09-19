---
name: fastmcp
description: Implements Python MCP servers with FastMCP. Use when adding or changing MCP tools/resources — not for Node MCP, Lambda, or re-implementing ingest inside tools.
---

# FastMCP

Default stack: Python + FastMCP.

- Use FastMCP, not the low-level MCP SDK. This setup has no Node MCP pack.
- stdio for a local Cursor client. Streamable HTTP for a long-running process. Do not deploy as Lambda or Functions.
- Tools call existing functions. They must not re-implement ingest.
- RAG-backed tools call the pydantic-ai-rag retriever, not a LlamaIndex query engine in the MCP layer.
- If the repo is already FastAPI, mount FastMCP there. Do not create a second process by default.
- App tests: in-process FastMCP client.

## Lint and types

If the repo already has these tools configured, run them. If bootstrapping, add them with the official presets below. Write config in the app repo. Do not add a parallel stack.

- Ruff: defaults plus `I` (isort) and `UP` (pyupgrade). Use Ruff format, not Black.
- Pyright: `typeCheckingMode: "standard"`.
