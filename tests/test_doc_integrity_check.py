import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_markdown_integrity.py"


class MarkdownIntegrityCheckerTests(unittest.TestCase):
    def load_checker(self):
        self.assertTrue(SCRIPT.exists(), "markdown integrity checker must exist")
        spec = importlib.util.spec_from_file_location("check_markdown_integrity", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_unclosed_fence_is_reported(self):
        checker = self.load_checker()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = root / "README.md"
            doc.write_text("# Test\n\n```python\nprint('x')\n", encoding="utf-8")
            result = checker.scan_repository(root)
            self.assertTrue(any("unclosed code fence" in err for err in result.errors))

    def test_missing_relative_markdown_link_is_reported(self):
        checker = self.load_checker()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = root / "README.md"
            doc.write_text("[missing](docs/NO_SUCH_FILE.md)\n", encoding="utf-8")
            result = checker.scan_repository(root)
            self.assertTrue(any("missing local link target" in err for err in result.errors))

    def test_existing_relative_link_and_anchor_are_allowed(self):
        checker = self.load_checker()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs").mkdir()
            (root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
            (root / "README.md").write_text(
                "[guide](docs/guide.md#guide) [section](#local-section)\n",
                encoding="utf-8",
            )
            result = checker.scan_repository(root)
            self.assertEqual([], result.errors)
            self.assertEqual(2, result.markdown_files)

    def test_external_links_and_mailto_are_not_treated_as_local_files(self):
        checker = self.load_checker()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text(
                "[web](https://example.com/a.md) [mail](mailto:test@example.com)\n",
                encoding="utf-8",
            )
            result = checker.scan_repository(root)
            self.assertEqual([], result.errors)


if __name__ == "__main__":
    unittest.main()
