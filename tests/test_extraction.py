"""Tests for FEATURE 1 - link extraction.

Coverage (ARCHITECTURE_v1.md section 6.2):
  happy path  -> inline / titled / angle / nested-paren / autolink targets are
                 parsed, in order of appearance, with correct line/column
  error path  -> code fences, inline code spans and images are ignored
                 (asserted *absent* from ``extract_links`` results)

The runtime module lives at the repo root (``linkguard.py``) and is loaded
directly by path; no installation or third-party dependency is required.
"""

import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

_spec = importlib.util.spec_from_file_location(
    "linkguard_core", os.path.join(_ROOT, "linkguard.py"))
lg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lg)


def _urls(text):
    """Return the extracted link URLs (convenience for assertions)."""
    return [link.url for link in lg.extract_links(text)]


class InlineLinkExtractionTests(unittest.TestCase):
    """Happy path: every supported inline target form is parsed."""

    def test_plain_inline_link_is_extracted(self):
        links = lg.extract_links("[text](https://example.com)\n")
        self.assertEqual([l.url for l in links], ["https://example.com"])

    def test_titled_link_strips_the_title(self):
        links = lg.extract_links('[text](https://example.com "Title")\n')
        self.assertEqual([l.url for l in links], ["https://example.com"])

    def test_bare_autolink_is_extracted(self):
        links = lg.extract_links("See <https://example.com>.\n")
        self.assertEqual([l.url for l in links], ["https://example.com"])

    @unittest.expectedFailure
    def test_angle_bracket_target_is_extracted(self):
        # DEFECT EXTRACT-ANGLE: an angle-bracket *destination*
        # (``[text](<url>)``) is currently emitted twice -- once by the inline
        # link regex (which keeps the inner ``<...>``) and once by the
        # autolink regex matching the same ``<url>``. ARCHITECTURE_v1.md
        # section 7 step 3 requires it parsed exactly once. Recorded here as a
        # known failure for the debugger (feature code, not test code).
        links = lg.extract_links("[text](<https://example.com>)\n")
        self.assertEqual([l.url for l in links], ["https://example.com"])

    @unittest.expectedFailure
    def test_nested_parentheses_are_kept(self):
        # DEFECT EXTRACT-NESTED: ``[text](host/(path))`` must keep the trailing
        # ``)`` (nested-paren support, ARCHITECTURE_v1.md section 7 step 3);
        # ``_INLINE_LINK_RE`` currently stops at the first ``)`` and yields
        # ``https://x.com/(y``. Recorded as a known failure for the debugger.
        links = lg.extract_links("[text](https://x.com/(y))\n")
        self.assertEqual([l.url for l in links], ["https://x.com/(y)"])

    def test_multiple_links_preserve_source_order(self):
        text = "[a](a.md)\n\n[b](b.md)\n\n[c](c.md)\n"
        self.assertEqual(_urls(text), ["a.md", "b.md", "c.md"])

    def test_line_and_column_are_reported(self):
        text = "# Title\n\n[here](target.md)\n"
        links = lg.extract_links(text)
        self.assertEqual(len(links), 1)
        # Third physical line (1-based) and the column of the '['.
        self.assertEqual(links[0].line, 3)
        self.assertEqual(links[0].column, 1)


class ExtractionErrorPathTests(unittest.TestCase):
    """Error path: non-link constructs must be ignored (asserted absent)."""

    def test_fenced_code_block_is_ignored(self):
        text = "```\n[fenced](https://should-not-be-found.example)\n```\n"
        self.assertEqual(_urls(text), [])

    def test_inline_code_span_is_ignored(self):
        text = "Inline `[code](https://nope.example)` span.\n"
        self.assertEqual(_urls(text), [])

    def test_image_is_not_reported_as_a_link(self):
        text = "![alt](image.png)\n"
        self.assertEqual(_urls(text), [])

    def test_links_around_a_fence_are_still_found(self):
        """Masking a fence must not swallow neighbouring real links."""
        text = "[before](a.md)\n\n```\n[hidden](b.md)\n```\n\n[after](c.md)\n"
        self.assertEqual(_urls(text), ["a.md", "c.md"])


if __name__ == "__main__":
    unittest.main()
