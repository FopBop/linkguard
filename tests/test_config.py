"""Tests for FEATURE 5 - config file loading (ARCHITECTURE_v1.md section 3.6).

Scope: the config-loading code only (``load_config`` / ``Config``) plus the
observable behaviour it drives (``apply_ignores`` and ``extra_skip_schemes``).
Directory scanning and CLI wiring (the rest of FEATURE 5/6) are covered
elsewhere.

Coverage:
  happy path  -> a config file's values are loaded (both ``linkguard.cfg`` and
                 ``.linkguard.yml``) and a matching ``ignore`` rule / extra
                 skip scheme changes classification behaviour
  error path  -> malformed config raises ``ConfigError`` with a clear message
  discovery   -> nearest file wins; explicit path overrides discovery

The implementation module lives at the repo root (``linkguard.py``); it is
loaded explicitly by path because the ``linkguard`` package facade currently
re-exports not-yet-implemented CLI entry points (FEATURE 6).
"""

import importlib.util
import os
import shutil
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_MODULE_PATH = os.path.join(_ROOT, "linkguard.py")

_spec = importlib.util.spec_from_file_location("linkguard_core", _MODULE_PATH)
lg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lg)


class _TempDirCase(unittest.TestCase):
    """Base case giving each test an isolated temporary directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="linkguard-cfg-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write(self, relpath, content):
        """Write ``content`` to ``relpath`` under the temp dir; return path."""
        path = os.path.join(self.tmp, relpath)
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path


class DefaultsTests(_TempDirCase):
    def test_no_config_yields_builtin_defaults(self):
        cfg = lg.load_config(self.tmp)
        self.assertEqual(cfg.exclude, [])
        self.assertEqual(cfg.ignore, [])
        self.assertEqual(cfg.extra_skip_schemes, [])
        self.assertEqual(cfg.timeout, lg.DEFAULT_TIMEOUT)
        self.assertFalse(cfg.no_network)
        self.assertIsNone(cfg.path)
        self.assertEqual(cfg.source, "default")


class IniConfigTests(_TempDirCase):
    def test_ini_config_values_are_loaded(self):
        self.write("linkguard.cfg", (
            "[linkguard]\n"
            "exclude = node_modules/*, vendor/*\n"
            "ignore = https://ignore-me.example/*\n"
            "extra_skip_schemes = ftp, ssh\n"
            "timeout = 7.5\n"
            "no_network = true\n"
        ))
        cfg = lg.load_config(self.tmp)
        self.assertEqual(cfg.exclude, ["node_modules/*", "vendor/*"])
        self.assertEqual(cfg.ignore, ["https://ignore-me.example/*"])
        self.assertEqual(cfg.extra_skip_schemes, ["ftp", "ssh"])
        self.assertEqual(cfg.timeout, 7.5)
        self.assertTrue(cfg.no_network)
        self.assertEqual(cfg.source, "linkguard.cfg")

    def test_multiline_list_values_are_split(self):
        self.write("linkguard.cfg", (
            "[linkguard]\n"
            "exclude =\n"
            "    build/*\n"
            "    dist/*\n"
        ))
        cfg = lg.load_config(self.tmp)
        self.assertEqual(cfg.exclude, ["build/*", "dist/*"])


class YamlConfigTests(_TempDirCase):
    def test_yaml_config_values_are_loaded(self):
        self.write(".linkguard.yml", (
            "linkguard:\n"
            "  exclude:\n"
            "    - node_modules/*\n"
            "    - vendor/*\n"
            "  ignore:\n"
            "    - https://ignore-me.example/*\n"
            "  extra_skip_schemes: ftp, ssh\n"
            "  timeout: 3\n"
        ))
        cfg = lg.load_config(self.tmp)
        self.assertEqual(cfg.exclude, ["node_modules/*", "vendor/*"])
        self.assertEqual(cfg.ignore, ["https://ignore-me.example/*"])
        self.assertEqual(cfg.extra_skip_schemes, ["ftp", "ssh"])
        self.assertEqual(cfg.timeout, 3.0)
        self.assertEqual(cfg.source, ".linkguard.yml")


class DiscoveryTests(_TempDirCase):
    def test_nearest_config_wins(self):
        self.write("linkguard.cfg", "[linkguard]\ntimeout = 1\n")
        nested = os.path.join(self.tmp, "sub", "deeper")
        os.makedirs(nested)
        self.write(os.path.join("sub", "deeper", "linkguard.cfg"),
                   "[linkguard]\ntimeout = 99\n")
        cfg = lg.load_config(nested)
        self.assertEqual(cfg.timeout, 99.0)

    def test_explicit_path_overrides_discovery(self):
        self.write("linkguard.cfg", "[linkguard]\ntimeout = 1\n")
        other = self.write(os.path.join("elsewhere", "custom.cfg"),
                           "[linkguard]\ntimeout = 42\n")
        cfg = lg.load_config(self.tmp, explicit_path=other)
        self.assertEqual(cfg.timeout, 42.0)
        self.assertEqual(cfg.path, other)

    def test_ini_preferred_over_yaml_in_same_dir(self):
        self.write("linkguard.cfg", "[linkguard]\ntimeout = 5\n")
        self.write(".linkguard.yml", "timeout: 11\n")
        cfg = lg.load_config(self.tmp)
        self.assertEqual(cfg.source, "linkguard.cfg")
        self.assertEqual(cfg.timeout, 5.0)


class MalformedConfigTests(_TempDirCase):
    def test_missing_explicit_file_raises(self):
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp,
                           explicit_path=os.path.join(self.tmp, "nope.cfg"))
        self.assertIn("not found", str(ctx.exception))

    def test_missing_section_raises(self):
        path = self.write("linkguard.cfg", "[wrong]\ntimeout = 1\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp, explicit_path=path)
        self.assertIn("[linkguard]", str(ctx.exception))

    def test_unknown_key_raises(self):
        path = self.write("linkguard.cfg", "[linkguard]\ntimout = 5\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp, explicit_path=path)
        self.assertIn("unknown config key", str(ctx.exception))

    def test_non_numeric_timeout_raises(self):
        path = self.write("linkguard.cfg", "[linkguard]\ntimeout = soon\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp, explicit_path=path)
        self.assertIn("timeout", str(ctx.exception))

    def test_non_positive_timeout_raises(self):
        path = self.write("linkguard.cfg", "[linkguard]\ntimeout = 0\n")
        with self.assertRaises(lg.ConfigError):
            lg.load_config(self.tmp, explicit_path=path)

    def test_bad_boolean_raises(self):
        path = self.write("linkguard.cfg", "[linkguard]\nno_network = maybe\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp, explicit_path=path)
        self.assertIn("boolean", str(ctx.exception))

    def test_malformed_ini_syntax_raises(self):
        path = self.write("linkguard.cfg", "[linkguard]\nkey without colon\n")
        with self.assertRaises(lg.ConfigError):
            lg.load_config(self.tmp, explicit_path=path)

    def test_yaml_orphan_list_item_raises(self):
        path = self.write(".linkguard.yml", "- orphan\n")
        with self.assertRaises(lg.ConfigError):
            lg.load_config(self.tmp, explicit_path=path)


class BehaviourChangeTests(_TempDirCase):
    """A sample config file must alter tool behaviour (success criterion)."""

    def _broken_link(self, url):
        link = lg.Link(url, line=1, column=1)
        link.status = "broken"
        link.target_type = "remote"
        link.error = "HTTP 404"
        return link

    def test_ignore_rule_downgrades_broken_link(self):
        self.write("linkguard.cfg", (
            "[linkguard]\n"
            "ignore = https://ignore-me.example/*\n"
        ))
        cfg = lg.load_config(self.tmp)

        ignored = self._broken_link("https://ignore-me.example/gone")
        kept = self._broken_link("https://real-broken.example/gone")
        lg.apply_ignores([ignored, kept], cfg)

        self.assertEqual(ignored.status, "skipped")
        self.assertEqual(ignored.error, "ignored by config")
        # A non-matching link stays broken -> proof the rule is specific.
        self.assertEqual(kept.status, "broken")

    def test_ignore_substring_rule_matches(self):
        self.write("linkguard.cfg", "[linkguard]\nignore = archive/\n")
        cfg = lg.load_config(self.tmp)
        link = self._broken_link("./archive/old.pdf")
        lg.apply_ignores([link], cfg)
        self.assertEqual(link.status, "skipped")

    def test_without_config_ignore_link_stays_broken(self):
        cfg = lg.load_config(self.tmp)  # no config file present
        link = self._broken_link("https://ignore-me.example/gone")
        lg.apply_ignores([link], cfg)
        self.assertEqual(link.status, "broken")

    def test_extra_skip_scheme_changes_classification(self):
        self.write("linkguard.cfg",
                   "[linkguard]\nextra_skip_schemes = ftp\n")
        cfg = lg.load_config(self.tmp)

        link = lg.Link("ftp://files.example/pub", line=1, column=1)
        lg.classify(link, allow_network=True, timeout=cfg.timeout,
                    extra_skip_schemes=cfg.extra_skip_schemes)
        self.assertEqual(link.status, "skipped")
        self.assertEqual(link.target_type, "skipped")

        # Without the config the same scheme is treated as unsupported
        # (still skipped, but via the built-in path) - assert the config
        # message is what distinguishes it.
        self.assertIn("config", link.error)


class NestedYamlBlockTests(_TempDirCase):
    """The documented ``linkguard:`` wrapper block in ``.linkguard.yml``.

    ARCHITECTURE_v1.md section 3.6 shows the YAML form mirroring the INI
    ``[linkguard]`` section, i.e. a single top-level ``linkguard:`` key with
    the real keys indented under it. These tests pin that contract and the
    validation that rejects bad nesting.
    """

    def test_wrapper_block_loads_scalars_and_lists(self):
        self.write(".linkguard.yml", (
            "# wrapper form mirrors the INI section\n"
            "linkguard:\n"
            "  exclude:\n"
            "    - node_modules/*\n"
            "    - vendor/*\n"
            "  ignore:\n"
            "    - https://ignore-me.example/*\n"
            "  timeout: 3\n"
            "  no_network: true\n"
        ))
        cfg = lg.load_config(self.tmp)

        self.assertEqual(cfg.exclude, ["node_modules/*", "vendor/*"])
        self.assertEqual(cfg.ignore, ["https://ignore-me.example/*"])
        self.assertEqual(cfg.timeout, 3)
        self.assertTrue(cfg.no_network)

    def test_wrapper_block_behaves_like_flat_form(self):
        """.linkguard.yml nested block must alter behaviour, not just parse."""
        self.write(".linkguard.yml", (
            "linkguard:\n"
            "  ignore:\n"
            "    - https://ignore-me.example/*\n"
            "  extra_skip_schemes:\n"
            "    - ftp\n"
        ))
        cfg = lg.load_config(self.tmp)

        link = lg.Link("https://ignore-me.example/gone", line=1, column=1)
        link.status = "broken"
        link.target_type = "remote"
        link.error = "HTTP 404"
        lg.apply_ignores([link], cfg)
        self.assertEqual(link.status, "skipped")
        self.assertEqual(link.error, "ignored by config")

        ftp = lg.Link("ftp://files.example/pub", line=1, column=1)
        lg.classify(ftp, allow_network=True, timeout=cfg.timeout,
                    extra_skip_schemes=cfg.extra_skip_schemes)
        self.assertIn("config", ftp.error)

    def test_dedented_key_after_block_is_error(self):
        """The wrapper is the whole document; a dedented key is malformed.

        We reject rather than guess at mixed block/flat layouts so the user
        gets a precise line number instead of a silently ignored key.
        """
        self.write(".linkguard.yml", (
            "linkguard:\n"
            "  timeout: 5\n"
            "no_network: true\n"
        ))
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp)
        self.assertIn(".linkguard.yml:3", str(ctx.exception))

    def test_list_item_under_wrapper_without_key_is_error(self):
        self.write(".linkguard.yml", "linkguard:\n  - stray\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp)
        self.assertIn("list item without a parent key", str(ctx.exception))

    def test_unindented_key_inside_block_is_error(self):
        self.write(".linkguard.yml", "linkguard:\n  timeout: 3\nexclude: x\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp)
        # ``exclude`` dedents back to the block header level -> nesting error.
        self.assertIn(".linkguard.yml:3", str(ctx.exception))

    def test_deeply_nested_key_is_error(self):
        """Only one nesting level is allowed; deeper keys are unknown."""
        self.write(".linkguard.yml", (
            "linkguard:\n"
            "  exclude:\n"
            "    nested: oops\n"
        ))
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp)
        msg = str(ctx.exception)
        self.assertIn("nested", msg)
        self.assertIn("valid keys", msg)

    def test_duplicate_wrapper_block_is_error(self):
        self.write(".linkguard.yml", "linkguard:\nlinkguard:\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp)
        self.assertIn("duplicate 'linkguard:' block", str(ctx.exception))


class MalformedConfigErrorTests(_TempDirCase):
    """Malformed config must surface a clear, actionable message."""

    def test_bad_timeout_in_yaml_names_file_and_key(self):
        self.write(".linkguard.yml", "timeout: soon\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp)
        msg = str(ctx.exception)
        self.assertIn(".linkguard.yml", msg)
        self.assertIn("timeout", msg)

    def test_bad_boolean_in_yaml(self):
        self.write(".linkguard.yml", "no_network: maybe\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp)
        self.assertIn("boolean", str(ctx.exception))

    def test_unknown_key_in_ini_is_rejected(self):
        self.write("linkguard.cfg", "[linkguard]\nbogus = 1\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp)
        msg = str(ctx.exception)
        self.assertIn("linkguard.cfg", msg)
        self.assertIn("bogus", msg)

    def test_ini_missing_section_is_rejected(self):
        self.write("linkguard.cfg", "timeout = 3\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp)
        self.assertIn("linkguard.cfg", str(ctx.exception))


class IgnorePatternValidationTests(_TempDirCase):
    """``ignore`` entries are substrings *or* regexes (docs/CONFIG.md).

    A malformed regex is malformed config and must fail fast at load time with
    a message naming the file and the offending pattern, instead of being
    silently dropped at match time.
    """

    def test_invalid_regex_in_ignore_is_rejected(self):
        path = self.write("linkguard.cfg",
                          "[linkguard]\nignore = (unclosed\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp, explicit_path=path)
        msg = str(ctx.exception)
        self.assertIn("linkguard.cfg", msg)
        self.assertIn("invalid regex", msg)
        self.assertIn("(unclosed", msg)

    def test_invalid_regex_in_yaml_ignore_is_rejected(self):
        self.write(".linkguard.yml",
                   "ignore:\n  - '(unbalanced'\n")
        with self.assertRaises(lg.ConfigError) as ctx:
            lg.load_config(self.tmp)
        msg = str(ctx.exception)
        self.assertIn(".linkguard.yml", msg)
        self.assertIn("invalid regex", msg)

    def test_valid_regex_in_ignore_is_accepted_and_matches(self):
        """A well-formed regex must load and actually suppress a broken link."""
        self.write("linkguard.cfg",
                   "[linkguard]\nignore = ^https?://old\\.example/.*$\n")
        cfg = lg.load_config(self.tmp)
        self.assertEqual(cfg.ignore, [r"^https?://old\.example/.*$"])

        link = lg.Link("https://old.example/gone", line=1, column=1)
        link.status = "broken"
        link.target_type = "remote"
        link.error = "HTTP 404"
        lg.apply_ignores([link], cfg)
        self.assertEqual(link.status, "skipped")
        self.assertEqual(link.error, "ignored by config")

    def test_glob_substring_ignore_not_treated_as_regex(self):
        """Glob/substring patterns must not trip the regex validation."""
        self.write("linkguard.cfg",
                   "[linkguard]\nignore = node_modules/*\n")
        cfg = lg.load_config(self.tmp)
        self.assertEqual(cfg.ignore, ["node_modules/*"])


if __name__ == "__main__":
    unittest.main()
