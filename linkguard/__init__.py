"""linkguard - thin importable facade over the ``linkguard.py`` module.

Public API (ARCHITECTURE_v1.md section 3.2, semver-stable within v1)::

    from linkguard import (
        Link, extract_links, classify, run, __version__,
    )

No logic lives here; this package only re-exports the stable surface defined
by the single-file CLI so it can be used programmatically.
"""

import os
import sys

# The single-file module lives one directory above this package. Add that
# directory to sys.path so ``import linkguard_core`` works both from a source
# checkout (``python -m linkguard``) and from an installed wheel.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Import the implementation module under a private alias. The on-disk file is
# ``linkguard.py`` at the repo root; to avoid shadowing this package we load it
# explicitly by path.
import importlib.util as _util

_SPEC = _util.spec_from_file_location(
    "linkguard_core", os.path.join(_ROOT, "linkguard.py")
)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - defensive
    raise ImportError("linkguard: cannot locate linkguard.py at %s" % _ROOT)
_core = _util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_core)

# --- public surface ---------------------------------------------------------

Link = _core.Link
extract_links = _core.extract_links
classify = _core.classify
main = _core.main
# ``run`` is the programmatic entry point: ``main`` returns a process exit
# code rather than raising, which is what callers of ``run`` expect.
run = _core.main
# ``run_cli`` is the zero-argument console-script target declared in
# pyproject.toml (``[project.scripts] linkguard = "linkguard:run_cli"``).
# It ignores argv (the CLI reads sys.argv via ``main``'s default).
def run_cli():  # pragma: no cover - thin wrapper
    return _core.main()
__version__ = _core.__version__

__all__ = [
    "Link",
    "extract_links",
    "classify",
    "run",
    "main",
    "run_cli",
    "__version__",
]
