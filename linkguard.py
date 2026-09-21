#!/usr/bin/env python3
"""linkguard - zero-dependency Markdown link/asset health checker.

Implements the v1 interfaces specified in
``workspace/product/ARCHITECTURE_v1.md`` (sections 2.2 and 3). The module is a
single file but strictly layered so each layer is unit-testable in isolation::

    constants -> Link -> [FEATURE 1] extract -> [FEATURE 2/4] classify
             -> [FEATURE 3] render -> [FEATURE 5] scan/config -> main

Runtime constraints (ARCHITECTURE_v1.md section 1.2):
  * Python 3.8+ (stdlib only; no third-party imports, ever).
  * 3.8-clean syntax (no ``dict |``, no bare ``list[str]`` annotations, no
    ``match``).
  * No mandatory network / external services.

Design rule (section 2.2): the pure functions (``extract_links``, ``classify``,
the three ``render_*``) take plain arguments and return plain data; they never
read global state and never call ``sys.exit``. Only ``main``/``run`` touch the
process.
"""

import argparse
import configparser
import fnmatch
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# --- constants --------------------------------------------------------------

__version__ = "1.0.0"
USER_AGENT = "linkguard/1.0"
DEFAULT_TIMEOUT = 10.0
EXIT_OK = 0
EXIT_BROKEN = 1
EXIT_USAGE = 2
SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:")
CONFIG_FILENAMES = ("linkguard.cfg", ".linkguard.yml")


class UsageError(Exception):
    """Raised for invalid command-line usage (FEATURE 3 output selection)."""

# Fenced code fence delimiter, e.g. ``` or ~~~ (three or more).
_FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})")
# Inline Markdown link: [text](target)  (text may contain nested brackets).
_INLINE_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
# Autolink: <https://example.com> / <mailto:a@b.com>
_AUTOLINK_RE = re.compile(r"<([A-Za-z][A-Za-z0-9+.-]*:[^<>\s]+)>")
# Image: ![alt](src) - matched on the raw text so whole images are masked.
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
# Inline code span: `code` (one or more backticks, no newlines inside).
_INLINE_CODE_RE = re.compile(r"`+[^`\n]*?`+")
# Remote schemes (http/https).
_REMOTE_SCHEME_RE = re.compile(r"^(https?):", re.IGNORECASE)
# Any scheme prefix.
_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")

# SARIF rule metadata (ARCHITECTURE_v1.md section 3.4).
SARIF_RULES = (
    {"id": "LG001", "name": "BrokenRemoteLink",
     "shortDescription": {"text": "Remote URL is unreachable"}},
    {"id": "LG002", "name": "MissingLocalFile",
     "shortDescription": {"text": "Local file target does not exist"}},
    {"id": "LG003", "name": "MissingAnchor",
     "shortDescription": {"text": "Intra-document anchor not found"}},
)


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
      source_file        -> path of the Markdown file containing the link
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
        self.source_file = None

    def to_dict(self):
        """Return the stable JSON record (FEATURE 3 schema, section 3.3).

        The keys mirror ``schemas/report.schema.json`` exactly. ``type`` is the
        JSON spelling of ``target_type``.
        """
        return {
            "url": self.url,
            "line": int(self.line),
            "column": int(self.column),
            "status": self.status,
            "http_status": self.http_status,
            "method": self.method,
            "error": self.error,
            "type": self.target_type,
        }

    def __repr__(self):
        return "Link(%r, line=%r, status=%r, type=%r)" % (
            self.url, self.line, self.status, self.target_type)


# --- FEATURE 1: extraction --------------------------------------------------


def _strip_code(text):
    """Mask fenced code blocks, inline code spans and image links.

    Returns the same-length text with masked regions replaced by spaces so
    line/column offsets remain stable. Fenced blocks and inline spans are
    neutralised first (so ``![code](x)`` written inside a fence is not treated
    as an image), then whole images are masked so their ``src`` is not checked
    as a link target.
    """
    chars = list(text)
    length = len(text)

    def _mask(start, end):
        for i in range(start, min(end, length)):
            if chars[i] != "\n":  # keep newlines so line numbers survive
                chars[i] = " "

    # 1. Fenced code blocks (``` or ~~~), including their content.
    in_fence = False
    fence_char = ""
    pos = 0
    while True:
        line_end = text.find("\n", pos)
        if line_end == -1:
            line_end = length
        line = text[pos:line_end]
        match = _FENCE_RE.match(line)
        if not in_fence:
            if match:
                in_fence = True
                fence_char = match.group(2)[0]
                _mask(pos, line_end)  # mask the opening fence line
        else:
            stripped = line.strip()
            if (match and match.group(2)[0] == fence_char
                    and len(stripped) >= 3
                    and set(stripped) <= {fence_char}):
                _mask(pos, line_end)  # closing fence
                in_fence = False
            else:
                _mask(pos, line_end)  # fenced content
        if line_end >= length:
            break
        pos = line_end + 1

    # 2. Inline code spans (only outside already-masked fenced regions).
    remaining = "".join(chars)
    for m in _INLINE_CODE_RE.finditer(remaining):
        _mask(m.start(), m.end())

    # 3. Images ``![alt](src)`` - mask the whole construct.
    remaining = "".join(chars)
    for m in _IMAGE_RE.finditer(remaining):
        _mask(m.start(), m.end())

    return "".join(chars)


