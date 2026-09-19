# my-cursor-setup

A small, auditable Cursor setup that does five jobs:

1. **Safety:** blocks force-pushes to `main`/`master`, recursive `rm`
   outside `/tmp` or `TMPDIR`, destructive database commands, secret
   git-add, `kubectl delete namespace`, `docker system prune -af`,
   production-looking `helm uninstall`, and `gh repo delete`; asks before
   `gh secret set` / `gh variable set` and before non-loopback
   `curl`/`wget`/`httpie`/`nc`. Hook process crashes deny the action.
2. **Process:** installs focused verification and TDD (`tdd`) guidance.
   Superpowers is not bundled.
3. **Personas:** v1 `implementer`/`reviewer` agents plus in-session domain
   personas (React, Node, Python, Terraform/Docker/Kubernetes, GitHub Actions, Prisma,
   SQLAlchemy) that the main agent adopts.
4. **Quality/style:** `commit-style` for commits; `quality-style` for formatter/linter/typecheck
   (use the repo’s stack, or the domain default when bootstrapping). `git commit`/`push
   --no-verify` is denied.
5. **Context routing:** loads the right repository context without loading an
   entire skill library.

## Install

Install the always-on `core` profile:

```sh
./scripts/bootstrap
```

Use `--dest DIR` to install somewhere other than `~/.cursor`. Omitting
`--dest` targets `~/.cursor`. On a TTY, type that dest path to confirm.
Non-TTY must pass `--dest`. `--dest ~/.cursor` skips the prompt.

Useful controls:

- `--status` reports enabled profiles and each stamp as in-sync, dirty, missing, or orphan.
- `--dry-run` prints planned `copied:` / `removed:` / `skipped_dirty:` without writing.
- `--force` replaces dirty managed files on copy **and** prune; it never overwrites or deletes an unstamped destination collision.
- `--disable-profile NAME` drops an optional profile (not `core`) and reconciles dest.
- `--uninstall` removes this setup’s in-sync dest files and unmerges our hook commands.
- `--profile NAME` adds an optional profile to the always-enabled `core`.
  `web-ts`, `backend`, `infra`, `db`, and `ci` add domain skills. Domain work is adopted
  in this session (no new subagents). `backend` includes both Node/Express
  and Python/FastAPI. `infra` includes Terraform, Docker, and Kubernetes/Helm
  (Helm is covered by `kubernetes-skill`, not a separate catalog ID). `db`
  includes Prisma and SQLAlchemy/Alembic. `ci` includes GitHub Actions
  (reusable workflows and composite actions use `github-actions`, not a
  separate catalog ID; GitLab is not included). This repository has no
  `.github/workflows/`. Production env files
  (`.env.production` and the other prod env basenames) are manual: the agent
  will not read them.

For example:

```sh
./scripts/bootstrap --dry-run --dest /tmp/mcs-dry
./scripts/bootstrap --profile web-ts
./scripts/bootstrap --status
```

## Mental model

Artifact identity and content live under `cursor/`. Relationships between artifact IDs live in `catalog.yaml`. Profiles are sets of those IDs; `core` is always active and optional profiles add to it. `manifest.yaml` maps selected IDs to source and destination paths.

See [Architecture](docs/architecture.md) for the complete system map and update rules.

Once a workflow is vendored here, disable the matching Cursor plugin or accept duplicate skills, rules, and behavior.