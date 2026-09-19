#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from safety_match import (
    DROP_RE,
    command_is_prod_looking,
    command_segments,
    has_remote_host,
    skip_js_runner,
)


def _is_prisma(tokens: list[str]) -> list[str] | None:
    tokens = skip_js_runner(tokens)
    if tokens and tokens[0] == "prisma":
        return tokens
    return None


def _decide_segment(tokens: list[str], command: str) -> tuple[str, str | None]:
    prisma = _is_prisma(tokens)
    if prisma:
        if "migrate" in prisma and "reset" in prisma:
            return "deny", "Blocked prisma migrate reset."
        if "db" in prisma and "push" in prisma:
            if "--accept-data-loss" in prisma or "--force-reset" in prisma:
                return "deny", "Blocked destructive prisma db push."
        if "migrate" in prisma and "deploy" in prisma and has_remote_host(command):
            return "ask", "Remote prisma migrate deploy needs confirmation."
    if tokens and tokens[0] == "alembic":
        if "downgrade" in tokens or "stamp" in tokens:
            if command_is_prod_looking(command):
                return "deny", "Blocked alembic downgrade/stamp against a production-looking database."
        if "upgrade" in tokens and has_remote_host(command):
            return "ask", "Remote alembic upgrade needs confirmation."
    if tokens and tokens[0] in {"psql", "pg_dump", "pg_restore"} and has_remote_host(
        command
    ):
        return "ask", "Remote Postgres client needs confirmation."
    return "allow", None


def decide(command: str) -> tuple[str, str | None]:
    if DROP_RE.search(command or ""):
        return "deny", "Blocked DROP DATABASE/SCHEMA."
    worst = "allow"
    reason = None
    rank = {"allow": 0, "ask": 1, "deny": 2}
    for tokens in command_segments(command):
        permission, msg = _decide_segment(tokens, command)
        if rank[permission] > rank[worst]:
            worst = permission
            reason = msg
        if permission == "deny":
            return permission, msg
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
        sys.stderr.write(f"deny-destructive-db crash: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