def _split_target(raw):
    """Split a raw ``(...)`` target into ``(url, title)``.

    Handles the angle-bracket form ``<url>`` (optionally followed by a title)
    and the common ``url "title"`` / ``url 'title'`` forms. Nested parentheses
    in the URL are preserved.
    """
    target = raw.strip()
    if not target:
        return "", None

    # Angle-bracket form: <url> ["title"]
    if target.startswith("<"):
        close = target.find(">")
        if close != -1:
            url = target[1:close]
            title = target[close + 1:].strip() or None
            return url, title

    # Title forms: url "title" / url 'title'. Only treat a trailing quoted
    # segment as a title (avoid eating nested parentheses that are part of URL).
    m = re.match(r'^(.*?)\s+("[^"]*"|\'[^\']*\')\s*$', target)
    if m:
        return m.group(1).strip(), m.group(2)
    return target, None


def _line_col(text, index):
    """Return the 1-based ``(line, column)`` of ``index`` in ``text``."""
    line = text.count("\n", 0, index) + 1
    last_nl = text.rfind("\n", 0, index)
    column = index - last_nl  # 1-based: index==0 -> column 1
    return line, column


def extract_links(text):
    """Extract Markdown links from ``text``.

    Handles inline, titled, angle-bracket, nested-parenthesis and autolink
    targets. Content inside code fences, inline code and images is ignored.

    :param text: full Markdown document source.
    :returns: a ``list`` of :class:`Link` objects (order of appearance).
    """
    masked = _strip_code(text)
    found = []  # list of (index, url)

    for m in _INLINE_LINK_RE.finditer(masked):
        url, _title = _split_target(m.group(2))
        if url:
            found.append((m.start(), url))

    for m in _AUTOLINK_RE.finditer(masked):
        found.append((m.start(), m.group(1)))

    found.sort(key=lambda item: item[0])

    links = []
    for index, url in found:
        line, column = _line_col(masked, index)
        links.append(Link(url, line, column))
    return links


# --- FEATURE 2 + 4: target classification ----------------------------------


# Inline Markdown link / image syntax: ``[text](url)`` or ``![alt](url)``.
# GitHub renders only the link *text* into the heading, so the URL must be
# dropped before slugging (``# See [docs](http://x)`` -> slug ``see-docs``).
# NOTE: distinct from ``_INLINE_LINK_RE`` (used by ``extract_links``) so that
# reducing a heading to its visible text does not clobber the extraction regex.
_HEADING_MARKUP_RE = re.compile(r"!?\[([^\]\[]*)\]\([^)]*\)")


def _slugify_heading(heading_text):
    """Convert a Markdown heading to the GitHub-style anchor slug.

    Lowercases, strips Markdown emphasis/backtick markers, removes punctuation
    except word characters/hyphens/underscores, and replaces runs of whitespace
    with single hyphens.
    """
    text = heading_text.strip()
    # Collapse inline links/images down to their visible text first so the URL
    # does not leak into the slug (GitHub drops the target entirely).
    text = _HEADING_MARKUP_RE.sub(r"\1", text)
    text = text.lower()
    text = re.sub(r"[*_`~]", "", text)          # drop emphasis/backtick markers
    text = re.sub(r"[^\w\s-]", "", text)        # drop other punctuation
    text = re.sub(r"\s+", "-", text.strip())    # whitespace -> hyphen
    return text


_ATX_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_SETEXT_UNDERLINE_RE = re.compile(r"^\s{0,3}(=+|-+)\s*$")

# Characters that can never appear in a GitHub anchor slug but may survive
# percent-decoding in a malformed fragment (path/query separators). Used by
# ``_find_anchor`` to reject fragments such as ``#foo-bar/`` or ``#a?b``.
_FRAGMENT_DELIM_RE = re.compile(r"[/\\?&=:#]")


