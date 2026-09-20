"""Tests for FEATURE 3 - JSON and SARIF report output.

Planned coverage (ARCHITECTURE_v1.md section 6.2):
  happy path  -> ``--json`` and ``--sarif`` validate against
                 ``schemas/report.schema.json`` / ``schemas/sarif.schema.json``
                 (validated by a stdlib-only subset validator, no jsonschema dep)
  error path  -> ``--json --sarif`` together => exit 2

Bodies land with FEATURE 3 of the build order (ARCHITECTURE_v1.md section 7).
"""

import unittest


class OutputTests(unittest.TestCase):
    """Placeholder; real cases are added with FEATURE 3."""

    @unittest.skip("scaffold: implemented with FEATURE 3 (output)")
    def test_json_report_matches_schema(self):
        raise NotImplementedError

    @unittest.skip("scaffold: implemented with FEATURE 3 (output)")
    def test_sarif_report_matches_schema(self):
        raise NotImplementedError

    @unittest.skip("scaffold: implemented with FEATURE 3 (output)")
    def test_json_and_sarif_are_mutually_exclusive(self):
        raise NotImplementedError


if __name__ == "__main__":
    unittest.main()
