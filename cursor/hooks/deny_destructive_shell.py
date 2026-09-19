#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import sys


FORCE_LONG = {"--force", "--force-with-lease"}
PUSH_SHORT_FLAGS = set("dfnquv")
PUSH_OPTIONS_WITH_VALUE = {
    "--exec",
    "--push-option",
    "--receive-pack",
    "--recurse-submodules",
    "--repo",
}
PUSH_SHORT_OPTIONS_WITH_VALUE = {"-o"}
COMMAND_SEPARATORS = {";", "&&", "||", "|"}
COMMAND_WRAPPERS = {"sudo", "env", "time", "nohup"}


def _parse_push_short_options(tok: str) -> tuple[bool, bool] | None:
    if not tok.startswith("-") or tok.startswith("--") or tok == "-":
        return None
    force = False
    body = tok[1:]
    for index, letter in enumerate(body):
        if letter == "o":
            return force, index == len(body) - 1
        if letter not in PUSH_SHORT_FLAGS:
            return None
        force = force or letter == "f"
    return force, False


def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _command_segments(command: str) -> list[list[str]]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = []
        for chunk in re.split(r"(\&\&|\|\||[;|])", command):
            if chunk in COMMAND_SEPARATORS:
                tokens.append(chunk)
            else:
                tokens.extend(_tokens(chunk))
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in COMMAND_SEPARATORS:
            if segments[-1]:
                segments.append([])
            continue
        if isinstance(token, str):
            segments[-1].append(token)
    return [_strip_command_wrappers(segment) for segment in segments if segment]


def _strip_command_wrappers(tokens: list[str]) -> list[str]:
    tokens = list(tokens)
    while tokens and tokens[0] in COMMAND_WRAPPERS:
        wrapper = tokens.pop(0)
        while tokens and tokens[0].startswith("-"):
            option = tokens.pop(0)
            if option == "--":
                break
        if wrapper == "env":
            while tokens and "=" in tokens[0] and not tokens[0].startswith("="):
                tokens.pop(0)
    return tokens


def _is_force_token(tok: str) -> bool:
    # Treat "--force" and "--force-with-lease" as force tokens.
    # Also accept forms like "--force-with-lease=ref" where an argument is attached.
    if tok.startswith("--"):
        key = tok.split("=", 1)[0]
        if key in FORCE_LONG:
            return True
    parsed = _parse_push_short_options(tok)
    return parsed is not None and parsed[0]


def _is_rm_recursive(tokens: list[str]) -> bool:
    if not tokens or tokens[0] != "rm":
        return False
    letters = set()
    options_ended = False
    for tok in tokens[1:]:
        # Once "--" is seen, the remaining tokens are operands, not flags.
        if tok == "--":
            options_ended = True
            break
        # Skip long options like "--recursive" (they're not short clustered flags)
        if tok.startswith("--"):
            if tok == "--recursive":
                letters.add("r")
            elif tok == "--force":
                letters.add("f")
            continue
        if tok.startswith("-") and not options_ended:
            letters.update("r" if letter == "R" else letter for letter in tok[1:])
    return "r" in letters


def _rm_paths(tokens: list[str]) -> list[str]:
    out: list[str] = []
    options_ended = False
    for token in tokens[1:]:
        if token == "--" and not options_ended:
            options_ended = True
            continue
        if not options_ended and token.startswith("-"):
            continue
        out.append(token)
    return out


def _under_tmp(path: str, tmpdir: str | None) -> bool:
    real = os.path.realpath(path)
    allowed = [os.path.realpath("/tmp")]
    if tmpdir:
        allowed.append(os.path.realpath(tmpdir))
    env_tmp = os.environ.get("TMPDIR")
    if env_tmp:
        allowed.append(os.path.realpath(env_tmp))
    return any(real == root or real.startswith(root + os.sep) for root in allowed)


