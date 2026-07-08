#!/usr/bin/env python3
"""Mechanical validator for Always-Wrapped SKILL.md files (skill-builder hard gate).

Usage:
    python validate_skill.py <path-to-SKILL.md | path-to-skill-dir>

Checks only mechanical, objective properties (it cannot judge content quality).
Conventions are drawn from Anthropic's Agent Skills spec/best-practices and
Cursor's create-skill guide. Exits non-zero on any error.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BLOCK_SCALARS = {">", ">-", ">+", "|", "|-", "|+"}
RESERVED_NAME_WORDS = ("anthropic", "claude")
ALLOWED_SUBDIRS = {"references", "scripts", "assets"}
MAX_BODY_LINES = 500
MAX_DESC_CHARS = 1024


def parse_frontmatter(text: str):
    """Return (frontmatter_dict_or_None, body_str). Minimal YAML, handles >- blocks."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, text
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:])
    data: dict[str, str] = {}
    i = 0
    while i < len(fm_lines):
        match = KEY_RE.match(fm_lines[i])
        if not match:
            i += 1
            continue
        key, val = match.group(1), match.group(2).strip()
        if val in BLOCK_SCALARS:
            block = []
            i += 1
            while i < len(fm_lines) and (fm_lines[i].startswith((" ", "\t")) or not fm_lines[i].strip()):
                block.append(fm_lines[i].strip())
                i += 1
            data[key] = " ".join(part for part in block if part).strip()
            continue
        data[key] = val.strip().strip('"').strip("'")
        i += 1
    return data, body


def resolve_target(arg: str) -> Path:
    path = Path(arg)
    if path.is_dir():
        path = path / "SKILL.md"
    return path


def check_reference(target: str, skill_dir: Path) -> str | None:
    """Return an error string for a bad markdown reference, else None."""
    link = target.split("#", 1)[0].strip()
    if not link or link.startswith(("http://", "https://", "mailto:")):
        return None
    if "\\" in link:
        return f"reference uses Windows-style path: {target!r}."
    parts = link.split("/")
    if len(parts) == 1:
        pass  # sibling file
    elif len(parts) == 2 and parts[0] in ALLOWED_SUBDIRS:
        pass  # one level into a known subdir (references/ scripts/ assets/)
    else:
        return f"reference not one level deep (use sibling or {sorted(ALLOWED_SUBDIRS)}/): {target!r}."
    if not (skill_dir / link).exists():
        return f"reference does not resolve: {target!r}."
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_skill.py <SKILL.md | skill-dir>", file=sys.stderr)
        return 2

    skill_path = resolve_target(argv[1])
    errors: list[str] = []
    warnings: list[str] = []

    if not skill_path.is_file():
        print(f"ERROR: not found: {skill_path}", file=sys.stderr)
        return 1

    if skill_path.name != "SKILL.md":
        errors.append(f"entry file must be named exactly 'SKILL.md' (got {skill_path.name!r}).")

    skill_dir = skill_path.parent
    text = skill_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    if fm is None:
        errors.append("missing or malformed YAML frontmatter (must start with '---').")
    else:
        name = fm.get("name", "")
        if not name:
            errors.append("frontmatter missing 'name'.")
        else:
            if not NAME_RE.match(name):
                errors.append(f"'name' must match ^[a-z0-9-]{{1,64}}$ (got: {name!r}).")
            if any(word in name.lower() for word in RESERVED_NAME_WORDS):
                errors.append(f"'name' must not contain reserved words {RESERVED_NAME_WORDS} (got: {name!r}).")
            if name != skill_dir.name:
                errors.append(f"'name' ({name!r}) must match directory name ({skill_dir.name!r}).")

        desc = fm.get("description", "")
        if not desc:
            errors.append("frontmatter missing 'description'.")
        else:
            if len(desc) > MAX_DESC_CHARS:
                errors.append(f"'description' is {len(desc)} chars (max {MAX_DESC_CHARS}).")
            if "<" in desc or ">" in desc:
                errors.append("'description' must not contain XML tags ('<' or '>').")
            if "use when" not in desc.lower() and "when " not in desc.lower():
                warnings.append("'description' has no WHEN trigger (add 'Use when ...').")
            low = desc.lower()
            if low.startswith(("i ", "i can", "you ", "you can", "we ")):
                warnings.append("'description' should be third person (avoid 'I'/'you'/'we').")

    body_lines = body.count("\n") + 1 if body else 0
    if body_lines > MAX_BODY_LINES:
        errors.append(f"body is {body_lines} lines (max {MAX_BODY_LINES}); use progressive disclosure.")

    parts = {p.lower() for p in skill_path.resolve().parts}
    if "skills" not in parts:
        warnings.append("skill is not under a 'skills/' directory.")

    for target in LINK_RE.findall(body):
        error = check_reference(target.strip(), skill_dir)
        if error:
            errors.append(error)

    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if errors:
        print(f"\nFAILED: {len(errors)} error(s), {len(warnings)} warning(s).", file=sys.stderr)
        return 1
    print(f"\nOK: {skill_path} passed ({len(warnings)} warning(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
