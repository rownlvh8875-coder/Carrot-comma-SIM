from pathlib import Path
import tempfile
import unittest

from carrot_sim.openpilot_overlay_compat import UPSTREAM_HOST_ANCHORS, inspect_openpilot_overlay_source


class TestOpenpilotOverlayCompatibility(unittest.TestCase):
  def _fixture(self):
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    for rel, anchors in UPSTREAM_HOST_ANCHORS.items():
      path = root / rel
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text("\n".join(anchors) + "\n", encoding="utf-8")
    return td, root

  def test_valid_host_surface_is_compatible(self):
    td, root = self._fixture()
    self.addCleanup(td.cleanup)
    result = inspect_openpilot_overlay_source(root)
    self.assertEqual(result.status, "COMPATIBLE")
    self.assertEqual(result.missing_paths, ())
    self.assertEqual(result.missing_anchors, ())

  def test_missing_required_host_path_is_invalid_source(self):
    td, root = self._fixture()
    self.addCleanup(td.cleanup)
    missing = root / "openpilot/selfdrive/controls/plannerd.py"
    missing.unlink()
    result = inspect_openpilot_overlay_source(root)
    self.assertEqual(result.status, "INVALID_SOURCE")
    self.assertIn("openpilot/selfdrive/controls/plannerd.py", result.missing_paths)

  def test_missing_anchor_requires_review(self):
    td, root = self._fixture()
    self.addCleanup(td.cleanup)
    target = root / "openpilot/cereal/log.capnp"
    target.write_text("customReserved3 @110\n", encoding="utf-8")
    result = inspect_openpilot_overlay_source(root)
    self.assertEqual(result.status, "REVIEW_REQUIRED")
    self.assertTrue(any("customReserved4 @111" in item for item in result.missing_anchors))

  def test_unrelated_native_egpu_file_does_not_make_upstream_incompatible(self):
    td, root = self._fixture()
    self.addCleanup(td.cleanup)
    native = root / "openpilot/selfdrive/modeld/native_egpu_backend.py"
    native.parent.mkdir(parents=True, exist_ok=True)
    native.write_text("# upstream-owned implementation\n", encoding="utf-8")
    result = inspect_openpilot_overlay_source(root)
    self.assertEqual(result.status, "COMPATIBLE")


if __name__ == "__main__":
  unittest.main()
