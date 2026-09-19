---
name: github-actions
description: Authors, debugs, and reviews GitHub Actions workflows and composite actions. Use for `.github/workflows` and `.github/actions` — not for Terraform, Dockerfiles, Kubernetes/Helm, or GitLab CI.
---

# GitHub Actions

Default: GitHub Actions for lint/test/build. Deploy only if the task asks.

## Author

- Put workflows in `.github/workflows/*.yml` (`.yaml` is valid). Composite actions live in `.github/actions/<name>/action.yml`.
- Set `permissions:` on every workflow (job-level if jobs differ). Default `contents: read`. Do not use `write-all`.
- Pin every `uses:` to a full commit SHA and comment the tag (`actions/checkout@<40-hex> # v4.2.2`). Look up the SHA at authoring time; do not copy a SHA from memory.
- Use `pull_request`, not `pull_request_target`, unless there is a documented reason. Never check out untrusted PR code in a privileged `pull_request_target` job.
- On PR workflows, set `concurrency` to cancel in-progress runs on the same ref. Set `timeout-minutes` on jobs.
- Cache from the lockfile via `actions/setup-node` / `actions/setup-python`. Do not hand-roll `actions/cache` of `node_modules`.
- Node/Express: `npm ci` then test. Python/FastAPI: use the project's existing installer (lockfile / `pyproject.toml`); do not invent Poetry or uv. Add a Postgres service container only if the task needs a DB. Do not invent extra deploy targets.
- Deploy jobs (only if asked): GitHub `environment` plus OIDC (`id-token: write`). Do not put long-lived cloud keys in repo secrets when OIDC works.
- Reusable workflows and composite actions are allowed. They are this skill, not a separate catalog ID.

## Debug

- Prefer `gh run list` and `gh run view --log-failed`. If `gh` is unavailable, say so and work from pasted logs.
- Inspect the failed step, then expressions (`if:`, `secrets.` on forks), then runner/`permissions`, then pin/SHA drift.
- Do not use `nektos/act` or design self-hosted runner fleets unless the user asks.

## Review

- Critical: unpinned `uses:`; overly broad `permissions`; `pull_request_target` plus untrusted checkout; secrets interpolated into shells; `curl | bash` of unpinned scripts; secrets available to fork PRs.
- Warnings: missing concurrency or timeouts; `:latest` action tags; deploy without an environment gate.
- Suggestions: matrix or path filters, lockfile cache, reusable workflow extraction.

Not Terraform (`terraform-skill`), Dockerfiles (`docker-conventions`), or Kubernetes/Helm (`kubernetes-skill`). A workflow that calls those tools still uses this skill for the YAML.

## Lint

If the repo already has actionlint, run it. If bootstrapping workflows, add actionlint with tool defaults. Do not add a second workflow linter.
