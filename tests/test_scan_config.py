"""Tests for FEATURE 5 - recursive scan + config + ignore rules.

Planned coverage (ARCHITECTURE_v1.md section 6.2):
  happy path  -> directory scan discovers ``**/*.md``; ``exclude``/``ignore``
                 rules are honored
  error path  -> malformed config => exit 2

Uses fixtures under ``tests/fixtures/`` (``nested/``, ``linkguard.cfg``).
Bodies land with FEATURE 5 of the build order (ARCHITECTURE_v1.md section 7).
"""

import unittest


class ScanAndConfigTests(unittest.TestCase):
    """Placeholder; real cases are added with FEATURE 5."""

    @unittest.skip("scaffold: implemented with FEATURE 5 (scan/config)")
    def test_directory_scan_discovers_markdown(self):
        raise NotImplementedError

    @unittest.skip("scaffold: implemented with FEATURE 5 (scan/config)")
    def test_exclude_globs_are_honored(self):
        raise NotImplementedError

    @unittest.skip("scaffold: implemented with FEATURE 5 (scan/config)")
    def test_malformed_config_exits_usage(self):
        raise NotImplementedError


if __name__ == "__main__":
    unittest.main()
