# Architecture

This repository separates installable artifact identity from the graph that relates artifacts.

## Two trees

The repository tree contains the source payload and repository-only metadata:

```text
my-cursor-setup/
├── cursor/             installable skills, rules, and hooks
├── catalog.yaml        artifact graph and profile ID sets
├── manifest.yaml       source-to-destination mapping
├── scripts/            bootstrap implementation
├── docs/               operator documentation
└── third_party/        upstream snapshots and licenses
```

The destination tree receives only selected payload files plus bootstrap state:

```text
$DEST/
├── skills/
├── agents/
├── rules/
├── hooks/
├── hooks.json
├── my-cursor-setup-catalog.yaml
└── .my-cursor-setup-state.json
```

## Identity and relationships

Files under `cursor/` define an artifact's identity and behavior. `catalog.yaml` is the canonical relationship graph and groups artifact IDs into profiles. `manifest.yaml` maps each ID to its repository source and destination.

| Kind | Installed? | Role |
|------|------------|------|
| Cursor agent | not shipped | This repository does not install dest `agents/*.md` |
| Persona | catalog only | In-session role the main agent adopts; not a file under `cursor/agents/` |
| Skill | `cursor/skills/<name>/` | Domain workflow or vendor port |
| Rule | `cursor/rules/<name>.mdc` | Always-on: `route-context`, `commit-style`, `quality-style`. Other rules are glob-scoped (`alwaysApply: false`) |

For a skill, `skills.<id>.agents` may be empty. It does not dispatch Cursor subagents. Domain packs use **personas** (`personas.<id>.skills` / `skills.<id>.personas`). v2 has no catalog `dispatch` field. Persona edges (`personas.<id>.skills` / `skills.<id>.personas`) must stay symmetric. Skill-to-agent, agent-to-skill symmetry applies only when agent IDs exist.

Glob-scoped rules are hints for matching files. Do not treat every `*.ts` file as UI; `.ts` overlap between web-ts and backend-node is resolved by the task (React vs Node API) in `route-context`. Prisma vs SQLAlchemy is chosen from the task and paths, not from `.ts`/`.py` alone. Terraform, Docker, and Kubernetes/Helm share persona `infra`; pick the skill from the task and paths. Do not glob all `**/*.yaml`. GitHub Actions shares no persona with `infra`; `*.yml` is not enough to choose `ci` vs `infra`.

`core` always installs safety hooks and process skills (`verification-before-completion` and `tdd`). Superpowers is not part of this repository. Domain skills and glob rules come from optional profiles (`web-ts`, `backend`, `infra`, `db`, `ci`, `rag`, `mcp`). `--profile infra` is one persona with three skills (`terraform-skill`, `docker-conventions`, `kubernetes-skill`); Helm has no catalog ID. `kubernetes-skill` is a KubeShark subset (core refs plus Helm/Kustomize plus EKS; other cloud CRR files are omitted). `--profile db` adds Prisma vendor skills plus `python-db-conventions`; it does not gate the safety hooks. `--profile ci` adds original `github-actions` plus glob `github-actions-files` (`.github/workflows` and `.github/actions`, not `**/*.yml`). Reusable workflows and composite actions have no extra catalog ID. `--profile infra` does not install GitHub Actions. `--profile rag` is persona `rag` (`llamaindex-ingest`, `pydantic-ai-rag`, plus `python-db-conventions` shared with `--profile db`). `--profile mcp` is persona `mcp` (`fastmcp`). These packs have no glob rules. `.py` is not enough to choose `rag` vs `mcp` vs `backend-python` vs `db-python`.

Domain skills name bootstrap formatters, linters, and typecheckers plus official presets. This repository does not ship `eslint.config.js` or `ruff.toml`; the agent writes those in the app repo.

## Bootstrap update rules