def _headings(text):
    """Return the ordered list of anchor slugs for headings in ``text``.

    Both ATX (``## Heading``) and Setext (underlined with ``===``/``---``)
    headings are recognised, matching the anchor targets GitHub generates.

    GitHub disambiguates repeated slugs by appending ``-1``, ``-2``, ... in
    order of appearance. Those suffixed slugs are materialised here (and the
    base slug kept) so that ``#setup``, ``#setup-1`` and ``#setup-2`` all
    resolve when a document repeats the same heading text.
    """
    slugs = []
    # ``occurrences`` maps every *emitted* slug (base and suffixed) to the
    # current suffix counter for its base, mirroring github-slugger. Tracking
    # emitted slugs (not just bases) is what makes cross-heading collisions
    # resolve correctly: ``## Setup``, ``## Setup``, ``## Setup 1`` yields
    # ``setup``, ``setup-1``, ``setup-1-1`` -- never a duplicate slug.
    occurrences = {}
    in_fence = False
    fence_char = ""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        fence = _FENCE_RE.match(line)
        if fence:
            if not in_fence:
                in_fence = True
                fence_char = fence.group(2)[0]
            elif fence.group(2)[0] == fence_char:
                in_fence = False
            continue
        if in_fence:
            continue

        heading_text = None
        m = _ATX_HEADING_RE.match(line)
        if m:
            heading_text = m.group(2)
        else:
            # Setext heading: the *previous* non-blank line is the heading
            # text when this line is a run of ``=`` (h1) or ``-`` (h2).
            underline = _SETEXT_UNDERLINE_RE.match(line)
            if underline and index > 0:
                previous = lines[index - 1]
                if previous.strip() and not _ATX_HEADING_RE.match(previous):
                    heading_text = previous.strip()

        if heading_text is not None:
            base = _slugify_heading(heading_text)
            if not base:
                continue
            # Materialise GitHub's duplicate-slug suffixes. Port of
            # github-slugger: while the candidate has already been emitted,
            # bump the base's counter and try ``base-N`` again.
            original = base
            while base in occurrences:
                occurrences[original] += 1
                base = "%s-%d" % (original, occurrences[original])
            occurrences[base] = 0
            slugs.append(base)
    return slugs


def _find_anchor(text, fragment):
    """Return True if ``text`` contains a heading whose slug == ``fragment``.

    The GitHub ``#top`` convention (link to the top of any document) is also
    honoured. The fragment is normalised before comparison: a leading ``#`` is
    stripped, any percent-encoding is decoded (so ``#caf%C3%A9`` matches the
    ``Cafe`` heading slug), and the result is lowercased.
    """
    if not fragment:
        return True
    frag = fragment.lstrip("#")
    # URL-decode percent-encoded fragments (e.g. non-ASCII or space escapes)
    # before slug comparison; unquote is a no-op when nothing is encoded.
    frag = urllib.parse.unquote(frag)
    frag = frag.lower()
    if frag in ("top", ""):
        return True
    headings = _headings(text)
    # Exact slug match (the common case: ``#advanced-usage``).
    if frag in headings:
        return True
    # A GitHub anchor slug can only ever contain word characters, hyphens and
    # underscores. If the fragment still carries URL path/query delimiters
    # (``/``, ``\``, ``?``, ``&``, ``=``, ``:``, ``#``) after decoding it is a
    # malformed fragment -- e.g. ``#foo-bar/`` -- and must NOT be allowed to
    # match by accident via punctuation-stripping below.
    if _FRAGMENT_DELIM_RE.search(frag):
        return False
    # GitHub-style anchors are matched slug-to-slug: percent-decoded fragments
    # that still contain spaces/punctuation (e.g. ``#Advanced%20Usage`` ->
    # ``advanced usage``) must be normalised the same way as heading text
    # (-> ``advanced-usage``) before comparison.
    return _slugify_heading(frag) in headings


