#!/usr/bin/env python3
from __future__ import annotations

import re
import shlex

COMMAND_SEPARATORS = {";", "&&", "||", "|"}
COMMAND_WRAPPERS = {"sudo", "env", "time", "nohup"}
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
PROD_SUFFIXES = ("rds.amazonaws.com", "neon.tech", "supabase.co")
URL_RE = re.compile(
    r"(?:postgres(?:ql)?|https?)://[^\s'\"\\]+",
    re.I,
)
DROP_RE = re.compile(r"\bDROP\s+(DATABASE|SCHEMA)\b", re.I)
PROD_ENV_BASENAMES = {
    ".env.production",
    ".env.prod",
    ".env.production.local",
    ".env.prod.local",
}
PRIVATE_KEY_BASENAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
PRIVATE_KEY_SUFFIXES = {".p12", ".pfx", ".p8"}


def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


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


def command_segments(command: str) -> list[list[str]]:
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


def skip_js_runner(tokens: list[str]) -> list[str]:
    tokens = list(tokens)
    if tokens and tokens[0] in {"npx", "pnpm", "yarn", "bunx"}:
        tokens.pop(0)
        while tokens and tokens[0].startswith("-"):
            option = tokens.pop(0)
            if option == "--":
                break
    return tokens


def is_loopback_host(host: str) -> bool:
    h = host.lower().strip().strip("[]")
    return h in LOOPBACK or h.startswith("127.")


def host_labels(host: str) -> list[str]:
    h = host.lower().strip().strip("[]")
    labels: list[str] = []
    for part in h.split("."):
        labels.extend(part.split("-"))
    return [lab for lab in labels if lab]


def is_prod_host(host: str) -> bool:
    if is_loopback_host(host):
        return False
    h = host.lower().strip().strip("[]")
    if any(h == suffix or h.endswith("." + suffix) for suffix in PROD_SUFFIXES):
        return True
    return any(lab in {"prod", "production"} for lab in host_labels(h))


def hosts_in_command(command: str) -> list[str]:
    hosts: list[str] = []
    for match in URL_RE.finditer(command):
        rest = match.group(0).split("://", 1)[-1]
        rest = rest.split("/")[0]
        rest = rest.split("@")[-1]
        host = rest.split(":")[0]
        if host:
            hosts.append(host)
    for tokens in command_segments(command):
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in {"-h", "--host"} and i + 1 < len(tokens):
                hosts.append(tokens[i + 1])
                i += 2
                continue
            if tok.startswith("--host="):
                hosts.append(tok.split("=", 1)[1])
            i += 1
    return hosts


def has_remote_host(command: str) -> bool:
    return any(not is_loopback_host(host) for host in hosts_in_command(command))


def command_is_prod_looking(command: str) -> bool:
    return any(
        is_prod_host(host)
        for host in hosts_in_command(command)
        if not is_loopback_host(host)
    )


LOCAL_KUBE_EXACT = {"docker-desktop", "minikube"}
LOCAL_KUBE_PREFIXES = ("kind-", "k3d-")


def kube_contexts_in_command(command: str) -> list[str]:
    names: list[str] = []
    for tokens in command_segments(command):
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in {"--context", "--kube-context"} and i + 1 < len(tokens):
                names.append(tokens[i + 1])
                i += 2
                continue
            if tok.startswith("--context=") or tok.startswith("--kube-context="):
                names.append(tok.split("=", 1)[1])
            i += 1
    return names


def docker_hosts_in_command(command: str) -> list[str]:
    hosts: list[str] = []
    for tokens in command_segments(command):
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in {"-H", "--host"} and i + 1 < len(tokens):
                hosts.append(tokens[i + 1])
                i += 2
                continue
            if tok.startswith("--host="):
                hosts.append(tok.split("=", 1)[1])
            i += 1
    return hosts


def is_local_kube_context(name: str) -> bool:
    n = name.lower().strip()
    if n in LOCAL_KUBE_EXACT:
        return True
    return any(n.startswith(prefix) for prefix in LOCAL_KUBE_PREFIXES)


def is_prod_looking_name(name: str) -> bool:
    return any(lab in {"prod", "production"} for lab in host_labels(name))


def is_local_container_target(command: str) -> bool:
    contexts = kube_contexts_in_command(command)
    docker_hosts = docker_hosts_in_command(command)
    if any(not is_local_kube_context(c) for c in contexts):
        return False
    if any(
        not is_loopback_host(h.split("://")[-1].split(":")[0] or h)
        for h in docker_hosts
    ):
        return False
    return True


def container_target_is_prod_looking(command: str) -> bool:
    if is_local_container_target(command):
        return False
    for ctx in kube_contexts_in_command(command):
        if not is_local_kube_context(ctx) and is_prod_looking_name(ctx):
            return True
    for host in docker_hosts_in_command(command) + hosts_in_command(command):
        h = host.split("://")[-1].split(":")[0]
        if h and not is_loopback_host(h) and is_prod_host(h):
            return True
    return False


def is_prod_env_basename(name: str) -> bool:
    return name in PROD_ENV_BASENAMES


def is_private_key_basename(name: str) -> bool:
    if name.endswith(".pub"):
        return False
    if name in PRIVATE_KEY_BASENAMES:
        return True
    return any(name.endswith(suffix) for suffix in PRIVATE_KEY_SUFFIXES)
