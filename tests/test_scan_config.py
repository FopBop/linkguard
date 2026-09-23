"""Tests for FEATURE 5 - recursive scan + config + ignore rules.

Coverage (ARCHITECTURE_v1.md section 6.2):
  happy path  -> a directory target discovers ``**/*.md`` recursively;
                 ``exclude`` globs drop files from a directory scan; ``ignore``
                 rules downgrade matching links to ``skipped``
  error path  -> a malformed config file makes the CLI exit 2; a config inside
                 the scan target applies even when cwd is elsewhere (D2)
Exercises both the unit-level helpers (``discover_paths`` /
``apply_ignores``) and the end-to-end CLI contract. The runtime module is
loaded by path; fixtures are created under a throwaway temp tree so no repo
state is touched.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_MODULE_PATH = os.path.join(_ROOT, "linkguard.py")

_spec = importlib.util.spec_from_file_location("linkguard_core", _MODULE_PATH)
lg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lg)


def _run(*args, **kwargs):
    """Invoke the CLI with ``args`` from ``cwd`` (default: repo root)."""
    cwd = kwargs.pop("cwd", _ROOT)
    return subprocess.run(
        [sys.executable, _MODULE_PATH] + list(args),
        cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True,
    )


class _TreeFixture(unittest.TestCase):
    """Create a small multi-directory Markdown tree in a temp dir."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="linkguard-scan-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        os.makedirs(os.path.join(self.tmp, "docs", "deep"))
        os.makedirs(os.path.join(self.tmp, "vendor"))
        self._write("README.md", "# Top\n[doc](docs/guide.md)\n")
        self._write("docs/guide.md", "# Guide\n[deep](deep/leaf.md)\n")
        self._write("docs/deep/leaf.md", "# Leaf\n[home](../../README.md)\n")
        self._write("vendor/skipme.md", "# Vendor\n[gone](nope.md)\n")

    def _write(self, rel, text):
        path = os.path.join(self.tmp, rel)
        with open(path, "w") as fh:
            fh.write(text)
        return path


class DirectoryScanTests(_TreeFixture):
    """Happy path: recursive discovery of ``**/*.md``."""

    def test_discovers_markdown_recursively(self):
        found = lg.discover_paths([self.tmp])
        self.assertEqual(
            [os.path.basename(p) for p in found],
            ["README.md", "leaf.md", "guide.md", "skipme.md"],
        )

    def test_non_markdown_files_are_not_discovered(self):
        with open(os.path.join(self.tmp, "notes.txt"), "w") as fh:
            fh.write("not markdown\n")
        found = lg.discover_paths([self.tmp])
        self.assertNotIn("notes.txt", [os.path.basename(p) for p in found])

    def test_explicit_file_target_is_returned(self):
        target = os.path.join(self.tmp, "README.md")
        self.assertEqual(lg.discover_paths([target]), [target])

    def test_missing_target_raises_oserror(self):
        with self.assertRaises(OSError):
            lg.discover_paths([os.path.join(self.tmp, "does-not-exist")])


class ExcludeGlobTests(_TreeFixture):
    """Happy path: exclude globs drop files from a directory scan."""

    def test_exclude_glob_drops_matching_files(self):
        found = lg.discover_paths([self.tmp], exclude_globs=["vendor/*"])
        self.assertNotIn("skipme.md", [os.path.basename(p) for p in found])
        self.assertIn("guide.md", [os.path.basename(p) for p in found])

    def test_exclude_does_not_hide_explicit_file_targets(self):
        target = os.path.join(self.tmp, "vendor", "skipme.md")
        found = lg.discover_paths([target], exclude_globs=["vendor/*"])
        self.assertEqual(found, [target])


class IgnoreRuleTests(unittest.TestCase):
    """Happy path: ``ignore`` rules downgrade matching links to ``skipped``."""

    def test_apply_ignores_downgrades_broken_matching_url(self):
        link = lg.Link("https://ignore-me.example/x", 1, 1)
        link.status = "broken"
        cfg = lg.Config(ignore=["https://ignore-me.example/*"])
        lg.apply_ignores([link], cfg)
        self.assertEqual(link.status, "skipped")

    def test_non_matching_broken_url_is_left_broken(self):
        link = lg.Link("https://keep.example/x", 1, 1)
        link.status = "broken"
        cfg = lg.Config(ignore=["https://ignore-me.example/*"])
        lg.apply_ignores([link], cfg)
        self.assertEqual(link.status, "broken")


class ConfigErrorPathTests(_TreeFixture):
    """Error path: a malformed config makes the CLI exit 2."""

    def test_malformed_config_exits_usage(self):
        bad = os.path.join(self.tmp, "bad.cfg")
        with open(bad, "w") as fh:
            fh.write("[linkguard]\ntimeout = not-a-number\n")
        proc = _run(os.path.join(self.tmp, "README.md"), "--config", bad)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", proc.stderr)

    def test_scan_honours_config_exclude_end_to_end(self):
        # A config that excludes the vendor tree and ignores nothing.
        cfg = os.path.join(self.tmp, "linkguard.cfg")
        with open(cfg, "w") as fh:
            fh.write("[linkguard]\nexclude = vendor/*\n")
        proc = _run(self.tmp, "--config", cfg, "--json")
        report = json.loads(proc.stdout)
        scanned = [os.path.basename(f["file"]) for f in report["files"]]
        self.assertNotIn("skipme.md", scanned)
        self.assertIn("guide.md", scanned)


class AutoDiscoveryFromTargetTests(_TreeFixture):
    """D2: a config inside the scan target applies when cwd is elsewhere.

    VALIDATION.md finding D2: README documents auto-discovery from each scan
    target directory, but the code previously discovered from the current
    working directory, so scanning a target from outside it silently ignored
    the target's own config. This is the end-to-end reproduction of D2.
    """

    def test_target_config_ignores_broken_link_from_unrelated_cwd(self):
        # A config in the target tree downgrades the broken link below.
        with open(os.path.join(self.tmp, ".linkguard.yml"), "w") as fh:
            fh.write("ignore: nope.md\n")
        # Run with cwd OUTSIDE the target tree (each target dir is the arg).
        proc = _run(self.tmp, "--no-network", cwd=os.path.dirname(self.tmp))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("ignored by config", proc.stdout)

    def test_explicit_file_target_uses_own_directory_config(self):
        target = os.path.join(self.tmp, "vendor", "skipme.md")
        with open(os.path.join(self.tmp, "vendor", ".linkguard.yml"), "w") as fh:
            fh.write("ignore: nope.md\n")
        proc = _run(target, "--no-network", cwd=os.path.dirname(self.tmp))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("ignored by config", proc.stdout)


if __name__ == "__main__":
    unittest.main()
