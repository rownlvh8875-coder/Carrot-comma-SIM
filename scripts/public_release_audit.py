from __future__ import annotations

"""Fail CI when obvious private-device or secret material enters the public repo."""

from pathlib import Path
import re
import sys


TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".ini",
    ".cfg",
}

FORBIDDEN_FILE_SUFFIXES = {
    ".rlog",
    ".qlog",
    ".zst",
    ".hevc",
    ".mov",
    ".mp4",
    ".pem",
    ".key",
}

FORBIDDEN_LITERAL_PATTERNS = (
    "BEGIN OPENSSH PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN EC PRIVATE KEY",
    "ssh-ed25519 ",
    "ssh-rsa ",
    "github_pat_",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "sk-proj-",
    "/home/",
    "C:\\Users\\",
)

PRIVATE_IPV4 = re.compile(
    r"(?<![0-9])(?:"
    r"10(?:\.[0-9]{1,3}){3}|"
    r"192\.168(?:\.[0-9]{1,3}){2}|"
    r"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2}"
    r")(?![0-9])"
)


def scan(root: Path) -> list[str]:
    errors: list[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue

        rel = path.relative_to(root)
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_FILE_SUFFIXES:
            errors.append(f"forbidden public file type: {rel}")
            continue

        if suffix not in TEXT_SUFFIXES and path.name not in {".gitignore"}:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"non-UTF8 file requires manual public audit: {rel}")
            continue

        # .gitignore names private artifacts intentionally, so only scan it for secrets/IPs.
        patterns = FORBIDDEN_LITERAL_PATTERNS
        if path.name == ".gitignore":
            patterns = tuple(
                p for p in patterns if p not in {"/home/", "C:\\Users\\"}
            )

        for pattern in patterns:
            if pattern in text:
                errors.append(f"forbidden literal {pattern!r} in {rel}")

        for match in PRIVATE_IPV4.finditer(text):
            errors.append(f"private IPv4 address {match.group(0)!r} in {rel}")

    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    errors = scan(root)
    if errors:
        print("PUBLIC RELEASE AUDIT: FAIL")
        for error in errors:
            print(f"- {error}")
        return 2

    print("PUBLIC RELEASE AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
