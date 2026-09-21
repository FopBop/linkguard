"""Tests for FEATURE 3 - JSON and SARIF report output.

Coverage (ARCHITECTURE_v1.md sections 3.3, 3.4 and 6.2):
  happy path  -> ``--json`` and ``--sarif`` output validate against the vendored
                 ``schemas/report.schema.json`` / ``schemas/sarif.schema.json``
                 (by the stdlib-only subset validator in ``schema_validator``)
  happy path  -> emitted SARIF carries severity, file, line and message for
                 every finding
  error path  -> ``--json --sarif`` together => exit 2 (mutual exclusion)

The runtime module is loaded directly by path (``linkguard.py``) so these tests
do not depend on the importable ``linkguard`` package facade.
"""

import importlib.util
import json
import os
import subprocess
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_MODULE_PATH = os.path.join(_ROOT, "linkguard.py")
_SCHEMA_DIR = os.path.join(_ROOT, "schemas")
_FIXTURES = os.path.join(_HERE, "fixtures")

# Make the sibling validator importable regardless of the discovery cwd.
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import schema_validator  # noqa: E402  (path set up above)


def _load_core():
    """Load the single-file ``linkguard.py`` module under a private name."""
    spec = importlib.util.spec_from_file_location("linkguard_core", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_schema(name):
    """Load a vendored JSON schema from ``schemas/``."""
    with open(os.path.join(_SCHEMA_DIR, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def _fixture_links(core, fixture, allow_network=False):
    """Run extraction + classification over a fixture, offline.

    Returns the classified ``Link`` list with ``source_file`` populated, ready
    to feed the renderers.
    """
    path = os.path.join("tests", "fixtures", fixture)
    with open(os.path.join(_FIXTURES, fixture), "r", encoding="utf-8") as fh:
        text = fh.read()
    links = core.extract_links(text)
    for link in links:
        link.source_file = path
        core.classify(link, allow_network=allow_network, timeout=1.0,
                      base_dir=_FIXTURES)
    return links


class JsonReportSchemaTests(unittest.TestCase):
    """``render_json`` output must satisfy ``schemas/report.schema.json``."""

    @classmethod
    def setUpClass(cls):
        cls.core = _load_core()
        cls.schema = _load_schema("report.schema.json")

    def test_fixture_run_validates_against_report_schema(self):
        links = _fixture_links(self.core, "sample.md")
        report = json.loads(self.core.render_json(["tests/fixtures/sample.md"],
                                                  links))
        errors = schema_validator.validate(report, self.schema)
        self.assertEqual(errors, [], "JSON report schema errors: %s" % errors)

    def test_single_file_report_keeps_backward_compatible_alias(self):
        """§3.3 compatibility note: exactly-one-file keeps the ``file`` key."""
        links = _fixture_links(self.core, "sample.md")
        report = json.loads(self.core.render_json(["tests/fixtures/sample.md"],
                                                  links))
        self.assertEqual(report["file"], os.path.normpath(
            "tests/fixtures/sample.md"))

    def test_summary_counts_match_emitted_links(self):
        links = _fixture_links(self.core, "sample.md")
        report = json.loads(self.core.render_json(["tests/fixtures/sample.md"],
                                                  links))
        emitted = report["files"][0]["links"]
        self.assertEqual(report["summary"]["total"], len(emitted))
        broken = sum(1 for link in emitted if link["status"] == "broken")
        self.assertEqual(report["summary"]["broken"], broken)


class SarifReportSchemaTests(unittest.TestCase):
    """``render_sarif`` output must satisfy ``schemas/sarif.schema.json``."""

    @classmethod
    def setUpClass(cls):
        cls.core = _load_core()
        cls.schema = _load_schema("sarif.schema.json")

    def test_fixture_run_validates_against_sarif_schema(self):
        links = _fixture_links(self.core, "sample.md")
        log = json.loads(self.core.render_sarif(["tests/fixtures/sample.md"],
                                                links))
        errors = schema_validator.validate(log, self.schema)
        self.assertEqual(errors, [], "SARIF schema errors: %s" % errors)

    def test_empty_findings_still_validate(self):
        """A run with no broken links must still be a valid SARIF log."""
        with open(os.path.join(_FIXTURES, "empty.md"), "r",
                  encoding="utf-8") as fh:
            text = fh.read()
        links = self.core.extract_links(text)
        for link in links:
            link.source_file = "tests/fixtures/empty.md"
            self.core.classify(link, allow_network=False, timeout=1.0,
                               base_dir=_FIXTURES)
        log = json.loads(self.core.render_sarif(["tests/fixtures/empty.md"],
                                                links))
        errors = schema_validator.validate(log, self.schema)
        self.assertEqual(errors, [], "empty SARIF run errors: %s" % errors)
        self.assertEqual(log["runs"][0]["results"], [])

    def test_findings_carry_severity_file_line_and_message(self):
        """Every result exposes severity, file, line and message (task spec)."""
        links = _fixture_links(self.core, "sample.md")
        log = json.loads(self.core.render_sarif(["tests/fixtures/sample.md"],
                                                links))

        sarif_rules = {rule["id"] for rule in log["runs"][0]["tool"]["driver"]["rules"]}
        broken = [link for link in links if link.status == "broken"]
        results = log["runs"][0]["results"]
        self.assertEqual(len(results), len(broken))
        self.assertTrue(results, "sample.md fixture must yield broken findings")

        for result in results:
            # severity
            self.assertEqual(result["level"], "error")
            self.assertIn(result["ruleId"], sarif_rules)
            # message
            self.assertIn("text", result["message"])
            self.assertTrue(result["message"]["text"])
            # file + line + column
            location = result["locations"][0]["physicalLocation"]
            self.assertTrue(location["artifactLocation"]["uri"])
            region = location["region"]
            self.assertIsInstance(region["startLine"], int)
            self.assertIsInstance(region["startColumn"], int)

    def test_remote_fixture_field_is_held_when_offline(self):
        """Offline fixture: only local/anchor breakages become results."""
        links = _fixture_links(self.core, "sample.md")
        log = json.loads(self.core.render_sarif(["tests/fixtures/sample.md"],
                                                links))
        rule_ids = {r["ruleId"] for r in log["runs"][0]["results"]}
        # sample.md has one missing anchor (#section) and one missing local file.
        self.assertEqual(rule_ids, {"LG002", "LG003"})


class OutputMutualExclusionTests(unittest.TestCase):
    """``--json`` and ``--sarif`` must be mutually exclusive => exit 2."""

    def test_json_and_sarif_together_exit_two(self):
        proc = subprocess.run(
            [sys.executable, _MODULE_PATH, "tests/fixtures/sample.md",
             "--json", "--sarif"],
            cwd=_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(proc.returncode, 2,
                         "expected exit 2, got %d (stderr=%s)"
                         % (proc.returncode, proc.stderr))


class SarifEndToEndTests(unittest.TestCase):
    """End-to-end: invoke the CLI ``--sarif`` on a fixture and parse the output.

    This is the acceptance path required by the task ("a passing test that
    parses the emitted output"). Unlike the unit tests above, it runs
    ``linkguard.py`` exactly as CI would, captures real stdout, and asserts the
    emitted bytes are parseable JSON with the per-finding fields the task
    mandates (severity, file, line, message) that satisfy the vendored schema.
    """

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema("sarif.schema.json")

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, _MODULE_PATH] + list(args),
            cwd=_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    def test_cli_sarif_on_broken_fixture_parses_and_validates(self):
        proc = self._run("tests/fixtures/sample.md", "--sarif")
        # A broken finding must fail CI with the "broken" exit code.
        self.assertEqual(proc.returncode, 1,
                         "expected exit 1, got %d (stderr=%s)"
                         % (proc.returncode, proc.stderr))

        # The emitted bytes must parse as a single JSON document.
        log = json.loads(proc.stdout)
        errors = schema_validator.validate(log, self.schema)
        self.assertEqual(errors, [],
                         "emitted SARIF schema errors: %s" % errors)

        run = log["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], "linkguard")
        results = run["results"]
        self.assertTrue(results, "broken fixture must emit >=1 result")

        # severity + file + line + message for every finding (task spec).
        for result in results:
            self.assertEqual(result["level"], "error")            # severity
            self.assertTrue(result["message"]["text"])            # message
            physical = result["locations"][0]["physicalLocation"]
            self.assertTrue(physical["artifactLocation"]["uri"])  # file
            region = physical["region"]
            self.assertIsInstance(region["startLine"], int)       # line
            self.assertGreaterEqual(region["startLine"], 1)

    def test_cli_sarif_on_clean_fixture_exits_zero_with_no_results(self):
        proc = self._run("tests/fixtures/empty.md", "--sarif")
        self.assertEqual(proc.returncode, 0,
                         "expected exit 0, got %d (stderr=%s)"
                         % (proc.returncode, proc.stderr))
        log = json.loads(proc.stdout)
        self.assertEqual(schema_validator.validate(log, self.schema), [])
        self.assertEqual(log["runs"][0]["results"], [])


if __name__ == "__main__":
    unittest.main()
