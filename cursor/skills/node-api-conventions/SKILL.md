---
name: node-api-conventions
description: Implements and reviews Node HTTP APIs with Express. Use for Express/Node service routes, middleware, validation, and API tests — not for React UI or Python.
---

# Node API conventions

Default stack: Node.js + Express.

- One router per resource. Keep handlers small; put domain logic in modules the router calls.
- Validate request bodies before use. Return 400 on schema failure, 404 when a resource is missing, 500 only for unexpected errors. Do not leak stack traces in responses.
- Use `async` handlers and a single Express error middleware. Do not swallow rejections.
- Tests: hit the HTTP layer (supertest or equivalent) for status codes and JSON shape. Prefer test DB or in-memory fakes over live prod.
- Layout: `src/` (or project equivalent) with `routes/`, not mixed into frontend `app/` or `components/`.

## Lint and types

If the repo already has these tools configured, run them. If bootstrapping, add them with the official presets below. Write config in the app repo. Do not add a parallel stack.

- ESLint: `eslint:recommended` plus `typescript-eslint` recommended when the project is TypeScript. Do not add the React Hooks plugin here.
- Prettier: defaults. Use `eslint-config-prettier` so ESLint does not fight Prettier.
- TypeScript: `tsc --noEmit` with `"strict": true`.
