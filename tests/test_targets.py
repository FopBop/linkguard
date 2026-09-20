"""Tests for FEATURE 2 - target classification (local files, anchors, remote).

Planned coverage (ARCHITECTURE_v1.md section 6.2):
  happy path  -> existing local file => ``ok``; existing anchor => ``ok``
  error path  -> missing file => ``broken``; missing anchor => ``broken``;
                 remote exercised via an offline stub (no network)

Bodies land with FEATURE 2 of the build order (ARCHITECTURE_v1.md section 7).
"""

import unittest


class TargetClassificationTests(unittest.TestCase):
    """Placeholder; real cases are added with FEATURE 2."""

    @unittest.skip("scaffold: implemented with FEATURE 2 (targets)")
    def test_existing_local_file_is_ok(self):
        raise NotImplementedError

    @unittest.skip("scaffold: implemented with FEATURE 2 (targets)")
    def test_missing_local_file_is_broken(self):
        raise NotImplementedError

    @unittest.skip("scaffold: implemented with FEATURE 2 (targets)")
    def test_existing_and_missing_anchor(self):
        raise NotImplementedError


if __name__ == "__main__":
    unittest.main()
