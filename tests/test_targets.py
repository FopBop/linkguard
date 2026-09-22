"""Tests for FEATURE 2 - broken-link detection / target classification.

Coverage (ARCHITECTURE_v1.md sections 6.2, 6.4):
  happy path  -> existing local file => ``ok``; existing anchor => ``ok``;
                 reachable remote URL => ``ok``
  error path  -> missing local file => ``broken``; missing anchor => ``broken``;
                 unreachable remote URL / HTTP error status / timeout => ``broken``

Remote checks are exercised *offline* against an in-process local HTTP fixture
server started on an ephemeral loopback port (ARCHITECTURE_v1.md section 6.4:
"Remote checks are stubbed in tests ... No test requires network"). The fixture
lives entirely on 127.0.0.1, so the suite stays hermetic and CI-safe.
"""

import importlib.util
import os
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_FIXTURES = os.path.join(_HERE, "fixtures")

# Load linkguard.py as a module without requiring it to be installed.
_spec = importlib.util.spec_from_file_location(
    "linkguard_core", os.path.join(_ROOT, "linkguard.py"))
lg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lg)


class _FixtureHandler(BaseHTTPRequestHandler):
    """A tiny offline HTTP endpoint used to exercise the remote classifier."""

    def log_message(self, *args):  # silence the default stderr logging
        pass

    def _respond(self, method):
        if self.path.startswith("/ok"):
            self.send_response(200)
            self.end_headers()
        elif self.path.startswith("/redirect"):
            # 302 to a reachable page; urllib follows redirects automatically.
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.end_headers()
        elif self.path.startswith("/head-rejected"):
            # Server rejects HEAD but serves GET (HEAD-then-GET fallback path).
            if method == "HEAD":
                self.send_response(405)
            else:
                self.send_response(200)
            self.end_headers()
        elif self.path.startswith("/notfound"):
            self.send_response(404)
            self.end_headers()
        elif self.path.startswith("/servererror"):
            self.send_response(500)
            self.end_headers()
        elif self.path.startswith("/ratelimited"):
            # Non-4xx-generic status: 429 must classify as broken too.
            self.send_response(429)
            self.end_headers()
        elif self.path.startswith("/slow"):
            # Sleep longer than the per-request timeout to force a timeout.
            import time
            time.sleep(2)
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self):
        self._respond("HEAD")

    def do_GET(self):
        self._respond("GET")


class _ServerFixture(object):
    """Context manager running the HTTP fixture on an ephemeral port."""

    def __enter__(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), _FixtureHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        return False

    def url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)


def _classify(url, allow_network=True, timeout=5.0, base_dir=_FIXTURES,
              source_file=None):
    link = lg.Link(url, 1, 1)
    link.source_file = source_file
    lg.classify(link, allow_network=allow_network, timeout=timeout,
                base_dir=base_dir)
    return link


class LocalTargetTests(unittest.TestCase):
    """Local file existence (broken-link detection, local half)."""

    def test_existing_local_file_is_ok(self):
        link = _classify("doc_with_headings.md")
        self.assertEqual(link.status, "ok")
        self.assertEqual(link.target_type, "local")
        self.assertIsNone(link.error)

    def test_missing_local_file_is_broken(self):
        link = _classify("does-not-exist.md")
        self.assertEqual(link.status, "broken")
        self.assertEqual(link.target_type, "local")
        self.assertIn("not found", link.error)


