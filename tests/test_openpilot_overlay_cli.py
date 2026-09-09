import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from carrot_sim.openpilot_overlay_compat import UPSTREAM_HOST_ANCHORS


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "check_openpilot_overlay.py"


class TestOpenpilotOverlayCLI(unittest.TestCase):
  def _fixture(self):
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    for rel, anchors in UPSTREAM_HOST_ANCHORS.items():
      path = root / rel
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text("\n".join(anchors) + "\n", encoding="utf-8")
    return td, root

  def _run(self, root):
    return subprocess.run(
      [sys.executable, str(CLI), str(root)],
      cwd=ROOT,
      capture_output=True,
      text=True,
      check=False,
    )

  def test_compatible_checkout_returns_zero(self):
    td, root = self._fixture()
    self.addCleanup(td.cleanup)
    result = self._run(root)
    self.assertEqual(result.returncode, 0, result.stderr)
    payload = json.loads(result.stdout)
    self.assertEqual(payload["status"], "COMPATIBLE")
    self.assertEqual(payload["missingPaths"], [])
    self.assertEqual(payload["missingAnchors"], [])

  def test_missing_hook_returns_two(self):
    td, root = self._fixture()
    self.addCleanup(td.cleanup)
    (root / "openpilot/selfdrive/controls/plannerd.py").unlink()
    result = self._run(root)
    self.assertEqual(result.returncode, 2)
    payload = json.loads(result.stdout)
    self.assertEqual(payload["status"], "INVALID_SOURCE")


if __name__ == "__main__":
  unittest.main()