def _classify_remote(link, timeout):
    """Classify a remote (http/https) link by issuing a HEAD-then-GET check.

    A ``HEAD`` request is tried first; if the server rejects it (403/405/501 or
    a network error that looks method-related) a ranged ``GET`` is attempted.
    Mutates ``link`` and returns it.
    """
    link.target_type = "remote"
    link.method = "HEAD"
    request = urllib.request.Request(
        link.url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            link.http_status = int(getattr(response, "status", 200))
        link.status = "ok"
        link.error = None
        return link
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        if status in (403, 405, 501):
            return _classify_remote_get(link, timeout)
        link.http_status = status
        link.status = "broken"
        link.error = "HTTP %d" % status
        return link
    except (urllib.error.URLError, ValueError, OSError) as exc:
        # Could be a HEAD-specific failure; try a GET before declaring broken.
        return _classify_remote_get(link, timeout, cause=str(exc))


def _classify_remote_get(link, timeout, cause=None):
    """Ranged ``GET`` fallback for servers that reject ``HEAD`` requests."""
    link.method = "GET"
    request = urllib.request.Request(
        link.url, method="GET",
        headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            link.http_status = int(getattr(response, "status", 200))
        link.status = "ok"
        link.error = None
        return link
    except urllib.error.HTTPError as exc:
        link.http_status = int(exc.code)
        link.status = "broken"
        link.error = "HTTP %d" % int(exc.code)
        return link
    except (urllib.error.URLError, ValueError, OSError) as exc:
        link.http_status = None
        link.status = "broken"
        link.error = str(cause or exc)
        return link


def _classify_local(link, base_dir):
    """Classify a local file link by checking existence relative to base_dir.

    Mutates ``link`` and returns it. A URL-encoded path is decoded; a trailing
    ``#fragment`` (if present) is validated against the target file.
    """
    link.target_type = "local"
    link.method = "LOCAL"
    raw = link.url
    path_part, _, fragment = raw.partition("#")
    path_part = urllib.parse.unquote(path_part) if path_part else ""

    if not path_part:
        # Pure fragment routed here defensively -> treat as anchor.
        return _classify_anchor(link, base_dir)

    base_dir = base_dir or os.getcwd()
    candidate = os.path.normpath(os.path.join(base_dir, path_part))
    if not os.path.exists(candidate):
        link.status = "broken"
        link.error = "local file not found: %s" % raw
        return link

    if fragment:
        try:
            with open(candidate, "r", encoding="utf-8", errors="replace") as fh:
                target_text = fh.read()
        except OSError as exc:
            link.status = "broken"
            link.error = "cannot read %s: %s" % (candidate, exc)
            return link
        if not _find_anchor(target_text, fragment):
            link.status = "broken"
            link.error = "anchor not found: %s" % raw
            return link

    link.status = "ok"
    return link


def _classify_anchor(link, base_dir):
    """Classify an anchor / fragment link against the target document.

    Handles the pure ``#frag`` form (against the source file) and the
    ``./doc.md#frag`` form (delegated to :func:`_classify_local`).
    """
    raw = link.url
    path_part, _, fragment = raw.partition("#")

    if path_part:
        # Composite local+anchor target.
        return _classify_local(link, base_dir)

    link.target_type = "anchor"
    link.method = "LOCAL"
    source = link.source_file
    # A source path was supplied but no such file exists: the same-page
    # anchor cannot be verified, so report it as broken rather than
    # silently assuming success (which is only valid when the caller
    # provided no source file at all).
    if source and not os.path.isfile(source):
        link.status = "broken"
        link.error = "source file not found for same-page anchor: %s" % source
        return link
    if source and os.path.isfile(source):
        try:
            with open(source, "r", encoding="utf-8", errors="replace") as fh:
                source_text = fh.read()
        except OSError as exc:
            link.status = "broken"
            link.error = "cannot read source %s: %s" % (source, exc)
            return link
        if _find_anchor(source_text, fragment):
            link.status = "ok"
            return link
        link.status = "broken"
        link.error = "anchor not found: %s" % raw
        return link

    # No source text available (programmatic use): assume the anchor resolves.
    link.status = "ok"
    return link


def classify(link, allow_network, timeout, base_dir=None,
             extra_skip_schemes=None):
    """Classify ``link`` in place and return it.

    Dispatches by scheme. When ``allow_network`` is False, remote links are
    marked ``skipped`` (FEATURE 4) while local files and anchors are still
    validated.

    :param link: the :class:`Link` to classify (mutated).
    :param allow_network: whether HTTP checks are permitted.
    :param timeout: per-request timeout in seconds.
    :param base_dir: directory used to resolve relative local targets.
    :param extra_skip_schemes: extra schemes (from config) to treat as
        ``skipped`` instead of ``broken``.
    :returns: the same ``link`` object.
    """
    url = link.url or ""
    # An empty or whitespace-only target is not a navigable link (defensive:
    # extraction should never emit one). Treat it as skipped rather than
    # falsely reporting a missing local file.
    if not url.strip():
        link.target_type = "skipped"
        link.status = "skipped"
        link.error = "empty target"
        return link
    lowered = url.lower()

    # Non-navigable / non-checkable schemes are always skipped.
    if lowered.startswith(SKIP_SCHEMES):
        link.target_type = "skipped"
        link.status = "skipped"
        link.error = "skipped scheme"
        return link

    # Config-provided extra schemes are skipped (FEATURE 5 config behaviour).
    for scheme in (extra_skip_schemes or ()):
        prefix = scheme if scheme.endswith(":") else scheme + ":"
        if lowered.startswith(prefix.lower()):
            link.target_type = "skipped"
            link.status = "skipped"
            link.error = "skipped scheme (config): %s" % scheme
            return link

    if _REMOTE_SCHEME_RE.match(url):
        if not allow_network:
            link.target_type = "skipped"
            link.status = "skipped"
            link.error = "remote check disabled (--no-network)"
            return link
        return _classify_remote(link, timeout)

    if url.startswith("#"):
        return _classify_anchor(link, base_dir)

    # Anything else with a scheme (ftp:, ssh:, file:) is skipped.
    if _SCHEME_RE.match(url):
        link.target_type = "skipped"
        link.status = "skipped"
        link.error = "unsupported scheme"
        return link

    # Relative / absolute local path (may carry a #fragment).
    return _classify_local(link, base_dir)


# --- FEATURE 5: config file loading -----------------------------------------


class ConfigError(Exception):
    """Raised when a config file is malformed or unreadable.

    ``main`` maps this to exit code :data:`EXIT_USAGE` (2) with a clear stderr
    message (ARCHITECTURE_v1.md section 3.6: "Invalid config => exit 2").
    """


#: Config keys recognised in both ``linkguard.cfg`` and ``.linkguard.yml``.
_CONFIG_KEYS = ("exclude", "ignore", "extra_skip_schemes", "timeout",
                "no_network")


class Config(object):
    """Parsed linkguard configuration with sane built-in defaults.

    Attributes (ARCHITECTURE_v1.md section 3.6 / docs/CONFIG.md):

      exclude            -> list of glob patterns for paths to skip
      ignore             -> list of substring/regex patterns; matching *broken*
                            links are not reported as broken
      extra_skip_schemes -> list of extra URL schemes treated as "skipped"
      timeout            -> default per-request timeout in seconds (float)
      no_network         -> bool; when True remote checks are skipped
      path               -> source file path, or None for built-in defaults
      source             -> "default" | "linkguard.cfg" | ".linkguard.yml"
    """

    def __init__(self, exclude=None, ignore=None, extra_skip_schemes=None,
                 timeout=DEFAULT_TIMEOUT, no_network=False, path=None,
                 source="default"):
        self.exclude = list(exclude or [])
        self.ignore = list(ignore or [])
        self.extra_skip_schemes = list(extra_skip_schemes or [])
        self.timeout = float(timeout)
        self.no_network = bool(no_network)
        self.path = path
        self.source = source

    def to_dict(self):
        """Return a JSON-friendly view (handy for debugging and tests)."""
        return {
            "exclude": list(self.exclude),
            "ignore": list(self.ignore),
            "extra_skip_schemes": list(self.extra_skip_schemes),
            "timeout": self.timeout,
            "no_network": self.no_network,
            "path": self.path,
            "source": self.source,
        }

    def __repr__(self):
        return ("Config(exclude=%r, ignore=%r, extra_skip_schemes=%r, "
                "timeout=%r, no_network=%r, source=%r)"
                % (self.exclude, self.ignore, self.extra_skip_schemes,
                   self.timeout, self.no_network, self.source))


def _split_list(raw):
    """Split a config list value on commas and/or newlines.

    Values may be given inline (``a, b, c``) or as one-per-line continuation
    lines; blank entries are dropped and surrounding whitespace is trimmed.
    """
    if raw is None:
        return []
    parts = []
    for chunk in re.split(r"[,\n]", raw):
        item = chunk.strip()
        if item:
            parts.append(item)
    return parts


def _parse_bool(raw, key, path):
    """Parse a boolean config value; raise :class:`ConfigError` on junk."""
    value = str(raw).strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ConfigError("%s: invalid boolean for '%s': %r" % (path, key, raw))


def _parse_timeout(raw, path):
    """Parse the ``timeout`` value; must be a positive number."""
    if raw is None or str(raw).strip() == "":
        raise ConfigError("%s: 'timeout' must be a number" % path)
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        raise ConfigError("%s: invalid 'timeout' value: %r (expected a number)"
                          % (path, raw))
    if value <= 0:
        raise ConfigError("%s: 'timeout' must be positive, got %r"
                          % (path, raw))
    return value


def _validate_ignore_patterns(patterns, path):
    """Reject malformed ``ignore`` regexes at load time.

    ``ignore`` entries are documented as substrings *or* regexes
    (docs/CONFIG.md). A plain substring or glob is always valid, but an entry
    that looks like a regex yet does not compile is malformed config: rather
    than silently dropping it at match time (which would hide the link it was
    meant to suppress), fail fast with a clear error naming the file and the
    offending pattern.
    """
    for pattern in patterns:
        if any(ch in pattern for ch in "*?["):
            # Glob-style pattern: ``_matches_ignore`` uses fnmatch for these,
            # which never raises, so no regex validation is required.
            continue
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ConfigError(
                "%s: invalid regex in 'ignore': %r (%s)"
                % (path, pattern, exc))


def _config_from_mapping(mapping, path, source):
    """Build a :class:`Config` from a ``{key: raw_value}`` mapping.

    Unknown keys are rejected so typos surface as clear errors instead of being
    silently ignored. Values are validated per key.
    """
    unknown = sorted(set(mapping) - set(_CONFIG_KEYS))
    if unknown:
        raise ConfigError(
            "%s: unknown config key(s): %s (valid keys: %s)"
            % (path, ", ".join(unknown), ", ".join(_CONFIG_KEYS)))

    cfg = Config(path=path, source=source)
    if "exclude" in mapping:
        cfg.exclude = _split_list(mapping["exclude"])
    if "ignore" in mapping:
        cfg.ignore = _split_list(mapping["ignore"])
        _validate_ignore_patterns(cfg.ignore, path)
    if "extra_skip_schemes" in mapping:
        cfg.extra_skip_schemes = _split_list(mapping["extra_skip_schemes"])
    if "timeout" in mapping:
        cfg.timeout = _parse_timeout(mapping["timeout"], path)
    if "no_network" in mapping:
        cfg.no_network = _parse_bool(mapping["no_network"], "no_network", path)
    return cfg


def _parse_cfg_file(path):
    """Parse an INI ``linkguard.cfg`` file into a :class:`Config`.

    The single ``[linkguard]`` section is required; a missing section or any
    ``configparser`` error is reported as a :class:`ConfigError`.
    """
    parser = configparser.ConfigParser()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            parser.read_file(fh)
    except configparser.Error as exc:
        raise ConfigError("%s: malformed INI config: %s" % (path, exc))
    except OSError as exc:
        raise ConfigError("%s: cannot read config: %s" % (path, exc))

    if not parser.has_section("linkguard"):
        raise ConfigError(
            "%s: missing required [linkguard] section" % path)

    mapping = {}
    for key, value in parser.items("linkguard"):
        mapping[key] = value
    return _config_from_mapping(mapping, path, "linkguard.cfg")


def _parse_yaml_file(path):
    """Parse the documented flat ``.linkguard.yml`` subset into a Config.

    Supported subset (ARCHITECTURE_v1.md section 3.6): top-level ``key: value``
    scalars and block ``- item`` lists. A single top-level ``linkguard:``
    mapping key is also accepted, with the real keys indented under it, so the
    YAML mirrors the INI ``[linkguard]`` section::

        linkguard:
          exclude:
            - node_modules/*
            - vendor/*
          timeout: 3

    Nesting deeper than the one ``linkguard:`` wrapper, tabs for indentation,
    or unparsable lines are reported as a :class:`ConfigError` rather than
    guessed at.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        raise ConfigError("%s: cannot read config: %s" % (path, exc))

    # Flatten to key -> list of raw (possibly multi-line) values.
    collected = {}       # key -> list of value strings
    current_key = None   # active list key, or None
    #: Indentation of the keys inside an opened ``linkguard:`` block, or None
    #: when we are at the document top level (flat mapping form).
    block_indent = None
    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        leading = line[:len(line) - len(line.lstrip())]
        if "\t" in leading:
            raise ConfigError(
                "%s:%d: tabs are not allowed for indentation"
                % (path, lineno))
        indent = len(leading)

        if stripped.startswith("- "):
            # List item: must belong to a key we have already seen.
            if current_key is None:
                raise ConfigError(
                    "%s:%d: list item without a parent key"
                    % (path, lineno))
            if block_indent is not None and indent <= block_indent:
                raise ConfigError(
                    "%s:%d: list item is not indented under %r"
                    % (path, lineno, current_key))
            collected[current_key].append(stripped[2:].strip())
            continue

        if ":" not in stripped:
            raise ConfigError(
                "%s:%d: expected 'key: value', got %r"
                % (path, lineno, raw_line))

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        if block_indent is None:
            # Document top level.
            if key == "linkguard" and value == "":
                # Open the INI-like wrapper block; real keys are indented.
                block_indent = indent
                current_key = None
                continue
            current_key = key
            collected.setdefault(key, [])
            if value:
                collected[key].append(value)
            continue

        # Inside a ``linkguard:`` block: only one level of nesting is allowed.
        if indent <= block_indent:
            if indent == block_indent and key == "linkguard" and value == "":
                raise ConfigError(
                    "%s:%d: duplicate 'linkguard:' block" % (path, lineno))
            raise ConfigError(
                "%s:%d: 'linkguard:' block must contain only indented keys"
                % (path, lineno))

        current_key = key
        collected.setdefault(key, [])
        if value:
            collected[key].append(value)

    mapping = {key: "\n".join(values) for key, values in collected.items()}
    return _config_from_mapping(mapping, path, ".linkguard.yml")


def find_config_file(start_dir):
    """Walk up from ``start_dir`` returning the nearest config file, or None.

    ``linkguard.cfg`` takes precedence over ``.linkguard.yml`` within the same
    directory; the nearest directory wins overall (ARCHITECTURE_v1.md 3.6).
    """
    directory = os.path.abspath(start_dir or os.getcwd())
    if os.path.isfile(directory):
        directory = os.path.dirname(directory) or os.getcwd()
    while True:
        for name in CONFIG_FILENAMES:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def load_config(start_dir=None, explicit_path=None):
    """Load linkguard configuration.

    Resolution order (ARCHITECTURE_v1.md section 3.6): an explicit
    ``explicit_path`` (the ``--config`` flag) always wins; otherwise the
    nearest ``linkguard.cfg``/``.linkguard.yml`` walking up from ``start_dir`` is
    used; with neither, built-in defaults are returned.

    :param start_dir: directory (or file) to auto-discover from. Defaults to
        the current working directory.
    :param explicit_path: an explicit config path that must exist.
    :returns: a :class:`Config`.
    :raises ConfigError: if an explicit path is missing, or the discovered /
        explicit config is malformed, unreadable or contains unknown keys.
    """
    if explicit_path:
        if not os.path.isfile(explicit_path):
            raise ConfigError("config file not found: %s" % explicit_path)
        path = explicit_path
    else:
        path = find_config_file(start_dir)

    if path is None:
        return Config()

    base = os.path.basename(path).lower()
    if base.endswith((".yml", ".yaml")):
        return _parse_yaml_file(path)
    if base.endswith(".cfg") or base == "linkguard.cfg":
        return _parse_cfg_file(path)
    # Fall back to INI for unknown extensions (explicit --config files).
    return _parse_cfg_file(path)


def _matches_ignore(url, patterns):
    """Return True if ``url`` matches any ignore pattern.

    Patterns are matched as a substring if they contain no glob/regex
    metacharacter, else as a glob (``fnmatch``) and finally as a regular
    expression. An invalid regex is ignored rather than aborting the scan.
    """
    for pattern in patterns:
        if not pattern:
            continue
        if pattern in url:
            return True
        if any(ch in pattern for ch in "*?["):
            if fnmatch.fnmatch(url, pattern):
                return True
        try:
            if re.search(pattern, url):
                return True
        except re.error:
            continue
    return False


def apply_ignores(links, cfg):
    """Apply the config ``ignore`` rules to classified links.

    Any ``broken`` link whose URL matches an ``ignore`` pattern is downgraded
    to ``skipped`` so it no longer fails CI. Non-broken links are untouched.
    This is the observable behaviour change a config file produces
    (ARCHITECTURE_v1.md section 3.6 / docs/CONFIG.md).

    :param links: classified :class:`Link` objects (mutated in place).
    :param cfg: the loaded :class:`Config`.
    :returns: the same list of links.
    """
    if not cfg or not cfg.ignore:
        return links
    for link in links:
        if link.status == "broken" and _matches_ignore(link.url or "",
                                                       cfg.ignore):
            link.status = "skipped"
            link.error = "ignored by config"
    return links


# --- FEATURE 3: report rendering --------------------------------------------


def _summarize(links):
    """Return the summary counts dict for a list of links."""
    summary = {"total": len(links), "ok": 0, "broken": 0, "skipped": 0}
    for link in links:
        if link.status == "ok":
            summary["ok"] += 1
        elif link.status == "broken":
            summary["broken"] += 1
        elif link.status == "skipped":
            summary["skipped"] += 1
    return summary


def render_text(links, quiet=False):
    """Render a human-readable report string.

    :param links: the classified :class:`Link` objects.
    :param quiet: when True, only ``broken`` findings are printed.
    :returns: a newline-terminated report string.
    """
    lines = []
    for link in links:
        if quiet and link.status != "broken":
            continue
        where = "%s:%d:%d" % (link.source_file or "-", link.line, link.column)
        status = link.status or "unknown"
        detail = ""
        if link.status == "broken":
            detail = " (%s)" % (link.error or "broken")
        elif link.status == "ok" and link.method in ("HEAD", "GET"):
            detail = " (HTTP %s)" % link.http_status
        elif link.status == "skipped":
            detail = " (%s)" % (link.error or "skipped")
        lines.append("[%s] %s %s%s" % (status, where, link.url, detail))

    summary = _summarize(links)
    lines.append("%d links: %d ok, %d broken, %d skipped"
                 % (summary["total"], summary["ok"], summary["broken"],
                    summary["skipped"]))
    return "\n".join(lines) + "\n"


def render_json(paths, links, exit_code=EXIT_OK):
    """Render the multi-file JSON report (schemas/report.schema.json).

    :param paths: ordered list of scanned file paths.
    :param links: the classified :class:`Link` objects (each with
        ``source_file`` set).
    :param exit_code: the exit code to embed.
    :returns: a pretty-printed JSON string.
    """
    by_file = {}
    order = []
    for path in paths:
        normalized = os.path.normpath(path)
        if normalized not in by_file:
            by_file[normalized] = []
            order.append(normalized)
    for link in links:
        key = os.path.normpath(link.source_file or "-")
        if key not in by_file:
            by_file[key] = []
            order.append(key)
        by_file[key].append(link)

    files = [{"file": path, "links": [l.to_dict() for l in by_file[path]]}
             for path in order]

    report = {
        "version": "1",
        "exit_code": int(exit_code),
        "summary": _summarize(links),
        "files": files,
    }
    # Backward-compatible single-file alias (section 3.3 compatibility note).
    if len(files) == 1:
        report["file"] = files[0]["file"]
    return json.dumps(report, indent=2) + "\n"


def _sarif_rule_id(link):
    """Map a broken link to its SARIF rule id (LG001/LG002/LG003)."""
    if link.target_type == "remote":
        return "LG001"
    if link.target_type == "anchor":
        return "LG003"
    if link.target_type == "local":
        # A local link carrying a fragment that failed was an anchor failure.
        if "#" in (link.url or "") and "anchor not found" in (link.error or ""):
            return "LG003"
        return "LG002"
    return "LG002"


def render_sarif(paths, links):
    """Render a SARIF 2.1.0 log (schemas/sarif.schema.json).

    One ``result`` is emitted per ``broken`` finding.

    :param paths: ordered list of scanned file paths (for the URI base).
    :param links: the classified :class:`Link` objects.
    :returns: a pretty-printed SARIF JSON string.
    """
    results = []
    for link in links:
        if link.status != "broken":
            continue
        results.append({
            "ruleId": _sarif_rule_id(link),
            "level": "error",
            "message": {"text": link.error or "broken link"},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": (link.source_file or "-").replace(os.sep, "/"),
                    },
                    "region": {
                        "startLine": int(link.line),
                        "startColumn": int(link.column),
                    },
                },
            }],
        })

    log = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "linkguard",
                    "informationUri": "https://github.com/OWNER/linkguard",
                    "version": __version__,
                    "rules": [dict(rule) for rule in SARIF_RULES],
                },
            },
            "results": results,
        }],
    }
    return json.dumps(log, indent=2) + "\n"


# --- FEATURE 3: output-format selection (entry point) -----------------------


def _parse_output_args(argv):
    """Parse just enough CLI to choose an output format.

    This deliberately covers only the output-selection concern owned by
    FEATURE 3 (``--json`` / ``--sarif`` and their mutual exclusion). The
    full command-line surface, exit-code summary and config handling belong to
    FEATURE 6 and are intentionally left to that feature.

    :param argv: argument list *excluding* the program name.
    :returns: ``(paths, fmt)`` where ``fmt`` is ``"text"|"json"|"sarif"``.
    :raises UsageError: when a path is missing or ``--json`` and ``--sarif``
        are requested together (mutually exclusive).
    """
    paths = []
    fmt = "text"
    want_json = False
    want_sarif = False
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--json":
            want_json = True
        elif arg == "--sarif":
            want_sarif = True
        elif arg.startswith("-") and arg != "-":
            raise UsageError("unknown option: %s" % arg)
        else:
            paths.append(arg)
        index += 1
    if want_json and want_sarif:
        raise UsageError("--json and --sarif are mutually exclusive")
    if want_json:
        fmt = "json"
    elif want_sarif:
        fmt = "sarif"
    return paths, fmt


def main(argv=None):
    """Entry point for ``python linkguard.py`` (output selection only).

    :param argv: arguments excluding the program name (defaults to sys.argv).
    :returns: process exit code.
    """
    if argv is None:
        argv = sys.argv[1:]
    try:
        paths, fmt = _parse_output_args(list(argv))
    except UsageError as exc:
        sys.stderr.write("linkguard: error: %s\n" % exc)
        return EXIT_USAGE
    if not paths:
        sys.stderr.write("linkguard: error: no input files\n")
        return EXIT_USAGE

    all_links = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            sys.stderr.write("linkguard: error: cannot read %s: %s\n"
                             % (path, exc))
            return EXIT_USAGE
        links = extract_links(text)
        for link in links:
            link.source_file = os.path.normpath(path)
            classify(link, allow_network=False, timeout=DEFAULT_TIMEOUT,
                     base_dir=os.path.dirname(os.path.abspath(path)))
            all_links.append(link)

    broken = any(link.status == "broken" for link in all_links)
    exit_code = EXIT_BROKEN if broken else EXIT_OK
    if fmt == "json":
        sys.stdout.write(render_json(paths, all_links, exit_code=exit_code))
    elif fmt == "sarif":
        sys.stdout.write(render_sarif(paths, all_links))
    return exit_code


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    sys.exit(main())
