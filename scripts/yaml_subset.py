from __future__ import annotations

from typing import Any


def parse_yaml_subset(text: str) -> dict:
    lines = text.splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        content = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if content.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"list item without list parent: {content}")
            parent.append(_parse_scalar(content[2:].strip()))
            continue
        if ":" not in content:
            raise ValueError(f"expected key: {content}")
        key, rest = content.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"map key under non-map: {key}")
        # multiline indicators like '|' or '>' are not supported by this subset
        if rest in ("|", ">"):
            raise ValueError(f"unsupported multiline indicator: {rest!r}")
        if rest == "":
            lookahead = _next_content(lines, i)
            child: Any
            if lookahead is None:
                child = {}
            else:
                next_indent, next_content = lookahead
                if next_indent <= indent:
                    child = {}
                elif next_content.startswith("- "):
                    child = []
                else:
                    child = {}
            parent[key] = child
            stack.append((indent, child))
            continue
        parent[key] = _parse_value(rest)
    return root


def _next_content(lines: list[str], start: int) -> tuple[int, str] | None:
    j = start
    while j < len(lines):
        raw = lines[j]
        if raw.strip() and not raw.lstrip().startswith("#"):
            indent = len(raw) - len(raw.lstrip(" "))
            return indent, raw.strip()
        j += 1
    return None


def _parse_value(rest: str) -> Any:
    if rest.startswith("[") and rest.endswith("]"):
        inner = rest[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p.strip()) for p in inner.split(",")]
    if rest.startswith("{") and rest.endswith("}"):
        inner = rest[1:-1].strip()
        if not inner:
            return {}
        out: dict[str, Any] = {}
        for part in _split_top_commas(inner):
            k, v = part.split(":", 1)
            out[k.strip()] = _parse_value(v.strip())
        return out
    return _parse_scalar(rest)


def _split_top_commas(s: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in s:
        if ch in "[({":
            depth += 1
        elif ch in "])}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def _parse_scalar(token: str) -> Any:
    if token in ("true", "True"):
        return True
    if token in ("false", "False"):
        return False
    if token in ("null", "~", ""):
        return None
    if token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
        return int(token)
    if (token.startswith('"') and token.endswith('"')) or (
        token.startswith("'") and token.endswith("'")
    ):
        return token[1:-1]
    return token


def load_yaml_file(path: str | bytes | Any) -> dict:
    from pathlib import Path

    return parse_yaml_subset(Path(path).read_text(encoding="utf-8"))