The `core` profile is always enabled; `--profile` adds another profile. Bootstrap copies selected manifest entries file by file and stamps their installed hashes. On later runs, unchanged managed files can be updated. Dirty managed files are skipped unless `--force` is used. Files that already exist without a stamp are unmanaged collisions and are never overwritten, including with `--force`, unless their content exactly matches the payload; an exact match is adopted as managed after state-file loss.

After copy/merge, bootstrap **prunes** dest paths that are stamped but not in this run’s planned set. Dirty stamped files are skipped unless `--force`. Unstamped dest files are never deleted. `--disable-profile` removes that profile from state then uses the same `install()` path. `--uninstall` copies nothing, unmerges this repository’s `command`s from dest `hooks.json`, prunes remaining stamps, and deletes `.my-cursor-setup-state.json` when the stamp map is empty.

Omitting `--dest` is `~/.cursor`: TTY must type the dest path; non-TTY fail-closed. `--status` and `--dry-run` do not prompt.

`hooks.json` is merged for **every** event key by hook command path instead of replacing the destination document, including when the destination document is unstamped. The merge uses the manifest source and destination and runs only when its associated hook ID is enabled. A dry run reports operations without creating destination files. Status reports profiles, managed paths, and catalog graph drift.

Bootstrap never copies repository documentation, scripts, tests, `third_party/`, `manifest.yaml`, secrets, or arbitrary unmanaged files. It never deletes an unmanaged destination overlay.

The catalog is installed at `$DEST/my-cursor-setup-catalog.yaml`. Local stamps and enabled profiles are stored at `$DEST/.my-cursor-setup-state.json`; that state file is never copied from the repository.

## Always-on quality and safety

The always-on rules are `route-context`, `commit-style`, and `quality-style`. `commit-style` asks agents for concise commit messages, prohibits secrets, and keeps commits subject to repository hooks. `quality-style` matches the repo formatter/linter/typecheck, or the installed domain pack’s official presets when bootstrapping a new project. Core fail-closed hooks (`failClosed: true`) run on `beforeShellExecution` and `beforeReadFile`:

- Deny `git commit --no-verify` and `git push --no-verify` (`git commit -n` is `--no-verify`; `git push -n` is dry-run and stays allowed).
- Deny force-pushes to `main`/`master` (including symbolic refs that cannot be proven safe) and recursive `rm` (`-r`/`-R`/`--recursive`, with or without `-f`) for a path outside `/tmp` or `TMPDIR`; non-recursive `rm` remains allowed.
- Deny destructive database commands (`DROP DATABASE`/`SCHEMA`, `prisma migrate reset`, destructive `prisma db push`, Alembic downgrade/stamp against a production-looking host).
- Deny `kubectl delete namespace`/`ns`, `docker system prune` with both all and force (`-af` / `-a --force`), and `helm uninstall`/`delete` against a production-looking cluster.
- Deny `git add`/`commit` of `.env` (except `.env.example`) and private-key files; deny reading production env files and private keys.
- Ask before remote Prisma deploy / Alembic upgrade / `psql`, remote kubectl mutate / helm mutate, and before non-loopback `curl`/`wget`/`httpie`/`nc`.
- Deny `gh repo delete`. Ask before `gh secret set` and `gh variable set`. Other `gh` subcommands are not special-cased.

`beforeReadFile` can only allow or deny. Production env files (`.env.production`, `.env.prod`, `.env.production.local`, `.env.prod.local`) are denied with a user-visible message to edit or apply them yourself. Private-key reads (`id_rsa` and siblings without `.pub`, plus `.p12`/`.pfx`/`.p8`) are denied. `.env`, `.env.local`, `*.pem`, and `*.key` are not blocked on read.

Known limits: the hooks evaluate simple command segments separated by `;`, `&&`, `||`, or `|` and unwrap leading `sudo`, `env`, `time`, and `nohup`. They are not a full shell parser, so nested commands such as `bash -c '…'`, substitutions, aliases, and shell functions are not fully inspected. Matcher failures fail closed; a hook process crash also fails closed.
