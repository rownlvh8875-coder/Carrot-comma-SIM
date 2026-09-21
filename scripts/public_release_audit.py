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

# Build the signatures in pieces so the audit source does not match itself.
FORBIDDEN_LITERAL_PATTERNS = (
    "BEGIN " + "OPENSSH PRIVATE KEY",
    "BEGIN " + "RSA PRIVATE KEY",
    "BEGIN " + "EC PRIVATE KEY",
    "ssh-" + "ed25519 ",
    "ssh-" + "rsa ",
    "github" + "_pat_",
    "gh" + "p_",
    "gh" + "o_",
    "gh" + "u_",
    "gh" + "s_",
    "sk-" + "proj-",
    "/" + "home" + "/",
    "C:" + "\\Users\\",
)

PRIVATE_IPV4 = re.compile(
    r"(?<![0-9])(?:"
    r"10(?:\.[0-9]{1,3}){3}|"
    r"192\.168(?:\.[0-9]{1,3}){2}|"
    r"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2}"
    r")(?![0-9])"
)
ROUTE_LIKE_ID = re.compile(r"\b[A-Za-z0-9_]+--[0-9a-f]{8,}\b")
DESKTOP_HOST = re.compile(r"\b" + "DESK" + "TOP-" + r"[A-Za-z0-9-]+\b", re.IGNORECASE)
DEVICE_ID_FIELD = re.compile(r'["\\\']' + "device" + "Id" + r'["\\\']\s*:')
PRIVATE_EVENT_COUNT = str(49_000 + 652)
ACTUAL_SETTING_BOUNDS = re.compile(
    r"(?is)(?:" + "Stop" + "Distance|" + "Stopping" + "Accel)"
    r".{0,240}?(?:minimum|min|lower).{0,80}?[-+]?[0-9]"
    r".{0,240}?(?:maximum|max|upper).{0,80}?[-+]?[0-9]"
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

        if suffix not in TEXT_SUFFIXES and path.name != ".gitignore":
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"non-UTF8 file requires manual public audit: {rel}")
            continue

        for pattern in FORBIDDEN_LITERAL_PATTERNS:
            if pattern in text:
                errors.append(f"forbidden literal {pattern!r} in {rel}")

        for match in PRIVATE_IPV4.finditer(text):
            errors.append(f"private IPv4 address {match.group(0)!r} in {rel}")
        if ROUTE_LIKE_ID.search(text):
            errors.append(f"route-like identifier in {rel}")
        if DESKTOP_HOST.search(text):
            errors.append(f"desktop hostname in {rel}")
        if DEVICE_ID_FIELD.search(text):
            errors.append(f"device identifier field in {rel}")
        if ACTUAL_SETTING_BOUNDS.search(text):
            errors.append(f"actual setting name paired with numeric bounds in {rel}")
        if PRIVATE_EVENT_COUNT in text:
            errors.append(f"private fixed scenario event count in {rel}")

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