def _git_push_refs(tokens: list[str]) -> tuple[list[str], bool]:
    # git push [options] [<repository>] [<refspec>…]
    # Return a tuple (positional_args, repo_option_seen)
    if not tokens or tokens[0] != "git" or "push" not in tokens:
        return [], False
    rest = tokens[tokens.index("push") + 1 :]
    positional: list[str] = []
    options_ended = False
    repo_option_seen = False
    i = 0
    while i < len(rest):
        token = rest[i]
        if token == "--" and not options_ended:
            options_ended = True
            i += 1
            continue
        if not options_ended and token.startswith("-"):
            # handle --repo and --repo=origin forms specially so we know a
            # repository was supplied via option rather than as the first
            # positional argument.
            if token == "--repo":
                repo_option_seen = True
                i += 2
                continue
            if token.startswith("--repo="):
                repo_option_seen = True
                i += 1
                continue
            if token in PUSH_OPTIONS_WITH_VALUE | PUSH_SHORT_OPTIONS_WITH_VALUE:
                i += 2
                continue
            short_options = _parse_push_short_options(token)
            if short_options is not None and short_options[1]:
                i += 2
                continue
            # Long options with "=" and short options with attached values
            # already contain their argument. Unknown options are flags; they
            # must not consume a possible repository or refspec.
            i += 1
            continue
        positional.append(token)
        i += 1
    return positional, repo_option_seen


NO_VERIFY_MESSAGE = "Blocked git commit/push --no-verify."


def _git_subcommand(tokens: list[str]) -> str | None:
    if not tokens or tokens[0] != "git":
        return None
    for tok in tokens[1:]:
        if tok == "--":
            return None
        if tok.startswith("-"):
            continue
        return tok
    return None


def _has_long_option(tokens: list[str], name: str) -> bool:
    return any(tok == name or tok.startswith(name + "=") for tok in tokens)


def _short_flag_letters(tokens: list[str]) -> set[str]:
    letters: set[str] = set()
    for tok in tokens[1:]:
        if tok == "--":
            break
        if tok.startswith("--"):
            continue
        if tok.startswith("-") and len(tok) > 1:
            letters.update(tok[1:])
    return letters


def _no_verify_permission(tokens: list[str]) -> tuple[str, str | None] | None:
    sub = _git_subcommand(tokens)
    if sub == "commit":
        if _has_long_option(tokens, "--no-verify") or "n" in _short_flag_letters(
            tokens
        ):
            return "deny", NO_VERIFY_MESSAGE
    if sub == "push" and _has_long_option(tokens, "--no-verify"):
        return "deny", NO_VERIFY_MESSAGE
    return None


def _decide_segment(tokens: list[str], tmpdir: str | None) -> tuple[str, str | None]:
    if tokens and tokens[0] == "git":
        no_verify = _no_verify_permission(tokens)
        if no_verify is not None:
            return no_verify
    if tokens and tokens[0] == "git" and "push" in tokens:
        force = any(_is_force_token(token) for token in tokens)
        if force:
            refs, repo_option = _git_push_refs(tokens)
            names = []
            for ref in refs:
                names.append(ref.lstrip("+").split(":")[-1].split("/")[-1])
            # The first positional may be the remote; however if --repo was
            # supplied (either --repo <name> or --repo=<name>) then the first
            # positional is actually a refspec. When --repo was supplied we
            # should not treat the first positional as remote.
            if repo_option:
                ref_names = names
            else:
                ref_names = names[1:]
            if not ref_names:
                return (
                    "deny",
                    "Blocked force-push without an explicit ref (cannot prove it is not main/master).",
                )
            if any(name in {"HEAD", "@"} for name in ref_names):
                return (
                    "deny",
                    "Blocked force-push to an unprovable symbolic ref.",
                )
            if any(name in {"main", "master"} for name in ref_names):
                return (
                    "deny",
                    "Blocked force-push to main/master.",
                )
    if _is_rm_recursive(tokens):
        paths = _rm_paths(tokens)
        if not paths:
            return "deny", "Blocked recursive rm without an explicit path."
        if not all(_under_tmp(path, tmpdir) for path in paths):
            return (
                "deny",
                "Blocked recursive delete outside /tmp or TMPDIR.",
            )
    return "allow", None


def decide(command: str, tmpdir: str | None) -> tuple[str, str | None]:
    for tokens in _command_segments(command):
        permission, reason = _decide_segment(tokens, tmpdir)
        if permission == "deny":
            return permission, reason
    return "allow", None


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        command = data.get("command") or data.get("shell_command") or ""
        tmpdir = os.environ.get("TMPDIR")
        permission, reason = decide(command, tmpdir)
        if permission == "deny":
            json.dump(
                {
                    "permission": "deny",
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
        sys.stderr.write(f"deny-destructive-shell crash: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
