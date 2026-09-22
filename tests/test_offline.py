"""Tests for FEATURE 4 - offline mode (``--no-network``).

Coverage (ARCHITECTURE_v1.md section 6.2 and 6.4):
  happy path  -> with ``allow_network=False`` local files and anchors are still
                 validated (a missing local file / anchor is still ``broken``)
  behaviour   -> remote links are ``skipped`` (never checked); a document whose
                 only non-ok findings are skipped remotes exits 0

Remote checks are never exercised here: offline mode is specifically about
*not* touching the network, so these tests assert that HTTP is never reached.
The runtime module is loaded by path; the suite stays hermetic.
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

_TIMEOUT = 1.0

# Fixture document with known headings, used for same-page anchor checks.
_DOC = os.path.join(_HERE, "fixtures", "doc_with_headings.md")

def _classify(url, base_dir):
    """Classify ``url`` offline (``allow_network=False``)."""
    link = lg.Link(url, line=1, column=1)
    return lg.classify(link, allow_network=False, timeout=_TIMEOUT,
                       base_dir=base_dir)


def _classify_in(url, source_file):
    """Classify a same-page anchor against ``source_file`` offline."""
    link = lg.Link(url, line=1, column=1)
    link.source_file = source_file
    return lg.classify(link, allow_network=False, timeout=_TIMEOUT,
                       base_dir=os.path.dirname(source_file))


class OfflineRemoteSkipTests(unittest.TestCase):
    """Offline mode skips remote links instead of checking them."""

    def test_http_remote_is_skipped_offline(self):
        link = _classify("https://example.invalid/page", _ROOT)
        self.assertEqual(link.status, "skipped")
        self.assertEqual(link.target_type, "skipped")
        self.assertIn("--no-network", link.error)

    def test_remote_scheme_is_skipped_offline(self):
        link = _classify("http://example.invalid/", _ROOT)
        self.assertEqual(link.status, "skipped")

    def test_skipped_remote_does_not_count_as_broken(self):
        """A skipped remote is neither ok nor broken (drives exit 0)."""
        link = _classify("https://example.invalid/", _ROOT)
        self.assertNotEqual(link.status, "broken")
        self.assertIsNone(link.http_status)


class OfflineLocalStillCheckedTests(unittest.TestCase):
    """Local files and anchors remain validated while offline."""

    def test_existing_local_file_is_ok_offline(self):
        # README.md exists at the repo root.
        link = _classify("README.md", _ROOT)
        self.assertEqual(link.status, "ok")

    def test_missing_local_file_is_broken_offline(self):
        link = _classify("definitely-not-here.md", _ROOT)
        self.assertEqual(link.status, "broken")

    def test_existing_fragment_anchor_is_ok_offline(self):
        # fixture doc has an "## Installing" heading, slugified to "installing".
        link = _classify_in("#installing", _DOC)
        self.assertEqual(link.status, "ok")

    def test_missing_fragment_anchor_is_broken_offline(self):
        link = _classify_in("#no-such-fragment", _DOC)
        self.assertEqual(link.status, "broken")


class OfflineExitCodeTests(unittest.TestCase):
    """A file whose only finding is a skipped remote exits 0."""

    def test_only_skipped_remote_yields_ok_summary(self):
        links = [
            _classify("https://example.invalid/", _ROOT),
            _classify("README.md", _ROOT),
        ]
        broken = [l for l in links if l.status == "broken"]
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
