from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import shutil
import subprocess
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("public_release_audit", Path(__file__).resolve().parents[1] / "scripts/public_release_audit.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class PublicReleaseAuditTests(unittest.TestCase):
    def test_missing_root_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertTrue(audit.scan(Path(temp) / "missing"))

    @unittest.skipUnless(shutil.which("git"), "Git is needed to exercise tracked release enumeration")
    def test_git_release_scans_tracked_content_and_ignores_unpublished_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=15)
            git("init", "--quiet")
            (root / "safe.txt").write_text("safe", encoding="utf-8")
            (root / "cache.pyc").write_bytes(b"\x00cache")
            git("add", "--", "safe.txt")
            self.assertEqual(audit.scan(root), [])
            (root / "data.csv").write_text("BEGIN " + "OPENSSH PRIVATE KEY", encoding="utf-8")
            git("add", "--", "data.csv")
            self.assertTrue(audit.scan(root))
            # The release index may still contain a secret after the worktree
            # was edited back to safe text without staging that correction.
            (root / "data.csv").write_text("safe worktree", encoding="utf-8")
            self.assertTrue(audit.scan(root))

    def test_scans_secret_signatures_without_extension_allowlist(self):
        signature = "BEGIN " + "OPENSSH PRIVATE KEY"
        for name in ("credentials", "data.csv", "sample.unknown"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / name).write_text(signature, encoding="utf-8")
                self.assertTrue(audit.scan(root))

    def test_sensitive_names_are_blocked_even_with_benign_content(self):
        for name in (".env", ".env.local", "id_rsa", "id_ed25519"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / name).write_text("fixture only", encoding="utf-8")
                self.assertTrue(audit.scan(root))

    def test_private_key_header_variants_block_csv_and_extensionless_files(self):
        for header in ("PRIVATE KEY", "ENCRYPTED PRIVATE KEY", "DSA PRIVATE KEY",
                       "RSA PRIVATE KEY", "EC PRIVATE KEY", "OPENSSH PRIVATE KEY"):
            for name in ("synthetic.csv", "credentials"):
                with self.subTest(header=header, name=name), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    # Header-only synthetic data: this test never contains a key.
                    (root / name).write_text("-----BEGIN " + header + "-----\n", encoding="utf-8")
                    self.assertTrue(audit.scan(root))

    def test_unknown_binary_requires_review(self):
        for content in (b"binary\x00payload", b"\xff\xfe\x00"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "asset.unknown").write_bytes(content)
                self.assertTrue(audit.scan(root))

    def test_benign_csv_and_extensionless_text_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data.csv").write_text("id,value\na,3\n", encoding="utf-8")
            (root / "LICENSE").write_text("Public fixture", encoding="utf-8")
            self.assertEqual(audit.scan(root), [])

    def test_unreadable_file_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data.csv").write_text("safe", encoding="utf-8")
            with patch.object(Path, "open", side_effect=PermissionError("fixture denied")):
                self.assertTrue(audit.scan(root))

    def test_oversized_unknown_file_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "large.data").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
            self.assertTrue(audit.scan(root))


if __name__ == "__main__":
    unittest.main()
