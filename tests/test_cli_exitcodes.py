"""Tests for FEATURE 6 - CI gate: exit codes 0/1/2 and CLI flags.

Planned coverage (ARCHITECTURE_v1.md section 6.2):
  happy path  -> clean input => exit 0
  error path  -> broken link => exit 1; bad usage / unreadable => exit 2
  flags       -> ``--quiet`` suppresses ok findings; ``--timeout`` accepted

Bodies land with FEATURE 6 of the build order (ARCHITECTURE_v1.md section 7).
"""

import unittest


class CliExitCodeTests(unittest.TestCase):
    """Placeholder; real cases are added with FEATURE 6."""

    @unittest.skip("scaffold: implemented with FEATURE 6 (CLI)")
    def test_clean_input_exits_zero(self):
        raise NotImplementedError

    @unittest.skip("scaffold: implemented with FEATURE 6 (CLI)")
    def test_broken_link_exits_one(self):
        raise NotImplementedError

    @unittest.skip("scaffold: implemented with FEATURE 6 (CLI)")
    def test_usage_error_exits_two(self):
        raise NotImplementedError


if __name__ == "__main__":
    unittest.main()
