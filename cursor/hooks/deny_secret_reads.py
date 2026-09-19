#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from safety_match import is_private_key_basename, is_prod_env_basename

PROD_ENV_MESSAGE = (
    "This looks like a production env file. The agent will not read it. "
    "Edit or apply it yourself. Do not paste its contents into chat."
)
PRIVATE_KEY_MESSAGE = (
    "This looks like a private key. It will not be sent to the model."
)


def decide(file_path: str) -> tuple[str, str | None]:
    name = Path(file_path).name
    if is_prod_env_basename(name):
        return "deny", PROD_ENV_MESSAGE
    if is_private_key_basename(name):
        return "deny", PRIVATE_KEY_MESSAGE
    return "allow", None


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        file_path = data.get("file_path") or data.get("path") or ""
        permission, reason = decide(file_path)
        payload = {"permission": permission}
        if permission == "deny":
            payload["user_message"] = reason
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        sys.stderr.write(f"deny-secret-reads crash: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
