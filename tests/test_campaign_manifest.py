from __future__ import annotations

import math
import unittest

from carrot_sim.campaign_manifest import canonical_json, content_sha256


class CampaignManifestTests(unittest.TestCase):
  def test_canonical_json_is_stable_and_compact(self):
    self.assertEqual(canonical_json({"b": 2, "a": [1]}), '{"a":[1],"b":2}')
    self.assertEqual(content_sha256({"b": 2, "a": [1]}), content_sha256({"a": [1], "b": 2}))

  def test_canonical_json_rejects_nonfinite_nested_values(self):
    for value in (math.nan, math.inf, -math.inf):
      with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite"):
        canonical_json({"outer": [{"value": value}]})


if __name__ == "__main__":
  unittest.main()
