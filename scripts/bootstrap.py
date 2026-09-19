from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from yaml_subset import load_yaml_file

HOOK_COMMAND = "./hooks/deny_destructive_shell.py"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _state_path(dest: Path) -> Path:
    return dest / ".my-cursor-setup-state.json"


def load_state(dest: Path) -> dict[str, Any]:
    path = _state_path(dest)
    if not path.is_file():
        return {"profiles": ["core"], "stamps": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    profiles = data.get("profiles") or ["core"]
    if "core" not in profiles:
        profiles = ["core", *profiles]
    data["profiles"] = profiles
    data.setdefault("stamps", {})
    return data


def save_state(dest: Path, state: dict[str, Any]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    _state_path(dest).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def enabled_profiles(state: dict[str, Any], extra_profile: str | None) -> list[str]:
    profiles = list(state.get("profiles") or ["core"])
    if "core" not in profiles:
        profiles.insert(0, "core")
    if extra_profile and extra_profile not in profiles:
        profiles.append(extra_profile)
    return profiles


def ids_for_profiles(catalog: dict[str, Any], profiles: list[str]) -> set[str]:
    ids: set[str] = set()
    for name in profiles:
        block = catalog.get("profiles", {}).get(name)
        if block is None:
            raise SystemExit(f"unknown profile: {name}")
        for key in ("skills", "agents", "rules", "hooks"):
            ids.update(block.get(key) or [])
    return ids


def planned_files(
    manifest: dict[str, Any], ids: set[str]
) -> list[dict[str, Any]]:
    files = manifest.get("files") or {}
    planned: list[dict[str, Any]] = []
    for file_id, spec in files.items():
        hook_enabled = (
            spec.get("merge") == "hooks" and spec.get("hook") in ids
        )
        if spec.get("always") or file_id in ids or hook_enabled:
            planned.append({"id": file_id, **spec})
    return planned


def _iter_src_files(repo_root: Path, src: str) -> list[tuple[Path, str]]:
    src_path = repo_root / src
    if src_path.is_file():
        return [(src_path, src_path.name)]
    if src_path.is_dir():
        out: list[tuple[Path, str]] = []
        for p in sorted(src_path.rglob("*")):
            if p.is_file():
                out.append((p, str(p.relative_to(src_path))))
        return out
    raise FileNotFoundError(src)


def merge_hooks_json(payload: dict, existing: dict | None) -> dict:
    if not existing:
        return json.loads(json.dumps(payload))
    out = json.loads(json.dumps(existing))
    out.setdefault("version", payload.get("version", 1))
    out.setdefault("hooks", {})
    incoming_hooks = payload.get("hooks") or {}
    for event, incoming in incoming_hooks.items():
        if not isinstance(incoming, list):
            continue
        dest_list = out["hooks"].setdefault(event, [])
        for item in incoming:
            command = item.get("command")
            replaced = False
            for i, cur in enumerate(dest_list):
                if cur.get("command") == command:
                    dest_list[i] = item
                    replaced = True
                    break
            if not replaced:
                dest_list.append(item)
    return out


def drift_warnings(catalog: dict) -> list[str]:
    warnings: list[str] = []
    skills = catalog.get("skills") or {}
    agents = catalog.get("agents") or {}
    for skill_id, spec in skills.items():
        for agent_id in spec.get("agents") or []:
            allow = (agents.get(agent_id) or {}).get("skills") or []
            if skill_id not in allow:
                warnings.append(
                    f"drift: skill {skill_id} lists agent {agent_id}, but that agent does not list the skill"
                )
    for agent_id, spec in agents.items():
        for skill_id in spec.get("skills") or []:
            used_by = (skills.get(skill_id) or {}).get("agents") or []
            if agent_id not in used_by:
                warnings.append(
                    f"drift: agent {agent_id} lists skill {skill_id}, but that skill does not list the agent"
                )
    personas = catalog.get("personas") or {}
    for skill_id, spec in skills.items():
        for persona_id in spec.get("personas") or []:
            allow = (personas.get(persona_id) or {}).get("skills") or []
            if skill_id not in allow:
                warnings.append(
                    f"drift: skill {skill_id} lists persona {persona_id}, but that persona does not list the skill"
                )
    for persona_id, spec in personas.items():
        for skill_id in spec.get("skills") or []:
            used_by = (skills.get(skill_id) or {}).get("personas") or []
            if persona_id not in used_by:
                warnings.append(
                    f"drift: persona {persona_id} lists skill {skill_id}, but that skill does not list the persona"
                )
    return warnings


def _merge_hooks_into_dest(
    repo_root: Path,
    dest: Path,
    spec: dict[str, Any],
    *,
    force: bool,
    dry_run: bool,
    stamps: dict[str, str],
    result: dict[str, list[str]],
) -> None:
    src = repo_root / spec["src"]
    if not src.is_file():
        return
    dest_rel = spec["dest"]
    dest_file = dest / dest_rel
    stamp = stamps.get(dest_rel)
    if dest_file.is_file():
        if stamp is not None and sha256_file(dest_file) != stamp and not force:
            result["skipped_dirty"].append(dest_rel)
            return
    payload = json.loads(src.read_text(encoding="utf-8"))
    existing = None
    if dest_file.is_file():
        existing = json.loads(dest_file.read_text(encoding="utf-8"))
    merged = merge_hooks_json(payload, existing)
    result["copied"].append(dest_rel)
    if dry_run:
        return
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    stamps[dest_rel] = sha256_file(dest_file)


OUR_HOOKS_DEST = "hooks.json"


def unmerge_our_hook_commands(
    dest: Path,
    payload: dict,
    stamps: dict[str, str],
    *,
    force: bool,
    dry_run: bool,
    result: dict[str, list[str]],
    planned: set[str],
    dest_rel: str = OUR_HOOKS_DEST,
) -> None:
    dest_file = dest / dest_rel
    if dest_rel in planned:
        return
    if not dest_file.is_file():
        stamps.pop(dest_rel, None)
        return
    stamp = stamps.get(dest_rel)
    if stamp is not None and not force and sha256_file(dest_file) != stamp:
        result["skipped_dirty"].append(dest_rel)
        planned.add(dest_rel)
        return
    existing = json.loads(dest_file.read_text(encoding="utf-8"))
    drop = {
        item.get("command")
        for event in (payload.get("hooks") or {}).values()
        for item in event
        if item.get("command")
    }
    changed = False
    for event, items in list((existing.get("hooks") or {}).items()):
        kept = []
        for item in items:
            cmd = item.get("command")
            if cmd in drop:
                result["removed"].append(f"{dest_rel} command {cmd}")
                changed = True
            else:
                kept.append(item)
        existing["hooks"][event] = kept
    remaining = [
        item
        for event in (existing.get("hooks") or {}).values()
        for item in event
    ]
    if not remaining:
        result["removed"].append(dest_rel)
        if not dry_run:
            dest_file.unlink()
            stamps.pop(dest_rel, None)
        return
    planned.add(dest_rel)
    if changed and not dry_run:
        dest_file.write_text(
            json.dumps(existing, indent=2) + "\n", encoding="utf-8"
        )
        if stamp is not None:
            stamps[dest_rel] = sha256_file(dest_file)


def dest_paths_for_ids(
    repo_root: Path, manifest: dict[str, Any], ids: set[str]
) -> set[str]:
    paths: set[str] = set()
    for spec in planned_files(manifest, ids):
        if spec.get("merge") == "hooks":
            paths.add(spec["dest"])
            continue
        src = spec["src"]
        dest_rel_root = spec["dest"]
        for _src_file, rel in _iter_src_files(repo_root, src):
            if (repo_root / src).is_dir():
                paths.add(str(Path(dest_rel_root) / rel))
            else:
                paths.add(dest_rel_root)
    return paths


def prune_unplanned(
    dest: Path,
    stamps: dict[str, str],
    planned: set[str],
    *,
    force: bool,
    dry_run: bool,
    result: dict[str, list[str]],
) -> None:
    for dest_rel in list(stamps):
        if dest_rel in planned:
            continue
        dest_file = dest / dest_rel
        if not dest_file.exists():
            del stamps[dest_rel]
            continue
        if not force and sha256_file(dest_file) != stamps[dest_rel]:
            result["skipped_dirty"].append(dest_rel)
            continue
        result["removed"].append(dest_rel)
        if dry_run:
            continue
        dest_file.unlink()
        del stamps[dest_rel]


def install(
    repo_root: Path,
    dest: Path,
    *,
    force: bool,
    dry_run: bool,
    extra_profile: str | None,
    disable_profile: str | None = None,
    uninstall: bool = False,
) -> dict[str, list[str]]:
    catalog = load_yaml_file(repo_root / "catalog.yaml")
    manifest = load_yaml_file(repo_root / "manifest.yaml")
    if disable_profile and disable_profile not in (catalog.get("profiles") or {}):
        raise SystemExit(f"unknown profile: {disable_profile}")
    state = load_state(dest)
    profiles = enabled_profiles(state, extra_profile)
    if disable_profile and disable_profile in profiles:
        profiles = [p for p in profiles if p != disable_profile]
        if "core" not in profiles:
            profiles = ["core", *profiles]
    ids = ids_for_profiles(catalog, profiles)
    result = {
        "copied": [],
        "removed": [],
        "skipped_dirty": [],
        "warnings": drift_warnings(catalog),
    }
    stamps: dict[str, str] = dict(state.get("stamps") or {})
    planned_paths: set[str] = set()

    if uninstall:
        ids = set()
        profiles = ["core"]

    planned = planned_files(manifest, ids)
    if not uninstall:
        for spec in planned:
            if spec.get("merge") == "hooks":
                continue
            src = spec["src"]
            dest_rel_root = spec["dest"]
            for src_file, rel in _iter_src_files(repo_root, src):
                if (repo_root / src).is_dir():
                    dest_rel = str(Path(dest_rel_root) / rel)
                else:
                    dest_rel = dest_rel_root
                planned_paths.add(dest_rel)
                dest_file = dest / dest_rel
                stamp = stamps.get(dest_rel)
                if dest_file.is_file():
                    if stamp is None:
                        payload_hash = sha256_file(src_file)
                        if sha256_file(dest_file) != payload_hash:
                            result["skipped_dirty"].append(dest_rel)
                            continue
                        stamps[dest_rel] = payload_hash
                        stamp = payload_hash
                    if not force and sha256_file(dest_file) != stamp:
                        result["skipped_dirty"].append(dest_rel)
                        continue
                result["copied"].append(dest_rel)
                if dry_run:
                    continue
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
                stamps[dest_rel] = sha256_file(dest_file)

        hooks_spec = next((s for s in planned if s.get("merge") == "hooks"), None)
        if hooks_spec is not None:
            planned_paths.add(hooks_spec["dest"])
            _merge_hooks_into_dest(
                repo_root,
                dest,
                hooks_spec,
                force=force,
                dry_run=dry_run,
                stamps=stamps,
                result=result,
            )

    if uninstall:
        hooks_json_spec = (manifest.get("files") or {}).get("hooks-json") or {}
        hooks_src = hooks_json_spec.get("src")
        hooks_dest = hooks_json_spec.get("dest") or OUR_HOOKS_DEST
        payload = {}
        if hooks_src:
            payload_path = repo_root / hooks_src
            if payload_path.is_file():
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
        unmerge_our_hook_commands(
            dest,
            payload,
            stamps,
            force=force,
            dry_run=dry_run,
            result=result,
            planned=planned_paths,
            dest_rel=hooks_dest,
        )

    prune_unplanned(
        dest,
        stamps,
        planned_paths,
        force=force,
        dry_run=dry_run,
        result=result,
    )

    if uninstall and not dry_run:
        if not stamps:
            state_path = _state_path(dest)
            if state_path.is_file():
                state_path.unlink()
            return result
        profiles = ["core"]

    if not dry_run:
        save_state(dest, {"profiles": profiles, "stamps": stamps})
    return result


def confirm_default_dest(dest: Path) -> bool:
    isatty = getattr(sys.stdin, "isatty", None)
    if not callable(isatty) or not isatty():
        print("pass --dest when stdin is not a TTY", file=sys.stderr)
        return False
    print(f"Type this dest path to confirm: {dest}", file=sys.stderr)
    line = sys.stdin.readline()
    return line.strip() == str(dest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install my-cursor-setup into ~/.cursor")
    parser.add_argument("--profile", dest="profile")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--disable-profile")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    repo = args.repo
    if args.status and any(
        [
            args.profile,
            args.disable_profile,
            args.uninstall,
            args.dry_run,
            args.force,
        ]
    ):
        print("cannot combine --status with mutating flags", file=sys.stderr)
        return 1
    if args.uninstall and (args.profile or args.disable_profile):
        print("cannot combine --uninstall with --profile or --disable-profile", file=sys.stderr)
        return 1
    if args.disable_profile and args.profile:
        print("cannot combine --profile and --disable-profile", file=sys.stderr)
        return 1
    if args.disable_profile == "core":
        print("cannot disable core; use --uninstall", file=sys.stderr)
        return 1
    if args.disable_profile:
        catalog = load_yaml_file(repo / "catalog.yaml")
        if args.disable_profile not in (catalog.get("profiles") or {}):
            print(f"unknown profile: {args.disable_profile}", file=sys.stderr)
            return 1
    dest_omitted = args.dest is None
    dest = args.dest if args.dest is not None else Path.home() / ".cursor"
    mutating = not args.status and not args.dry_run
    if dest_omitted and mutating:
        if not confirm_default_dest(dest):
            return 1
    if args.status:
        catalog = load_yaml_file(repo / "catalog.yaml")
        manifest = load_yaml_file(repo / "manifest.yaml")
        state = load_state(dest)
        profiles = enabled_profiles(state, None)
        ids = ids_for_profiles(catalog, profiles)
        planned = dest_paths_for_ids(repo, manifest, ids)
        stamps = state.get("stamps") or {}
        print("profiles:", ", ".join(profiles))
        print("stamped files:", len(stamps))
        for dest_rel in sorted(stamps):
            stamp = stamps[dest_rel]
            dest_file = dest / dest_rel
            if dest_rel not in planned:
                label = "orphan" if dest_file.exists() else "missing"
            elif not dest_file.exists():
                label = "missing"
            elif sha256_file(dest_file) != stamp:
                label = "dirty"
            else:
                label = "in-sync"
            print(f"{label}: {dest_rel}")
        for w in drift_warnings(catalog):
            print("warning:", w, file=sys.stderr)
        return 0
    result = install(
        repo,
        dest,
        force=args.force,
        dry_run=args.dry_run,
        extra_profile=args.profile,
        disable_profile=args.disable_profile,
        uninstall=args.uninstall,
    )
    for label in ("copied", "removed", "skipped_dirty", "warnings"):
        for item in result[label]:
            print(f"{label}: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
