# linkguard

[![linkguard](https://github.com/FopBop/linkguard/actions/workflows/linkguard.yml/badge.svg)](https://github.com/FopBop/linkguard/actions/workflows/linkguard.yml)
[![CI](https://github.com/FopBop/linkguard/actions/workflows/ci.yml/badge.svg)](https://github.com/FopBop/linkguard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Zero-dependency Markdown link & asset health checker + repo-safe CI gate.**

A single-file CLI (plus an optional GitHub Action wrapper) that scans your
`.md` files for **broken links, missing image/static assets, and dead
in-document anchors** — all with the Python standard library. No `pip install`,
no Node, no `npm install`, no paid services, no network required.

```console
$ python3 linkguard.py . --no-network
[ok] README.md:12:5 CONTRIBUTING.md
[broken] docs/guide.md:6:31 ./does-not-exist.md (local file not found: ./does-not-exist.md)
[broken] docs/guide.md:7:31 #no-such-heading (anchor not found: #no-such-heading)
3 links: 1 ok, 2 broken, 0 skipped
```

`linkguard` exits non-zero on the first broken link, so it drops straight into
CI as a gate.

---

## Table of contents

- [What linkguard does](#what-linkguard-does)
- [Requirements](#requirements)
- [Install and setup](#install-and-setup)
- [Usage](#usage)
- [CLI reference](#cli-reference)
- [Configuration](#configuration)
- [Example output](#example-output)
- [Example CI usage](#example-ci-usage)
- [How it works](#how-it-works)
- [Running the tests](#running-the-tests)
- [Exit codes](#exit-codes)
- [License](#license)

---

## What linkguard does

Given one or more Markdown files or directories, `linkguard` extracts every
link and image reference and classifies each one as **`ok`**, **`broken`**, or
**`skipped`**:

| Check | What it validates |
|---|---|
| **Remote URLs** | `http(s)://…` targets are requested (HEAD, falling back to GET) and treated as broken on 404/5xx/timeout. *(Optional — disable with `--no-network`.)* |
| **Local files** | Relative/absolute paths (`./doc.md`, `images/logo.png`) are resolved against the source file's directory and must exist on disk. |
| **Anchors** | `#fragment` and `./doc.md#fragment` targets are compared against GitHub-style heading slugs parsed from the target document. |
| **Image / static assets** | `![alt](src)` references (inline and reference-style) are checked the same way as local files. |
| **Skipped** | Non-navigable schemes (`mailto:`, `tel:`, `javascript:`, `data:`), unsupported schemes, and — under `--no-network` — remote URLs. Skips never fail the run. |

It reports in **plain text**, **JSON** (`--json`), or **SARIF 2.1.0**
(`--sarif`) for GitHub code-scanning annotations.

## Requirements

- **Python 3.8 or newer.** Nothing else. The CLI imports only the standard
  library (`argparse`, `json`, `re`, `os`, `urllib`, `configparser`,
  `fnmatch`). This is enforced by a test in the suite.

## Install and setup

There is **nothing to install** for the zero-friction path — clone and run the
single file:

```console
$ git clone https://github.com/OWNER/linkguard.git
$ cd linkguard
$ python3 linkguard.py . --no-network
```

Optionally, install it as a command on your `PATH` (still zero dependencies):

```console
$ pip install .          # or: pip install -e .   for a live editable checkout
$ linkguard . --no-network
```

Using it in CI as a GitHub Action requires no install step at all — see
[Example CI usage](#example-ci-usage).

## Usage

```console
$ python3 linkguard.py [PATH ...] [options]
```

- `PATH` is one or more `.md` files **or** directories.
- Directories are scanned recursively for `**/*.md`.
- When `PATH` is omitted it defaults to `.` (the current directory).
- `-h`/`--help` prints the full usage text and exits `0`.
- `--version` prints `linkguard <ver>` and exits `0`.

Typical invocations:

```console
# Offline scan of the whole repo (recommended default for docs repos):
$ python3 linkguard.py . --no-network

# A single file, only broken findings printed:
$ python3 linkguard.py README.md --no-network --quiet

# JSON report piped to jq:
$ python3 linkguard.py docs --no-network --json | jq '.summary'

# SARIF report written to a file for CI upload:
$ python3 linkguard.py . --no-network --sarif --output linkguard.sarif

# Override a config value on the command line:
$ python3 linkguard.py . --exclude 'archive/*' --timeout 5
```

## CLI reference

| Flag | Description |
|---|---|
| `PATH ...` | Markdown files or directories to scan. Directory targets are scanned recursively for `**/*.md`. Defaults to `.`. |
| `--json` | Emit a single JSON report object (schema: [`schemas/report.schema.json`](schemas/report.schema.json)). Mutually exclusive with `--sarif`. |
| `--sarif` | Emit a SARIF 2.1.0 log for CI annotations (schema: [`schemas/sarif.schema.json`](schemas/sarif.schema.json)). Mutually exclusive with `--json`. |
| `--no-network` | Skip all HTTP checks; validate only local files, assets and anchors. Remote URLs are reported `skipped`. |
| `--quiet` | Print only `broken` findings (text mode). The trailing summary line is still printed. |
| `--timeout SEC` | Per-request timeout in seconds for remote checks. Default `10`. Must be a positive number. |
| `--config PATH` | Explicit config file. Overrides auto-discovery. Must exist and be valid, or exit `2`. |
| `--exclude GLOB` | Extra path-exclusion glob. Repeatable. Merged with the config `exclude` list. |
| `--output PATH` | Write the report to a file instead of stdout (useful for `--sarif` artifacts). |
| `--version` | Print `linkguard <ver>` and exit `0`. |
| `-h`, `--help` | Show the usage message and exit `0`. |

Every value-taking option also accepts the `--flag=value` form (e.g.
`--timeout=5`, `--config=ci.cfg`).

## Configuration

`linkguard` auto-discovers a config file by **walking up from each scan target
directory** (the nearest file wins). Override discovery with `--config PATH`.
Two filenames are recognised:

> **Discovery is target-relative, not cwd-relative.** For `linkguard docs/` the
> search starts at `docs/` (for `linkguard docs/a.md` it starts at `docs/`),
> even when you run the command from an unrelated working directory. A target
> that has no config anywhere up its tree contributes nothing, and discovery
> falls through to the next target; if *no* target yields a config the built-in
> defaults apply. Passing no target scans `.` and therefore discovers
> from the current working directory.

- **`linkguard.cfg`** — INI syntax (stdlib `configparser`).
- **`.linkguard.yml`** — a documented flat subset parsed by a ~40-line
  built-in reader (no third-party YAML library).

**Precedence:**

```text
CLI flags  >  --config file  >  auto-discovered file  >  built-in defaults
```

### Config keys

| Key | Type | Default | Meaning |
|---|---|---|---|
| `exclude` | list of globs | *(empty)* | Paths/globs skipped during directory discovery. Comma- or newline-separated. |
| `ignore` | list of substrings/globs/regexes | *(empty)* | A **broken** link whose URL matches any pattern is downgraded to `skipped`, so it never fails CI. |
| `extra_skip_schemes` | list of schemes | *(empty)* | Extra URL schemes (e.g. `ftp`, `ssh`) treated as `skipped` instead of `broken`. |
| `timeout` | number (seconds) | `10` | Default per-request timeout when `--timeout` is not given. |
| `no_network` | boolean | `false` | When `true`, remote checks are skipped by default (same as always passing `--no-network`). |

Unknown keys, a bad boolean, a non-positive timeout, an invalid `ignore`
regex, or malformed syntax are all reported as errors and exit `2`.

### `linkguard.cfg` example

```ini
# linkguard.cfg
[linkguard]
# paths/globs to skip entirely (comma- or newline-separated)
exclude = node_modules/*, vendor/*, .git/*

# URLs/patterns whose *broken* status is ignored (never fails CI).
# Substrings, globs (*, ?), or regular expressions.
ignore =
    https://example.com/deprecated-*
    https://internal.invalid/*

# extra schemes treated as "skipped" rather than "broken"
extra_skip_schemes = ftp, ssh

# default per-request timeout in seconds
timeout = 10

# skip remote checks by default (recommended for offline/doc repos)
no_network = false
```

### `.linkguard.yml` example

A single top-level `linkguard:` wrapper mirrors the INI `[linkguard]` section,
with keys indented one level under it. The flat form (keys at column 0, no
wrapper) is also accepted.

```yaml
# .linkguard.yml
linkguard:
  exclude:
    - node_modules/*
    - vendor/*
  ignore:
    - https://internal.invalid/*
    - ./archive/*.pdf
  extra_skip_schemes:
    - ftp
    - ssh
  timeout: 10
  no_network: true
```

A bundled sample config ships at the repo root ([`linkguard.cfg`](linkguard.cfg));
a worked example with `ignore` rules lives at
[`examples/broken/linkguard.cfg`](examples/broken/linkguard.cfg).

## Example output

### Text (default)

```console
$ python3 linkguard.py examples/clean --no-network
[ok] examples/clean/README.md:6:15 CONTRIBUTING.md
[ok] examples/clean/README.md:7:28 #example-clean
2 links: 2 ok, 0 broken, 0 skipped
```

```console
$ python3 linkguard.py examples/broken --no-network
[broken] examples/broken/README.md:6:31 ./does-not-exist.md (local file not found: ./does-not-exist.md)
[broken] examples/broken/README.md:7:31 #no-such-heading (anchor not found: #no-such-heading)
2 links: 0 ok, 2 broken, 0 skipped
```

Each finding is `[status] path:line:column target (detail)`, followed by a
summary line `N links: X ok, Y broken, Z skipped`.

### JSON (`--json`)

```console
$ python3 linkguard.py examples/broken --no-network --json
{
  "version": "1",
  "exit_code": 1,
  "summary": { "total": 2, "ok": 0, "broken": 2, "skipped": 0 },
  "files": [
    {
      "file": "examples/broken/README.md",
      "links": [
        {
          "url": "./does-not-exist.md",
          "line": 6, "column": 31,
          "status": "broken",
          "http_status": null,
          "method": "LOCAL",
          "error": "local file not found: ./does-not-exist.md",
          "type": "local"
        },
        {
          "url": "#no-such-heading",
          "line": 7, "column": 31,
          "status": "broken",
          "http_status": null,
          "method": "LOCAL",
          "error": "anchor not found: #no-such-heading",
          "type": "anchor"
        }
      ]
    }
  ],
  "file": "examples/broken/README.md"
}
```

> For a single-file scan the top-level `"file"` alias is included for backward
> compatibility; `files[]` is the authoritative multi-path structure.

### SARIF (`--sarif`)

```console
$ python3 linkguard.py examples/broken --no-network --sarif
{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "linkguard",
          "informationUri": "https://github.com/OWNER/linkguard",
          "version": "1.0.0",
          "rules": [
            { "id": "LG001", "name": "BrokenRemoteLink",
              "shortDescription": { "text": "Remote URL is unreachable" } },
            { "id": "LG002", "name": "MissingLocalFile",
              "shortDescription": { "text": "Local file target does not exist" } },
            { "id": "LG003", "name": "MissingAnchor",
              "shortDescription": { "text": "Intra-document anchor not found" } }
          ]
        }
      },
      "results": [
        {
          "ruleId": "LG002",
          "level": "error",
          "message": { "text": "local file not found: ./does-not-exist.md" },
          "locations": [{
            "physicalLocation": {
              "artifactLocation": { "uri": "examples/broken/README.md" },
              "region": { "startLine": 6, "startColumn": 31 }
            }
          }]
        }
      ]
    }
  ]
}
```

## Example CI usage

`linkguard` ships as a **composite GitHub Action** with **no dependency
install step** (the CLI is standard-library-only Python). It fails the job with
exit code `1` when any link is broken.

**One-line usage:**

```yaml
- uses: OWNER/linkguard@v1
  with:
    path: .
    args: --no-network          # offline-safe default for most docs repos
```

**Full workflow (offline check + SARIF upload to code scanning):**

```yaml
name: linkguard
on: [push, pull_request]
jobs:
  check-links:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: OWNER/linkguard@v1
        with:
          path: .
          args: --no-network --sarif --output linkguard.sarif
      - name: Upload SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: linkguard.sarif
```

**Without the Action** (plain runner step):

```yaml
- name: Check links
  run: python3 linkguard.py . --no-network
```

The Action's inputs:

| Input | Required | Default | Description |
|---|---|---|---|
| `path` | no | `.` | File or directory to scan. |
| `args` | no | `""` | Extra CLI arguments (e.g. `--no-network --sarif --output linkguard.sarif`). |

## How it works

`linkguard` is a single file (`linkguard.py`) organised into strictly layered
stages, which keeps every stage independently unit-testable. Pure functions
take plain arguments and return plain data — they never read global state and
never call `sys.exit`; only `main` touches the process.

```
path discovery ─▶ extract ─▶ classify ─▶ apply ignores ─▶ render ─▶ exit code
```

1. **Path discovery** (`discover_paths`) — expands CLI targets into a sorted
   list of `.md` files. Directories are walked recursively for `**/*.md`;
   `exclude` globs (config + `--exclude`) filter discovery. Explicitly named
   files are always kept.
2. **Extraction** (`extract_links`, `extract_assets`) — parses inline, titled,
   angle-bracket and autolink Markdown links, plus `![alt](src)` image/asset
   references (inline and reference-style). Fenced code blocks and inline code
   spans are masked so example snippets don't produce false positives. Each
   finding becomes a `Link` carrying `url`, `line`, `column`, and `type`
   (`remote` / `local` / `anchor` / `skipped`).
3. **Classification** (`classify`, `check_asset`) — dispatches by scheme:
   - **remote** `http(s)` → HEAD, falling back to GET, with the configured
     timeout. Under `--no-network` it is marked `skipped` instead.
   - **anchors** `#frag` / `./doc.md#frag` → headings are parsed from the
     target document and slugified GitHub-style, then compared.
   - **local files** and **assets** → resolved against the source file's
     directory and checked for existence.
   - non-navigable/unsupported schemes (`mailto:`, `tel:`, `javascript:`,
     `data:`, `ftp:`, …) are `skipped`.
4. **Ignore rules** (`apply_ignores`) — any `broken` link matching a config
   `ignore` pattern is downgraded to `skipped`, so it no longer fails CI.
5. **Rendering** (`render_text` / `render_json` / `render_sarif`) — produces
   the text/JSON/SARIF report, optionally written to `--output`.
6. **Exit code** (`main`) — `1` if any finding is still `broken`, else `0`;
   `2` on usage, I/O, or config errors.

## Running the tests

The suite uses the standard-library `unittest` runner only — no pytest, no
network, no secrets, no third-party packages.

```console
$ cd linkguard
$ python3 -m unittest discover -s tests
```

Verbose (per-test names):

```console
$ python3 -m unittest discover -s tests -v
```

A single module:

```console
$ python3 -m unittest discover -s tests -p "test_output.py"
```

The current suite runs **162 tests, all green** (2 are deliberately
`@unittest.expectedFailure`, documenting known extraction edge cases — see
[`TEST_REPORT.md`](TEST_REPORT.md) for the full coverage map). Modules:

| Module | Covers |
|---|---|
| `tests/test_extraction.py` | Link extraction (FEATURE 1) |
| `tests/test_targets.py` | Broken-link/anchor detection (FEATURE 2) |
| `tests/test_output.py` | JSON & SARIF schemas (FEATURE 3) |
| `tests/test_offline.py` | `--no-network` mode (FEATURE 4) |
| `tests/test_scan_config.py` | Recursive scan + config (FEATURE 5) |
| `tests/test_config.py` | Config subsystem (INI + YAML, precedence) |
| `tests/test_assets.py` | Image/asset reference checks |
| `tests/test_cli_exitcodes.py` | Exit codes 0/1/2 (FEATURE 6) |
| `tests/test_no_third_party.py` | Guard: standard-library-only imports |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All checked links OK (skips allowed). |
| `1` | At least one `broken` finding. |
| `2` | Usage error, unreadable file, or invalid config. |

## License

MIT — see [LICENSE](LICENSE).
