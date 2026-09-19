#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from safety_match import (
    URL_RE,
    command_segments,
    has_remote_host,
    is_loopback_host,
)

NETWORK_TOOLS = {"curl", "wget", "httpie", "nc", "netcat"}
ASK_MESSAGE = "Non-loopback network request needs confirmation."


def _first_operand(tokens: list[str]) -> str | None:
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if tok.startswith("-"):
            if tok in {"-H", "--header", "-o", "--output", "-d", "--data", "-X"} and i + 1 < len(
                tokens
            ):
                i += 2
                continue
            i += 1
            continue
        return tok
    return None


def _operand_looks_remote(operand: str) -> bool:
    if URL_RE.search(operand):
        return has_remote_host(operand)
    host = operand.split("/")[0].split(":")[0].strip()
    if not host or host.startswith(".") or "/" in host:
        return False
    if "." in host or host in {"localhost"}:
        return not is_loopback_host(host)
    return False


def decide(command: str) -> tuple[str, str | None]:
    for tokens in command_segments(command):
        if not tokens or tokens[0] not in NETWORK_TOOLS:
            continue
        if has_remote_host(command):
            return "ask", ASK_MESSAGE
        operand = _first_operand(tokens)
        if operand and _operand_looks_remote(operand):
            return "ask", ASK_MESSAGE
    return "allow", None


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        command = data.get("command") or data.get("shell_command") or ""
        permission, reason = decide(command)
        payload = {"permission": permission}
        if permission == "ask":
            payload["user_message"] = reason
            payload["agent_message"] = reason
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        sys.stderr.write(f"ask-unexpected-network crash: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
