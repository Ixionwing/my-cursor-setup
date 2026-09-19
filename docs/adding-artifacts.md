# Adding artifacts

Use this checklist when extending the setup:

- [ ] Add the installable file or directory under `cursor/`.
- [ ] Add its stable ID to `catalog.yaml` and to the appropriate profile ID set.
- [ ] Keep skill-to-agent relationships symmetric: every skill `agents` edge must have the matching agent `skills` edge, and vice versa.
- [ ] For domain skills, also keep `personas` edges symmetric (`personas.<id>.skills` ↔ `skills.<id>.personas`).
- [ ] Glob-scoped rules use `alwaysApply: false` except `route-context`, `commit-style`, and `quality-style`. Do not add a blanket `**/*.ts` glob for web-ts or backend-node, a blanket `**/*.py` glob for db-python, or a blanket `**/*.yaml` / `**/*.yml` glob for infra or GitHub Actions.
- [ ] Removing a catalog ID or disabling a profile deletes in-sync dest copies on the next bootstrap. Dest is not a backup.
- [ ] Confirmation tests mock `Path.home()`. Do not exercise omitted `--dest` against a live `~/.cursor`.
- [ ] New hook scripts need a catalog hook ID, a `manifest.yaml` file mapping, and a matching `cursor/hooks.json` event entry (`beforeShellExecution` or `beforeReadFile`). Shared helpers can use `always: true` in the manifest without being catalog hook IDs.
- [ ] Vendor subsets: copy only the kept upstream files into `third_party/`; list omitted files in the adapted `cursor/skills/.../SKILL.md` origin note. Helm is not a separate catalog skill ID.
- [ ] DB skills use persona edges (`db-prisma`, `db-python`, `domain-reviewer`), not new `cursor/agents/` files. Infra Docker/Kubernetes skills use persona `infra` the same way. GitHub Actions uses persona `ci` the same way (no extra catalog ID for reusable workflows or composite actions). Do not vendor Superpowers here.
- [ ] Add a `manifest.yaml` `files` entry mapping the ID's `src` to its destination-relative `dest`.
- [ ] Write descriptions as WHAT the artifact does plus WHEN it should be used.
- [ ] Run `python3 -m unittest discover -s tests -v`.
- [ ] Run `./scripts/bootstrap --dry-run --dest /tmp/mcs-dry`.

Do not add a catalog ID without a manifest entry, or a manifest source outside the repository. Test installation with a temporary `--dest`; do not use a live `~/.cursor` while developing.
