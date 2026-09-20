"""Tests for FEATURE 4 - offline mode (``--no-network``).

Planned coverage (ARCHITECTURE_v1.md section 6.2):
  happy path  -> local files and anchors are still validated offline
  behaviour   -> remote links are ``skipped``; exit 0 when everything else OK

Bodies land with FEATURE 4 of the build order (ARCHITECTURE_v1.md section 7).
"""

import unittest


class OfflineModeTests(unittest.TestCase):
    """Placeholder; real cases are added with FEATURE 4."""

    @unittest.skip("scaffold: implemented with FEATURE 4 (offline)")
    def test_remote_links_are_skipped_offline(self):
        raise NotImplementedError

    @unittest.skip("scaffold: implemented with FEATURE 4 (offline)")
    def test_local_and_anchor_still_checked_offline(self):
        raise NotImplementedError


if __name__ == "__main__":
    unittest.main()
