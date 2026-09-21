"""Guard test: the runtime must import standard library modules only.

ARCHITECTURE_v1.md sections 1.2 and 6.3 mandate a *zero third-party runtime
dependency* product. This test enforces that promise at test time by parsing
``linkguard.py`` with :mod:`ast` and asserting every top-level imported module
is in the stdlib allow-list.

This test is fully functional as of the scaffold commit: it passes even while
the feature bodies are still stubs, and will keep guarding future edits.
"""

import ast
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_MODULE_PATH = os.path.join(_ROOT, "linkguard.py")

# Explicit allow-list of permitted top-level module roots. Keep alphabetical.
# Extend only with genuine Python standard-library modules.
STDLIB_ALLOWLIST = {
    "argparse",
    "ast",
    "collections",
    "configparser",
    "dataclasses",
    "fnmatch",
    "glob",
    "io",
    "json",
    "os",
    "pathlib",
    "re",
    "sys",
    "typing",
    "urllib",
}


def _imported_roots(tree):
    """Return the set of top-level module names imported by ``tree``."""
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (level > 0) are intra-package, always allowed.
            if node.level and node.level > 0:
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


class NoThirdPartyImportsTests(unittest.TestCase):
    def test_module_exists(self):
        self.assertTrue(os.path.isfile(_MODULE_PATH),
                        "linkguard.py not found at %s" % _MODULE_PATH)

    def test_only_stdlib_imports(self):
        with open(_MODULE_PATH, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=_MODULE_PATH)
        roots = _imported_roots(tree)

        offenders = sorted(r for r in roots if r not in STDLIB_ALLOWLIST)
        self.assertEqual(
            offenders, [],
            "third-party import(s) detected in linkguard.py: %s. "
            "linkguard must remain standard-library only."
            % ", ".join(offenders),
        )

        # Sanity: every allow-listed module we actually import is importable on
        # this interpreter (guards against typos in the allow-list itself).
        for root in sorted(roots):
            self.assertIn(root, sys.stdlib_module_names
                          if hasattr(sys, "stdlib_module_names") else {root},
                          "%s is not a stdlib module" % root)


if __name__ == "__main__":
    unittest.main()
