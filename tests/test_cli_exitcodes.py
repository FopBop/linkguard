"""Tests for FEATURE 6 - full CLI surface: exit codes 0/1/2 and CLI flags.

Coverage (ARCHITECTURE_v1.md section 6.2 and docs/USAGE.md):
  happy path  -> clean input => exit 0
  error path  -> broken link => exit 1; bad usage / unreadable => exit 2
  flags       -> text mode prints a report (D1); every documented flag is
                 accepted (D2); config + ignores apply (D3); directory scan and
                 default ``.`` work (D4); ``--no-network``/``--timeout`` reach
                 ``classify`` (D5); ``--output`` writes a file (D6);
                 ``--version``/``--help`` exit 0 (D7).

Each regression test names the defect id from CHECKPOINT_MVP.md it guards.
The CLI is exercised as a subprocess exactly as CI would (real stdout/stderr/
exit code), with all fixtures created in a temp tree so no repo state is
touched.
"""

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


def _run(*args, **kwargs):
    """Invoke the CLI with ``args`` from ``cwd`` (default: repo root)."""
    cwd = kwargs.pop("cwd", _ROOT)
    return subprocess.run(
        [sys.executable, _MODULE_PATH] + list(args),
        cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True,
    )


class _FixtureMixin(object):
    """Build the CHECKPOINT_MVP.md fixture in a throwaway temp directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="linkguard-cli-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        os.makedirs(os.path.join(self.tmp, "docs"))
        os.makedirs(os.path.join(self.tmp, "assets"))

        with open(os.path.join(self.tmp, "README.md"), "w") as fh:
            fh.write(
                "# Fixture Project\n\n"
                "See [the docs](docs/guide.md) and "
                "[guide anchor](docs/guide.md#usage).\n\n"
                "Broken relative link: [missing](docs/nope.md)\n"
                "Anchor link to own section: [jump](#fixture-project)\n\n"
                "Image asset good: ![logo](assets/logo.svg)\n"
                "Image asset ghost: ![ghost](assets/ghost.png)\n"
            )
        with open(os.path.join(self.tmp, "docs", "guide.md"), "w") as fh:
            fh.write(
                "# Guide\n\n## Usage\n\n"
                "![diagram](../assets/logo.svg)\n\n"
                "Broken anchor: [fake](#does-not-exist)\n"
            )
        with open(os.path.join(self.tmp, "assets", "logo.svg"), "w") as fh:
            fh.write('<svg xmlns="http://www.w3.org/2000/svg"></svg>\n')
        with open(os.path.join(self.tmp, "linkguard.cfg"), "w") as fh:
            fh.write(
                "[linkguard]\n"
                "exclude = docs/ignored.md\n"
                "ignore = nope.md\n"
                "no_network = true\n"
            )


class CliTextModeTests(_FixtureMixin, unittest.TestCase):
    """D1: text mode must render a human-readable report."""

    def test_text_mode_prints_report_on_broken_file(self):
        """D1 regression: broken file exits 1 *and* prints findings."""
        proc = _run(os.path.join(self.tmp, "README.md"))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("[broken]", proc.stdout)
        self.assertIn("docs/nope.md", proc.stdout)
        # The summary line must be present too.
        self.assertIn("links:", proc.stdout)

    def test_text_mode_clean_file_exits_zero(self):
        clean = os.path.join(self.tmp, "clean.md")
        with open(clean, "w") as fh:
            fh.write("# Clean\n[ok](docs/guide.md)\n")
        proc = _run(clean)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("[ok]", proc.stdout)


class CliFlagSurfaceTests(_FixtureMixin, unittest.TestCase):
    """D2: every documented flag must be accepted (no exit-2 'unknown option')."""

    def test_no_network_flag_accepted(self):
        proc = _run(os.path.join(self.tmp, "README.md"), "--no-network")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertNotIn("unknown option", proc.stderr)

    def test_quiet_suppresses_ok_findings(self):
        proc = _run(os.path.join(self.tmp, "README.md"), "--quiet")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertNotIn("[ok]", proc.stdout)
        self.assertIn("[broken]", proc.stdout)

    def test_timeout_flag_accepted(self):
        proc = _run(os.path.join(self.tmp, "README.md"), "--timeout", "3")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertNotIn("unknown option", proc.stderr)

    def test_timeout_flag_rejects_junk(self):
        proc = _run(os.path.join(self.tmp, "README.md"), "--timeout", "abc")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--timeout", proc.stderr)

    def test_exclude_flag_accepted_and_applied(self):
        proc = _run(self.tmp, "--exclude", "docs/*")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        # docs/guide.md must no longer be *scanned* (its own finding gone).
        self.assertNotIn("guide.md:7", proc.stdout)

    def test_unknown_option_still_exits_two(self):
        proc = _run(os.path.join(self.tmp, "README.md"), "--bogus")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown option", proc.stderr)


class CliConfigTests(_FixtureMixin, unittest.TestCase):
    """D3: config discovery/loading and ignore rules must reach `main`."""

    def test_explicit_config_ignore_downgrades_broken_link(self):
        proc = _run(os.path.join(self.tmp, "README.md"),
                    "--config", os.path.join(self.tmp, "linkguard.cfg"),
                    "--json")
        report = json.loads(proc.stdout)
        statuses = {l["url"]: l["status"]
                    for l in report["files"][0]["links"]}
        self.assertEqual(statuses["docs/nope.md"], "skipped")

    def test_auto_discovered_config_is_applied(self):
        """Running from inside the fixture dir auto-discovers linkguard.cfg."""
        proc = _run("README.md", "--json", cwd=self.tmp)
        report = json.loads(proc.stdout)
        statuses = {l["url"]: l["status"]
                    for l in report["files"][0]["links"]}
        self.assertEqual(statuses["docs/nope.md"], "skipped")

    def test_missing_explicit_config_exits_two(self):
        proc = _run(os.path.join(self.tmp, "README.md"),
                    "--config", os.path.join(self.tmp, "nope.cfg"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("config", proc.stderr)

    def test_malformed_config_exits_two(self):
        bad = os.path.join(self.tmp, "bad.cfg")
        with open(bad, "w") as fh:
            fh.write("[linkguard]\ntimeout = not-a-number\n")
        proc = _run(os.path.join(self.tmp, "README.md"), "--config", bad)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", proc.stderr)


class CliDirectoryScanTests(_FixtureMixin, unittest.TestCase):
    """D4: directories are scanned recursively; no target defaults to `.`."""

    def test_directory_target_is_scanned(self):
        proc = _run(self.tmp)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        # Both files discovered: README.md and docs/guide.md.
        self.assertIn("docs/guide.md", proc.stdout)
        self.assertIn("README.md", proc.stdout)

    def test_default_dot_target_scans_cwd(self):
        proc = _run(cwd=self.tmp)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("docs/guide.md", proc.stdout)

    def test_missing_target_exits_two(self):
        proc = _run(os.path.join(self.tmp, "does-not-exist"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", proc.stderr)

    def test_exclude_glob_skips_discovered_file(self):
        proc = _run(self.tmp, "--exclude", "docs/guide.md")
        self.assertNotIn("docs/guide.md:7", proc.stdout)


class CliNetworkPolicyTests(_FixtureMixin, unittest.TestCase):
    """D5: --no-network / --timeout must reach `classify`."""

    def test_no_network_skips_remote_links(self):
        with open(os.path.join(self.tmp, "remote.md"), "w") as fh:
            fh.write("# R\n[remote](http://example.invalid/x)\n")
        proc = _run(os.path.join(self.tmp, "remote.md"),
                    "--no-network", "--json")
        report = json.loads(proc.stdout)
        link = report["files"][0]["links"][0]
        self.assertEqual(link["status"], "skipped")
        self.assertIn("--no-network", link["error"])

    def test_config_no_network_is_honoured(self):
        """The fixture config sets no_network=true; remote links skip."""
        with open(os.path.join(self.tmp, "remote.md"), "w") as fh:
            fh.write("# R\n[remote](http://example.invalid/x)\n")
        proc = _run(os.path.join(self.tmp, "remote.md"), "--json",
                    cwd=self.tmp)
        report = json.loads(proc.stdout)
        link = report["files"][-1]["links"][0]
        self.assertEqual(link["status"], "skipped")


class CliOutputTests(_FixtureMixin, unittest.TestCase):
    """D6: --output writes the report to a file instead of stdout."""

    def test_output_writes_sarif_file_and_stdout_is_empty(self):
        out = os.path.join(self.tmp, "out.sarif")
        proc = _run(os.path.join(self.tmp, "README.md"),
                    "--sarif", "--output", out)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(os.path.isfile(out))
        with open(out) as fh:
            log = json.load(fh)
        self.assertEqual(log["version"], "2.1.0")

    def test_output_json_to_file(self):
        out = os.path.join(self.tmp, "out.json")
        proc = _run(os.path.join(self.tmp, "README.md"),
                    "--json", "--output", out)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        with open(out) as fh:
            report = json.load(fh)
        self.assertEqual(report["exit_code"], 1)

    def test_unwritable_output_exits_two(self):
        bad = os.path.join(self.tmp, "no-such-dir", "out.json")
        proc = _run(os.path.join(self.tmp, "README.md"),
                    "--json", "--output", bad)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", proc.stderr)


class CliVersionHelpTests(unittest.TestCase):
    """D7: --version and -h/--help print and exit 0."""

    def test_version_prints_and_exits_zero(self):
        proc = _run("--version")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("linkguard", proc.stdout)
        self.assertIn("1.0.0", proc.stdout)

    def test_help_prints_usage_and_exits_zero(self):
        proc = _run("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("usage: linkguard", proc.stdout)

    def test_h_short_flag_prints_usage(self):
        proc = _run("-h")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("usage: linkguard", proc.stdout)


class CliExitCodeContractTests(_FixtureMixin, unittest.TestCase):
    """The exit-code contract itself (0 / 1 / 2)."""

    def test_clean_input_exits_zero(self):
        clean = os.path.join(self.tmp, "clean.md")
        with open(clean, "w") as fh:
            fh.write("# Clean\n[ok](docs/guide.md)\n")
        proc = _run(clean)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_broken_link_exits_one(self):
        proc = _run(os.path.join(self.tmp, "README.md"))
        self.assertEqual(proc.returncode, 1)

    def test_usage_error_exits_two(self):
        proc = _run("--json", "--sarif")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("mutually exclusive", proc.stderr)


if __name__ == "__main__":
    unittest.main()
