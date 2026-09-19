#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from safety_match import (
    command_segments,
    is_private_key_basename,
    is_prod_env_basename,
)


def _operand_names(tokens: list[str]) -> list[str]:
    names: list[str] = []
    skip_value = {"-m", "-F", "--message", "--file", "-C", "--reuse-message"}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in skip_value and i + 1 < len(tokens):
            i += 2
            continue
        if tok.startswith("-") and tok not in {"-"}:
            i += 1
            continue
        names.append(Path(tok).name)
        i += 1
    return names


def _secret_git_operand(name: str) -> bool:
    if name == ".env.example":
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    if is_prod_env_basename(name) or is_private_key_basename(name):
        return True
    return False


def decide(command: str) -> tuple[str, str | None]:
    worst = "allow"
    reason = None
    rank = {"allow": 0, "ask": 1, "deny": 2}
    for tokens in command_segments(command):
        if not tokens:
            continue
        if tokens[0] == "git" and ("add" in tokens or "commit" in tokens):
            start = tokens.index("add") if "add" in tokens else tokens.index("commit")
            for name in _operand_names(tokens[start + 1 :]):
                if _secret_git_operand(name):
                    return "deny", f"Blocked git from staging secret file {name}."
        if tokens[0] in {"cat", "type", "head"}:
            for name in _operand_names(tokens[1:]):
                if is_prod_env_basename(name):
                    return (
                        "deny",
                        "Blocked reading a production env file. Edit or apply it yourself.",
                    )
                if name in {".env", ".env.local"}:
                    worst = "ask"
                    reason = "Reading .env needs confirmation."
        if rank[worst] == 2:
            break
    return worst, reason


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        command = data.get("command") or data.get("shell_command") or ""
        permission, reason = decide(command)
        payload = {"permission": permission}
        if permission != "allow":
            payload["user_message"] = reason
            payload["agent_message"] = reason
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        sys.stderr.write(f"deny-secrets-shell crash: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
