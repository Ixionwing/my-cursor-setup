#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from safety_match import (
    command_segments,
    container_target_is_prod_looking,
    is_local_container_target,
)


def _has_all_and_force(tokens: list[str]) -> bool:
    has_all = False
    has_force = False
    for tok in tokens:
        if tok in {"-a", "--all"}:
            has_all = True
        elif tok in {"-f", "--force"}:
            has_force = True
        elif tok.startswith("-") and not tok.startswith("--"):
            letters = tok.lstrip("-")
            if "a" in letters:
                has_all = True
            if "f" in letters:
                has_force = True
    return has_all and has_force


def decide(command: str) -> tuple[str, str | None]:
    worst = "allow"
    reason = None
    rank = {"allow": 0, "ask": 1, "deny": 2}
    for tokens in command_segments(command):
        if not tokens:
            continue
        perm, msg = "allow", None
        if tokens[0] == "kubectl":
            if "delete" in tokens and ("namespace" in tokens or "ns" in tokens):
                perm, msg = "deny", "Blocked kubectl delete namespace."
            elif any(t in tokens for t in ("apply", "delete", "replace", "rollout")):
                if not is_local_container_target(command):
                    perm, msg = "ask", "Remote kubectl mutate needs confirmation."
        elif tokens[0] == "helm":
            if "uninstall" in tokens or "delete" in tokens:
                if container_target_is_prod_looking(command):
                    perm, msg = (
                        "deny",
                        "Blocked helm uninstall against a production-looking cluster.",
                    )
                elif not is_local_container_target(command):
                    perm, msg = "ask", "Remote helm uninstall needs confirmation."
            elif any(t in tokens for t in ("upgrade", "install", "rollback")):
                if not is_local_container_target(command):
                    perm, msg = "ask", "Remote helm mutate needs confirmation."
        elif tokens[0] == "docker":
            if "system" in tokens and "prune" in tokens:
                if _has_all_and_force(tokens):
                    perm, msg = "deny", "Blocked docker system prune -af."
            elif (tokens[:3] == ["docker", "compose", "down"] and "-v" in tokens) or (
                "rm" in tokens and "-f" in tokens
            ):
                if not is_local_container_target(command):
                    perm, msg = "ask", "Remote docker destructive command needs confirmation."
        if rank[perm] > rank[worst]:
            worst, reason = perm, msg
        if perm == "deny":
            return perm, msg
    return worst, reason


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        command = data.get("command") or data.get("shell_command") or ""
        permission, reason = decide(command)
        if permission == "deny":
            json.dump(
                {
                    "permission": "deny",
                    "user_message": reason,
                    "agent_message": reason,
                },
                sys.stdout,
            )
        elif permission == "ask":
            json.dump(
                {
                    "permission": "ask",
                    "user_message": reason,
                    "agent_message": reason,
                },
                sys.stdout,
            )
        else:
            json.dump({"permission": "allow"}, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        sys.stderr.write(f"deny-destructive-containers crash: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
