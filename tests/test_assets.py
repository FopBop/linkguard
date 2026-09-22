"""Tests for the image / static-asset reference check.

Coverage (ARCHITECTURE_v1.md section 2.2, FEATURE 1b + asset check):

  happy path  -> a referenced image that exists on disk resolves ``ok``,
                 including dotted, parent-relative and root-relative paths,
                 titled targets, angle-bracket targets and reference-style
                 images.
  error path  -> a referenced image that is missing resolves ``broken``;
                 non-local assets (``data:``/``http(s):``/...), in-document
                 fragments and images inside code fences are ``skipped`` or
                 ignored, never falsely ``broken``.

The check is hermetic: all fixtures are created under a temporary directory
(or the checked-in ``tests/fixtures/`` tree); no network access is used.
"""

import importlib.util
import os
import shutil
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# Load linkguard.py as a module without requiring it to be installed.
_spec = importlib.util.spec_from_file_location(
    "linkguard_core", os.path.join(_ROOT, "linkguard.py"))
lg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lg)


class _AssetFixture(unittest.TestCase):
    """Base class building an on-disk tree of present/missing assets."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="linkguard-assets-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def touch(self, relpath):
        """Create an empty file at ``relpath`` under the fixture root."""
        path = os.path.join(self.tmp, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("")

    def check(self, text, base_dir=None):
        """Extract and check every image in ``text``.

        :returns: a list of ``(url, status)`` tuples in document order.
        """
        base = base_dir or self.tmp
        results = []
        for asset in lg.extract_assets(text):
            lg.check_asset(asset, base_dir=base)
            results.append((asset.url, asset.status))
        return results


class InlineImageTests(_AssetFixture):
    """``![alt](src)`` inline image references."""

    def test_present_asset_is_ok(self):
        self.touch("images/logo.png")
        self.assertEqual(
            self.check("![logo](images/logo.png)\n"),
            [("images/logo.png", "ok")])

    def test_missing_asset_is_broken(self):
        self.assertEqual(
            self.check("![logo](images/missing.png)\n"),
            [("images/missing.png", "broken")])

    def test_dot_relative_and_dotdot_paths_resolve(self):
        # Relative asset paths resolve against the *document's* directory
        # (base_dir), not the scan root: ``./sibling.png`` must therefore be
        # a sibling of the document (``docs/sibling.png``), and
        # ``../images/logo.png`` climbs back out to the scan root's ``images``.
        self.touch("images/logo.png")
        self.touch("docs/sibling.png")
        sub = os.path.join(self.tmp, "docs")
        text = ("![a](./sibling.png)\n"
                "![b](../images/logo.png)\n")
        self.assertEqual(
            self.check(text, base_dir=sub),
            [("./sibling.png", "ok"), ("../images/logo.png", "ok")])

    def test_dot_relative_path_not_beside_document_is_broken(self):
        # The mirror of the test above: a file at the scan root is NOT a
        # sibling of a document in ``docs/``, so the doc-dir-relative
        # resolution must report it broken rather than false-positive ``ok``.
        self.touch("sibling.png")
        sub = os.path.join(self.tmp, "docs")
        os.makedirs(sub, exist_ok=True)
        self.assertEqual(
            self.check("![a](./sibling.png)\n", base_dir=sub),
            [("./sibling.png", "broken")])

    def test_windows_backslash_separator_resolves(self):
        # Windows-authored documents write relative assets with ``\``.
        # On POSIX ``\`` is a plain filename character, so the check must
        # normalise it to ``/`` before probing the filesystem.
        self.touch("img/logo.png")
        self.assertEqual(
            self.check("![a](img\\logo.png)\n"),
            [("img\\logo.png", "ok")])

    def test_windows_backslash_separator_missing_is_broken(self):
        self.assertEqual(
            self.check("![a](img\\missing.png)\n"),
            [("img\\missing.png", "broken")])

    def test_root_relative_path_resolves_against_base_dir(self):
        self.touch("assets/logo.png")
        self.assertEqual(
            self.check("![a](/assets/logo.png)\n"),
            [("/assets/logo.png", "ok")])

    def test_titled_and_angle_bracket_targets(self):
        self.touch("logo.png")
        text = ('![a](logo.png "the logo")\n'
                '![b](<logo.png>)\n')
        self.assertEqual(
            self.check(text),
            [("logo.png", "ok"), ("logo.png", "ok")])

    def test_percent_encoded_and_query_fragment_are_decoded(self):
        self.touch("my image.png")
        text = ("![a](my%20image.png)\n"
                "![b](missing.png?cache=1#frag)\n")
        self.assertEqual(
            self.check(text),
            [("my%20image.png", "ok"), ("missing.png?cache=1#frag", "broken")])


class SkippedAssetTests(_AssetFixture):
    """Non-local / in-document image targets are skipped, not broken."""

    def test_non_local_schemes_are_skipped(self):
        text = ("![r](https://example.com/a.png)\n"
                "![d](data:image/png;base64,AAAA)\n"
                "![m](mailto:a@b.com)\n"
                "![f](ftp://example.com/a.png)\n")
        self.assertEqual(
            self.check(text),
            [("https://example.com/a.png", "skipped"),
             ("data:image/png;base64,AAAA", "skipped"),
             ("mailto:a@b.com", "skipped"),
             ("ftp://example.com/a.png", "skipped")])

    def test_fragment_only_reference_is_skipped(self):
        self.assertEqual(self.check("![a](#section)\n"),
                         [("#section", "skipped")])

    def test_inline_image_with_no_target_is_ignored(self):
        # ``![alt]()`` has an empty destination: nothing to check.
        self.assertEqual(self.check("![alt]()\n"), [])


class CodeFenceTests(_AssetFixture):
    """Images inside fenced/inline code are not real asset references."""

    def test_image_inside_fence_is_ignored(self):
        text = "```\n![x](never-checked.png)\n```\n"
        self.assertEqual(self.check(text), [])

    def test_image_inside_inline_code_is_ignored(self):
        self.assertEqual(self.check("text `![x](never.png)` more\n"), [])


class ReferenceStyleImageTests(_AssetFixture):
    """``![alt][id]`` reference images resolved via ``[id]: src``."""

    def test_bare_definition_resolves(self):
        self.touch("logo.png")
        text = "[logo]: logo.png\n\n![x][logo]\n"
        self.assertEqual(self.check(text), [("logo.png", "ok")])

    def test_definition_with_title_keeps_only_the_path(self):
        self.touch("logo.png")
        text = '[logo]: logo.png "the logo"\n\n![x][logo]\n'
        self.assertEqual(self.check(text), [("logo.png", "ok")])

    def test_angle_bracket_definition_resolves(self):
        self.touch("logo.png")
        text = "[logo]: <logo.png>\n\n![x][logo]\n"
        self.assertEqual(self.check(text), [("logo.png", "ok")])

    def test_angle_bracket_definition_may_contain_spaces(self):
        # CommonMark allows spaces inside an angle-bracket destination.
        self.touch("my logo.png")
        text = '[logo]: <my logo.png> "alt"\n\n![x][logo]\n'
        self.assertEqual(self.check(text), [("my logo.png", "ok")])

    def test_missing_definition_target_is_broken(self):
        text = "[logo]: missing.png\n\n![x][logo]\n"
        self.assertEqual(self.check(text), [("missing.png", "broken")])

    def test_first_definition_wins_for_duplicate_ids(self):
        # CommonMark: later duplicate definitions are ignored.
        self.touch("first.png")
        text = "[logo]: first.png\n[logo]: second.png\n\n![x][logo]\n"
        self.assertEqual(self.check(text), [("first.png", "ok")])

    def test_undefined_reference_is_ignored(self):
        self.assertEqual(self.check("![x][nope]\n"), [])


if __name__ == "__main__":
    unittest.main()
