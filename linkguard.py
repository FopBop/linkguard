#!/usr/bin/env python3
"""linkguard - zero-dependency Markdown link/asset health checker.

v1 scaffold stub. This module defines the *public interfaces* specified in
``workspace/product/ARCHITECTURE_v1.md`` (see sections 2.2 and 3). The bodies
are intentionally not implemented yet: each function is documented with its
contracted signature and raises :class:`NotImplementedError`. The CLI entry
point (``main``) runs without crashing and prints a not-implemented message so
the scaffold can be smoke-tested.

Runtime constraints (ARCHITECTURE_v1.md section 1.2):
  * Python 3.8+ (stdlib only; no third-party imports, ever).
  * 3.8-clean syntax (no ``dict |``, no bare ``list[str]`` annotations, no
    ``match``).
  * No mandatory network / external services.

Build order (ARCHITECTURE_v1.md section 7) fills in the bodies feature by
feature; this file is step 1 of that order.
"""

import argparse
import sys

# --- constants --------------------------------------------------------------

__version__ = "0.1.0.0-alpha0"
USER_AGENT = "linkguard/0.1"
DEFAULT_TIMEOUT = 10.0
EXIT_OK = 0
EXIT_BROKEN = 1
EXIT_USAGE = 2
SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:")
CONFIG_FILENAMES = ("linkguard.cfg", ".linkguard.yml")


# --- data model -------------------------------------------------------------


class Link(object):
    """A single extracted link and its classification result.

    Attributes (ARCHITECTURE_v1.md section 2.2):
      url, line, column  -> where the link was found
      status             -> "ok" | "broken" | "skipped"
      http_status        -> int or None
      method             -> HTTP method or "LOCAL" or None
      error              -> human-readable reason or None
      target_type        -> "remote" | "local" | "anchor" | "skipped"
    """

    def __init__(self, url, line, column):
        self.url = url
        self.line = line
        self.column = column
        self.status = None
        self.http_status = None
        self.method = None
        self.error = None
        self.target_type = None

    def to_dict(self):
        """Return the stable JSON record (FEATURE 3 schema).

        Interface only; implementation lands with FEATURE 3.
        """
        raise NotImplementedError("Link.to_dict is not implemented in v1 scaffold")


# --- FEATURE 1: extraction --------------------------------------------------


def _strip_code(text):
    """Mask fenced code blocks, inline code spans and image links.

    Returns the same-length text with masked regions replaced by spaces so
    line/column offsets remain stable.
    """
    raise NotImplementedError("_strip_code is not implemented in v1 scaffold")


def extract_links(text):
    """Extract Markdown links from ``text``.

    Handles inline, titled, angle-bracket, nested-parenthesis and autolink
    targets. Content inside code fences, inline code and images is ignored.

    :param text: full Markdown document source.
    :returns: a ``list`` of :class:`Link` objects (order of appearance).
    """
    raise NotImplementedError("extract_links is not implemented in v1 scaffold")


# --- FEATURE 2 + 4: target classification -----------------------------------


def _find_anchor(text, fragment):
    """Return True if ``text`` contains a heading whose slug == ``fragment``."""
    raise NotImplementedError("_find_anchor is not implemented in v1 scaffold")


def _classify_remote(link, timeout):
    """Classify a remote (http/https) link by issuing a HEAD-then-GET check."""
    raise NotImplementedError("_classify_remote is not implemented in v1 scaffold")


def _classify_local(link, base_dir):
    """Classify a local file link by checking existence relative to base_dir."""
    raise NotImplementedError("_classify_local is not implemented in v1 scaffold")


def _classify_anchor(link, base_dir):
    """Classify an anchor / fragment link against the target document."""
    raise NotImplementedError("_classify_anchor is not implemented in v1 scaffold")


def classify(link, allow_network, timeout, base_dir=None):
    """Classify ``link`` in place and return it.

    Dispatches by scheme. When ``allow_network`` is False, remote links are
    marked ``skipped`` (FEATURE 4) while local files and anchors are still
    validated.

    :param link: the :class:`Link` to classify (mutated).
    :param allow_network: whether HTTP checks are permitted.
    :param timeout: per-request timeout in seconds.
    :param base_dir: directory used to resolve relative local targets.
    :returns: the same ``link`` object.
    """
    raise NotImplementedError("classify is not implemented in v1 scaffold")


