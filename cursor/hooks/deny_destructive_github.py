#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from safety_match import command_segments


def _segment_perm(tokens: list[str]) -> tuple[str, str | None]:
    if not tokens or tokens[0] != "gh":
        return "allow", None
    if len(tokens) >= 3 and tokens[1] == "repo" and tokens[2] == "delete":
        return "deny", "Blocked gh repo delete."
    if len(tokens) >= 3 and tokens[1] == "secret" and tokens[2] == "set":
        return "ask", "GitHub secret write needs confirmation."
    if len(tokens) >= 3 and tokens[1] == "variable" and tokens[2] == "set":
        return "ask", "GitHub variable write needs confirmation."
    return "allow", None


def decide(command: str) -> tuple[str, str | None]:
    worst = "allow"
    reason = None
    rank = {"allow": 0, "ask": 1, "deny": 2}
    for tokens in command_segments(command):
        perm, msg = _segment_perm(tokens)
        if rank[perm] > rank[worst]:
            worst = perm
            reason = msg
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
        sys.stderr.write(f"deny-destructive-github crash: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