class AnchorTests(unittest.TestCase):
    """Intra-document anchors (broken-link detection, anchor half)."""

    def test_existing_anchor_in_target_doc_is_ok(self):
        link = _classify("doc_with_headings.md#installing")
        self.assertEqual(link.status, "ok")
        self.assertIsNone(link.error)

    def test_missing_anchor_in_target_doc_is_broken(self):
        link = _classify("doc_with_headings.md#nope")
        self.assertEqual(link.status, "broken")
        self.assertIn("anchor not found", link.error)

    def test_percent_encoded_anchor_resolves_to_slug(self):
        # Edge case: ``#Advanced%20Usage`` must normalise to the heading slug
        # ``advanced-usage`` (GitHub-style slug comparison), not stay broken.
        link = _classify("doc_with_headings.md#Advanced%20Usage")
        self.assertEqual(link.status, "ok")

    def test_pure_fragment_checked_against_source_file(self):
        link = _classify("#missing", source_file=os.path.join(
            _FIXTURES, "doc_with_headings.md"))
        self.assertEqual(link.status, "broken")
        self.assertEqual(link.target_type, "anchor")

    def test_top_fragment_always_resolves(self):
        link = _classify("#top", source_file=os.path.join(
            _FIXTURES, "doc_with_headings.md"))
        self.assertEqual(link.status, "ok")

    def test_pure_fragment_with_missing_source_file_is_broken(self):
        # Edge case: a source path was supplied but the file does not exist, so
        # the same-page anchor cannot be verified. It must be reported broken
        # rather than silently assumed to resolve.
        link = _classify("#anything", source_file=os.path.join(
            _FIXTURES, "no-such-source.md"))
        self.assertEqual(link.status, "broken")
        self.assertEqual(link.target_type, "anchor")
        self.assertIn("source file not found", link.error)

    def test_pure_fragment_without_source_file_is_ok(self):
        # Edge case: no source file context at all (programmatic use) -- the
        # anchor cannot be checked and is left as ok, preserving the documented
        # fallback behaviour.
        link = _classify("#anything", source_file=None)
        self.assertEqual(link.status, "ok")
        self.assertEqual(link.target_type, "anchor")


class AnchorEdgeCaseTests(unittest.TestCase):
    """Anchor edge cases against a single fixture with valid + invalid anchors.

    Exercises the extra normalisation added on top of the base FEATURE 2 anchor
    check using ``fixtures/anchors_edges.md`` (valid: exact slug, percent-encoded
    space, ``#top``, duplicate-heading suffix, inline-link heading; invalid:
    missing slug, malformed trailing-slash and query fragments).
    """

    _DOC = "anchors_edges.md"

    def _classify_anchor(self, fragment):
        return _classify("%s#%s" % (self._DOC, fragment))

    def test_valid_and_invalid_anchor_batch(self):
        # (fragment, expected_status) -- ``file.md#frag`` is a composite
        # local+anchor target, hence ``target_type == "local"``.
        cases = [
            ("advanced-usage", "ok"),
            ("Advanced%20Usage", "ok"),
            ("top", "ok"),
            ("setup", "ok"),
            ("setup-1", "ok"),
            ("see-the-docs", "ok"),
            ("does-not-exist", "broken"),
        ]
        for fragment, status in cases:
            with self.subTest(fragment=fragment):
                link = self._classify_anchor(fragment)
                self.assertEqual(link.status, status, link.error)
                self.assertEqual(link.target_type, "local")

    def test_malformed_trailing_slash_fragment_is_broken(self):
        # ``#advanced-usage/`` is not a real slug; punctuation-stripping must
        # not let it accidentally resolve to the ``advanced-usage`` heading.
        link = self._classify_anchor("advanced-usage/")
        self.assertEqual(link.status, "broken", link.error)
        self.assertIn("anchor not found", link.error)

    def test_malformed_query_fragment_is_broken(self):
        link = self._classify_anchor("advanced-usage?ref=1")
        self.assertEqual(link.status, "broken", link.error)
        self.assertIn("anchor not found", link.error)

    def test_inline_link_heading_slug_drops_url(self):
        # A heading containing an inline link slugs to the *visible text* only
        # (GitHub renders ``See the docs`` -> ``see-the-docs``), not the URL.
        link = self._classify_anchor("see-the-docs")
        self.assertEqual(link.status, "ok", link.error)
        broken = self._classify_anchor("see-the-docshttps")
        self.assertEqual(broken.status, "broken", broken.error)

    def test_cross_base_duplicate_slug_collision(self):
        # Edge case: a later heading's base slug can collide with a slug that
        # an *earlier* duplicate produced. ``## Setup``, ``## Setup``,
        # ``## Setup 1`` must slug to ``setup``, ``setup-1``, ``setup-1-1``
        # (github-slugger parity) -- never emitting ``setup-1`` twice. The
        # collision-avoiding suffix must therefore also be a valid target.
        doc = "anchors_collision.md"

        def anchor(fragment):
            return _classify("%s#%s" % (doc, fragment))

        for fragment in ("setup", "setup-1", "setup-1-1"):
            with self.subTest(fragment=fragment):
                link = anchor(fragment)
                self.assertEqual(link.status, "ok", link.error)
                self.assertEqual(link.target_type, "local")
        # Suffixes GitHub never emits must stay broken.
        for fragment in ("setup-1-2", "setup-2"):
            with self.subTest(fragment=fragment):
                link = anchor(fragment)
                self.assertEqual(link.status, "broken", link.error)
                self.assertIn("anchor not found", link.error)

    def test_atx_heading_without_space_after_hash(self):
        # Edge case: CommonMark makes the space after an ATX opening ``#``
        # sequence optional, so ``#Setup`` / ``#5 bolt`` / ``#hashtag`` are
        # real headings (spec examples 66/67). Anchors targeting their slugs
        # must resolve; a naive ``#\s+``-only regex wrongly reports them
        # broken. Seven ``#`` is a paragraph, so its "slug" must stay broken.
        doc = "anchors_nospace.md"

        def anchor(fragment):
            return _classify("%s#%s" % (doc, fragment))

        for fragment in ("setup", "5-bolt", "hashtag"):
            with self.subTest(fragment=fragment):
                link = anchor(fragment)
                self.assertEqual(link.status, "ok", link.error)
                self.assertEqual(link.target_type, "local")
        # ``####### not-a-heading`` is not a heading at all -> no target.
        for fragment in ("not-a-heading", "nope"):
            with self.subTest(fragment=fragment):
                link = anchor(fragment)
                self.assertEqual(link.status, "broken", link.error)
                self.assertIn("anchor not found", link.error)