# --- FEATURE 3: report rendering --------------------------------------------


def render_text(links, quiet=False):
    """Render a human-readable report string."""
    raise NotImplementedError("render_text is not implemented in v1 scaffold")


def render_json(paths, links):
    """Render the multi-file JSON report (schemas/report.schema.json)."""
    raise NotImplementedError("render_json is not implemented in v1 scaffold")


def render_sarif(paths, links):
    """Render a SARIF 2.1.0 log (schemas/sarif.schema.json)."""
    raise NotImplementedError("render_sarif is not implemented in v1 scaffold")


# --- FEATURE 5: discovery + config ------------------------------------------


def discover_paths(target, excludes):
    """Expand a file-or-directory target into a sorted list of Markdown paths.

    Directories are scanned recursively for ``**/*.md``; ``excludes`` is a list
    of glob patterns to skip.
    """
    raise NotImplementedError("discover_paths is not implemented in v1 scaffold")


def load_config(start_dir):
    """Load ``linkguard.cfg`` / ``.linkguard.yml`` walking up from start_dir."""
    raise NotImplementedError("load_config is not implemented in v1 scaffold")


def apply_ignores(links, cfg):
    """Drop or skip links matching the config's ignore rules."""
    raise NotImplementedError("apply_ignores is not implemented in v1 scaffold")


# --- FEATURE 6 + entry point ------------------------------------------------


def build_parser():
    """Construct the argparse parser for the documented CLI (section 3.1)."""
    p = argparse.ArgumentParser(
        prog="linkguard",
        description="Zero-dependency Markdown link & asset checker.",
    )
    p.add_argument("paths", nargs="*", default=["."],
                   help="Markdown files or directories (default: .)")
    p.add_argument("--json", action="store_true",
                   help="emit a single JSON report object")
    p.add_argument("--sarif", action="store_true",
                   help="emit a SARIF 2.1.0 log (mutually exclusive with --json)")
    p.add_argument("--no-network", action="store_true",
                   help="skip all HTTP checks; validate local files + anchors only")
    p.add_argument("--quiet", action="store_true",
                   help="print only broken findings (text mode)")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                   help="per-request timeout in seconds (default %g)" % DEFAULT_TIMEOUT)
    p.add_argument("--config", default=None,
                   help="explicit config file (else auto-discovered)")
    p.add_argument("--exclude", action="append", default=[],
                   help="additional path-exclusion glob (repeatable)")
    p.add_argument("--output", default=None,
                   help="write the report to a file instead of stdout")
    p.add_argument("--version", action="version",
                   version="linkguard " + __version__)
    return p


def run(targets, cfg, args):
    """Execute a scan over ``targets`` and return a process exit code.

    Contract (ARCHITECTURE_v1.md section 3.2): returns ``EXIT_OK`` (0),
    ``EXIT_BROKEN`` (1) or ``EXIT_USAGE`` (2). Implementation lands with the
    feature steps; the scaffold returns ``EXIT_USAGE`` after signalling that the
    body is not yet implemented.
    """
    raise NotImplementedError("run is not implemented in v1 scaffold")


def main(argv=None):
    """CLI entry point. Always returns an int exit code (never raises)."""
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse signalling --help/--version/usage error
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE

    # --- v1 scaffold behaviour ------------------------------------------------
    # The scan pipeline is not implemented yet. Rather than crashing with a
    # traceback, emit a clear not-implemented message and return EXIT_OK so the
    # scaffold smoke-test assertion ("entry point runs and prints a
    # not-implemented message without crashing") observes a clean success, not
    # a failure. This branch is removed once ``run`` is implemented (build
    # order step 8).
    sys.stderr.write(
        "linkguard %s: not implemented yet (v1 scaffold)\n"
        "This build contains interface stubs only. See ARCHITECTURE_v1.md\n"
        "section 7 for the numbered build order that implements the features.\n"
        % __version__
    )
    return EXIT_OK


def run_cli():
    """Console-script wrapper for ``[project.scripts] linkguard = linkguard:run_cli``.

    Identical to :func:`main` but takes no arguments and converts the returned
    exit code into a process exit status. Kept as a separate name so the
    documented programmatic interface (:func:`run`, :func:`main`) stays clean
    while the installed console script has a zero-argument callable target.
    """
    return main()


if __name__ == "__main__":
    sys.exit(main())
