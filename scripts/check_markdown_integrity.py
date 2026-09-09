#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote


LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "data:")


@dataclass(frozen=True)
class ScanResult:
    markdown_files: int
    errors: list[str]


def _markdown_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            files.append(path)
    return sorted(files)


def _normalize_link_target(raw: str) -> str | None:
    target = raw.strip()
    if not target or target.startswith("#") or target.startswith(EXTERNAL_PREFIXES):
        return None

    if target.startswith("<") and ">" in target:
        target = target[1:target.index(">")]
    else:
        # Markdown permits an optional title after the destination.
        target = target.split(maxsplit=1)[0]

    target = unquote(target)
    target = target.split("#", 1)[0].split("?", 1)[0]
    return target or None


def _check_fences(path: Path, text: str, root: Path) -> list[str]:
    opened: tuple[str, int, int] | None = None
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = FENCE_RE.match(line)
        if not match:
            continue
        fence = match.group(1)
        char = fence[0]
        length = len(fence)
        if opened is None:
            opened = (char, length, line_no)
        elif char == opened[0] and length >= opened[1]:
            opened = None

    if opened is None:
        return []

    rel = path.relative_to(root).as_posix()
    return [f"{rel}:{opened[2]}: unclosed code fence"]


def _check_links(path: Path, text: str, root: Path) -> list[str]:
    errors: list[str] = []
    rel = path.relative_to(root).as_posix()
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in LINK_RE.finditer(line):
            target = _normalize_link_target(match.group(1))
            if target is None:
                continue
            if target.startswith("/"):
                resolved = root / target.lstrip("/")
            else:
                resolved = path.parent / target
            if not resolved.exists():
                errors.append(
                    f"{rel}:{line_no}: missing local link target: {match.group(1).strip()}"
                )
    return errors


def scan_repository(root: Path) -> ScanResult:
    root = root.resolve()
    errors: list[str] = []
    files = _markdown_files(root)
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{path.relative_to(root).as_posix()}: not valid UTF-8")
            continue
        errors.extend(_check_fences(path, text, root))
        errors.extend(_check_links(path, text, root))
    return ScanResult(markdown_files=len(files), errors=errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Markdown structure and local links.")
    parser.add_argument("--root", default=".", help="Repository root to scan")
    args = parser.parse_args(argv)

    result = scan_repository(Path(args.root))
    print(f"Markdown files scanned: {result.markdown_files}")
    if result.errors:
        print(f"Markdown integrity errors: {len(result.errors)}", file=sys.stderr)
        for error in result.errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Markdown integrity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
