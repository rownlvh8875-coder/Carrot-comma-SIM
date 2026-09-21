from __future__ import annotations

"""Fail CI when obvious private-device or secret material enters the public repo."""

from pathlib import Path
import re
import subprocess
import sys


MAX_TEXT_BYTES = 2 * 1024 * 1024
PRIVATE_KEY_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}

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
    "BEGIN " + "PRIVATE KEY",
    "BEGIN " + "ENCRYPTED PRIVATE KEY",
    "BEGIN " + "DSA PRIVATE KEY",
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


def _scan_bytes(data: bytes, label: str) -> list[str]:
    if len(data) > MAX_TEXT_BYTES:
        return [f"oversized file requires manual public audit: {label}"]
    if b"\0" in data:
        return [f"binary file requires manual public audit: {label}"]
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [f"non-UTF8 file requires manual public audit: {label}"]
    errors = [f"forbidden literal {pattern!r} in {label}" for pattern in FORBIDDEN_LITERAL_PATTERNS if pattern in text]
    errors.extend(f"private IPv4 address {match.group(0)!r} in {label}" for match in PRIVATE_IPV4.finditer(text))
    if ROUTE_LIKE_ID.search(text):
        errors.append(f"route-like identifier in {label}")
    if DESKTOP_HOST.search(text):
        errors.append(f"desktop hostname in {label}")
    if DEVICE_ID_FIELD.search(text):
        errors.append(f"device identifier field in {label}")
    if ACTUAL_SETTING_BOUNDS.search(text):
        errors.append(f"actual setting name paired with numeric bounds in {label}")
    if PRIVATE_EVENT_COUNT in text:
        errors.append(f"private fixed scenario event count in {label}")
    return errors


def scan(root: Path) -> list[str]:
    """Scan tracked release files, or all files in a non-Git export.

    Extensionless and unfamiliar text formats receive the same content checks.
    An unreadable, binary, oversized or linked file requires explicit review;
    it cannot silently satisfy the public release check.
    """
    root = root.resolve()
    if not root.is_dir():
        return ["public release root is not a readable directory"]
    errors: list[str] = []
    index_blobs: dict[Path, str] = {}
    try:
        if (root / ".git").exists():
            result = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(root), "ls-files", "--stage", "-z"],
                capture_output=True, check=True, timeout=30,
            )
            paths = []
            for entry in result.stdout.decode("utf-8").split("\0"):
                if not entry:
                    continue
                metadata, name = entry.split("\t", 1)
                mode, object_id, stage = metadata.split()
                path = root / name
                if stage != "0" or mode not in {"100644", "100755"}:
                    errors.append(f"non-regular or unmerged index entry requires manual public audit: {name}")
                    continue
                paths.append(path)
                index_blobs[path] = object_id
        else:
            paths = [p for p in root.rglob("*") if ".git" not in p.relative_to(root).parts and (p.is_file() or p.is_symlink())]
    except (OSError, ValueError, subprocess.SubprocessError):
        return ["could not enumerate public release files; manual audit required"]

    for path in sorted(paths):
        rel = path.relative_to(root)
        name = path.name.lower()
        if path.is_symlink():
            errors.append(f"linked file requires manual public audit: {rel}")
            continue
        if name.startswith(".env") or name in PRIVATE_KEY_NAMES:
            errors.append(f"forbidden public file name: {rel}")
            continue
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_FILE_SUFFIXES:
            errors.append(f"forbidden public file type: {rel}")
            continue

        # Inspect the staged bytes as well as the worktree: editing a secret
        # out of a working file does not remove it from an already staged blob.
        if path in index_blobs:
            command = ["git", "--no-optional-locks", "-C", str(root), "cat-file"]
            try:
                size_result = subprocess.run(command + ["-s", index_blobs[path]], capture_output=True, check=True, timeout=30)
                size = int(size_result.stdout)
                if size > MAX_TEXT_BYTES:
                    errors.append(f"oversized staged file requires manual public audit: {rel}")
                else:
                    blob = subprocess.run(command + ["blob", index_blobs[path]], capture_output=True, check=True, timeout=30)
                    errors.extend(_scan_bytes(blob.stdout, f"{rel} (index)"))
            except (OSError, ValueError, subprocess.SubprocessError):
                errors.append(f"unreadable staged file requires manual public audit: {rel}")
        try:
            with path.open("rb") as stream:
                data = stream.read(MAX_TEXT_BYTES + 1)
            errors.extend(_scan_bytes(data, str(rel)))
        except OSError:
            errors.append(f"unreadable file requires manual public audit: {rel}")

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