class AnchorHtmlCommentTests(unittest.TestCase):
    """Headings inside HTML comments must not register as anchor targets.

    GitHub never parses the body of a block-level ``<!-- ... -->`` comment as
    Markdown, so a ``## Hidden`` line inside one produces no slug. A link to
    that phantom anchor must be reported ``broken`` rather than resolving.

    Exercised against ``fixtures/anchors_comments.md`` (a real heading, a
    multi-line comment hiding a heading-like line, and a heading after the
    comment).
    """

    _DOC = "anchors_comments.md"

    def _anchor(self, fragment):
        return _classify("%s#%s" % (self._DOC, fragment))

    def test_visible_heading_resolves(self):
        link = self._anchor("visible-heading")
        self.assertEqual(link.status, "ok")
        self.assertEqual(link.target_type, "local")
        self.assertIsNone(link.error)

    def test_heading_after_comment_resolves(self):
        link = self._anchor("after-comment")
        self.assertEqual(link.status, "ok")
        self.assertIsNone(link.error)

    def test_heading_inside_comment_is_broken(self):
        link = self._anchor("hidden-heading")
        self.assertEqual(link.status, "broken")
        self.assertIn("anchor not found", link.error)

    def test_find_anchor_ignores_commented_heading(self):
        text = "<!--\n# Hidden\n-->\n# Shown"
        self.assertFalse(lg._find_anchor(text, "hidden"))
        self.assertTrue(lg._find_anchor(text, "shown"))

    def test_find_anchor_masks_unterminated_comment(self):
        # A trailing ``<!--`` with no closer swallows the rest of the doc, so
        # nothing after it is an anchor target.
        text = "# Visible\n<!--\n# Hidden\n# Still Hidden"
        self.assertTrue(lg._find_anchor(text, "visible"))
        self.assertFalse(lg._find_anchor(text, "hidden"))
        self.assertFalse(lg._find_anchor(text, "still-hidden"))

    def test_find_anchor_single_line_comment_masks_inline_heading(self):
        # Heading-looking text on the same line as an inline comment is masked.
        text = "<!-- # Hidden -->\n# Real"
        self.assertFalse(lg._find_anchor(text, "hidden"))
        self.assertTrue(lg._find_anchor(text, "real"))


