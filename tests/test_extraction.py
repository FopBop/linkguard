"""Tests for FEATURE 1 - link extraction.

Planned coverage (ARCHITECTURE_v1.md section 6.2):
  happy path  -> inline / titled / angle / nested-paren / autolink parsed
  error path  -> code fences, inline code and images are ignored (asserted
                 absent from results)

Bodies land with FEATURE 1 of the build order (ARCHITECTURE_v1.md section 7).
"""

import unittest


class ExtractionTests(unittest.TestCase):
    """Placeholder; real cases are added with FEATURE 1."""

    @unittest.skip("scaffold: implemented with FEATURE 1 (extraction)")
    def test_inline_link_is_extracted(self):
        raise NotImplementedError

    @unittest.skip("scaffold: implemented with FEATURE 1 (extraction)")
    def test_code_blocks_and_images_are_ignored(self):
        raise NotImplementedError


if __name__ == "__main__":
    unittest.main()
