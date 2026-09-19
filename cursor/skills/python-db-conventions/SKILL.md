---
name: python-db-conventions
description: Implements and reviews Python Postgres access with SQLAlchemy 2.x and Alembic. Use for models, sessions, and migrations in FastAPI services — not for Prisma, React, or raw infra.
---

# Python DB conventions

Default stack: PostgreSQL + SQLAlchemy 2.x + Alembic, used from FastAPI via a request-scoped `AsyncSession`.

- Create revisions with `alembic revision`. Never hand-number revision ids.
- Autogenerate is a draft. Review before apply (renames, enums, CHECKs, and unnamed constraints are blind spots).
- Do not edit a revision that has reached a shared environment. Keep one head (`alembic heads` / `alembic check`).
- Revision files must not import live ORM models. Use `sa.table()` / SQL snapshots. Put data changes in their own revision.
- Set a `MetaData` naming_convention so constraints have deterministic names.
- SQLAlchemy 2.x only: `DeclarativeBase`, `Mapped[...]`, `mapped_column()`, `select()`. Relationships `lazy="raise"` unless the query eager-loads.
- One session per request or job. Async sessions use `expire_on_commit=False`.
- On live/prod-shaped tables: expand/contract (nullable add, backfill, concurrent indexes). Do not rename in place.
- Test migrations on PostgreSQL, not SQLite standing in for prod. Do not run `alembic downgrade` against a production-looking URL.

## Lint and types

If the repo already has these tools configured, run them. If bootstrapping, add them with the official presets below. Write config in the app repo. Do not add a parallel stack.

- Ruff: defaults plus `I` (isort) and `UP` (pyupgrade). Use Ruff format, not Black.
- Pyright: `typeCheckingMode: "standard"`.