class AnchorUnderscoreTests(unittest.TestCase):
    """Edge case: an intraword ``_`` survives in the GitHub anchor slug.

    GitHub's slugger treats ``_`` as a word character, so the heading
    ``## foo_bar`` generates ``#foo_bar`` -- not ``#foobar``. A slugifier that
    strips every underscore (mistaking it for an emphasis marker) computes the
    wrong slug and so reports the valid ``#foo_bar`` link as broken. Exercised
    against ``fixtures/anchors_underscore.md``.
    """

    _DOC = "anchors_underscore.md"

    def _anchor(self, fragment):
        return _classify("%s#%s" % (self._DOC, fragment))

    def test_underscore_preserving_slug_matches_github(self):
        # Unit-level: the slug keeps intraword underscores but still drops
        # ``*``/backtick/``~`` emphasis markers.
        self.assertEqual(lg._slugify_heading("foo_bar baz"), "foo_bar-baz")
        self.assertEqual(lg._slugify_heading("**bold** text"), "bold-text")
        self.assertEqual(lg._slugify_heading("`x` y"), "x-y")

    def test_valid_underscore_anchors_resolve(self):
        for fragment in ("foo_bar", "config_file_path", "mixed---foo_bar-baz"):
            with self.subTest(fragment=fragment):
                link = self._anchor(fragment)
                self.assertEqual(link.status, "ok", link.error)
                self.assertEqual(link.target_type, "local")

    def test_underscore_stripped_anchors_are_broken(self):
        # The slugs a naive underscore-stripping slugifier would invent must
        # NOT resolve -- they are not real GitHub anchors.
        for fragment in ("foobar", "configfilepath"):
            with self.subTest(fragment=fragment):
                link = self._anchor(fragment)
                self.assertEqual(link.status, "broken", link.error)
                self.assertIn("anchor not found", link.error)

    def test_slugify_keeps_intraword_underscore_but_drops_emphasis(self):
        # Focused slugger-level regression: ``_`` is a *word* character in
        # GitHub's slugger, so it survives verbatim, whereas the emphasis
        # markers ``*``, backtick and ``~`` are still stripped.
        self.assertEqual(lg._slugify_heading("foo_bar"), "foo_bar")
        self.assertEqual(lg._slugify_heading("config_file_path"),
                         "config_file_path")
        self.assertEqual(lg._slugify_heading("snake_case heading"),
                         "snake_case-heading")
        # Emphasis / code / strikethrough markers are removed as before.
        self.assertEqual(lg._slugify_heading("**bold**"), "bold")
        self.assertEqual(lg._slugify_heading("`code`"), "code")
        self.assertEqual(lg._slugify_heading("~~gone~~"), "gone")
        # A pure-emphasis heading must not leak an underscore slug.
        self.assertEqual(lg._slugify_heading("_emph_"), "_emph_")
        self.assertEqual(lg._slugify_heading("a*b_c~d"), "ab_cd")

    def test_same_page_intraword_underscore_anchor_end_to_end(self):
        # Same-page anchor to an underscore-bearing heading resolves; the
        # underscore-stripped variant does not (concrete fixture walkthrough).
        src = os.path.join(_FIXTURES, "anchors_underscore.md")
        valid = _classify("#foo_bar", source_file=src)
        self.assertEqual(valid.status, "ok", valid.error)
        self.assertEqual(valid.target_type, "anchor")
        invalid = _classify("#foobar", source_file=src)
        self.assertEqual(invalid.status, "broken", invalid.error)
        self.assertIn("anchor not found", invalid.error)


class RemoteTargetTests(unittest.TestCase):
    """Remote (http/https) reachability against the offline fixture server."""

    def test_reachable_remote_is_ok(self):
        with _ServerFixture() as srv:
            link = _classify(srv.url("/ok"))
        self.assertEqual(link.status, "ok")
        self.assertEqual(link.target_type, "remote")
        self.assertEqual(link.http_status, 200)
        self.assertEqual(link.method, "HEAD")

    def test_redirecting_remote_is_ok(self):
        with _ServerFixture() as srv:
            link = _classify(srv.url("/redirect"))
        self.assertEqual(link.status, "ok")
        self.assertEqual(link.http_status, 200)

    def test_head_rejected_remote_falls_back_to_get(self):
        with _ServerFixture() as srv:
            link = _classify(srv.url("/head-rejected"))
        self.assertEqual(link.status, "ok")
        self.assertEqual(link.method, "GET")
        self.assertEqual(link.http_status, 200)

    def test_unreachable_remote_404_is_broken(self):
        with _ServerFixture() as srv:
            link = _classify(srv.url("/notfound"))
        self.assertEqual(link.status, "broken")
        self.assertEqual(link.http_status, 404)

    def test_server_error_remote_is_broken(self):
        with _ServerFixture() as srv:
            link = _classify(srv.url("/servererror"))
        self.assertEqual(link.status, "broken")
        self.assertEqual(link.http_status, 500)

    def test_timeout_remote_is_broken(self):
        with _ServerFixture() as srv:
            link = _classify(srv.url("/slow"), timeout=0.3)
        self.assertEqual(link.status, "broken")
        self.assertIsNone(link.http_status)

    def test_connection_refused_remote_is_broken(self):
        # Reserve then release a port so nothing is listening on it.
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        link = _classify("http://127.0.0.1:%d/gone" % port, timeout=1.0)
        self.assertEqual(link.status, "broken")
        self.assertEqual(link.target_type, "remote")

    def test_rate_limited_remote_is_broken(self):
        # 429 is neither a HEAD-rejection (403/405/501) nor a redirect, so it
        # must be classified broken with its status preserved.
        with _ServerFixture() as srv:
            link = _classify(srv.url("/ratelimited"))
        self.assertEqual(link.status, "broken")
        self.assertEqual(link.http_status, 429)

    def test_no_network_skips_remote(self):
        link = _classify("http://127.0.0.1:1/ok", allow_network=False)
        self.assertEqual(link.status, "skipped")
        self.assertEqual(link.target_type, "skipped")


class EmptyTargetTests(unittest.TestCase):
    """Edge case: empty / whitespace-only targets are skipped, not reported.

    A blank target is not a navigable link; classifying it as a missing local
    file would produce a phantom broken-link finding. This is the missing
    edge-case handling for the broken-link detector.
    """

    def test_empty_target_is_skipped_not_broken(self):
        link = _classify("")
        self.assertEqual(link.status, "skipped")
        self.assertEqual(link.target_type, "skipped")
        self.assertEqual(link.error, "empty target")

    def test_whitespace_only_target_is_skipped(self):
        link = _classify("   ")
        self.assertEqual(link.status, "skipped")
        self.assertEqual(link.target_type, "skipped")


class SkippedSchemeTests(unittest.TestCase):
    """Non-navigable schemes are skipped, never reported broken."""

    def test_mailto_is_skipped(self):
        link = _classify("mailto:a@b.com")
        self.assertEqual(link.status, "skipped")

    def test_unsupported_scheme_is_skipped(self):
        link = _classify("ftp://example.com/x")
        self.assertEqual(link.status, "skipped")


if __name__ == "__main__":
    unittest.main()
