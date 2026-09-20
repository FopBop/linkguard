# linkguard — CLI usage reference

> **Status:** v1 scaffold. The CLI flags and exit codes below are the
> contracted interface (ARCHITECTURE_v1.md §3.1). The feature bodies that make
> them behave are implemented in the numbered build order (§7); until then the
> entry point prints a not-implemented notice and exits `2`.

## Invocation

The single-file form needs no install:

```console
$ python3 linkguard.py [PATH ...] [options]
```

If the package is installed (or on `PATH`), the console script works too:

```console
$ linkguard [PATH ...] [options]
```

`PATH` may be one or more `.md` files **or** directories. Directories are
scanned recursively for `**/*.md`. When omitted, the target defaults to `.`.

## Options

| Flag | Description |
|---|---|
| `PATH ...` | Markdown files or directories (default: `.`). |
| `--json` | Emit a single JSON report object (schema: `schemas/report.schema.json`). |
| `--sarif` | Emit a SARIF 2.1.0 log for CI annotations. Mutually exclusive with `--json`. |
| `--no-network` | Skip all HTTP checks; validate only local files + anchors. |
| `--quiet` | Print only broken findings (text mode). |
| `--timeout SEC` | Per-request timeout, default `10`. |
| `--config PATH` | Explicit config file; otherwise auto-discovered (`linkguard.cfg` / `.linkguard.yml`). |
| `--exclude GLOB` | Repeatable; extra path-exclusion globs merged with config excludes. |
| `--output PATH` | Write the report to a file instead of stdout. |
| `--version` | Print `linkguard <ver>` and exit `0`. |
| `-h`, `--help` | Show usage and exit `0`. |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All checked links OK (skips allowed). |
| `1` | At least one `broken` finding. |
| `2` | Usage error, unreadable file, or invalid config. |

## Examples

Check the current directory offline (no network, no install):

```console
$ python3 linkguard.py . --no-network
```

Emit SARIF for GitHub code-scanning annotations:

```console
$ python3 linkguard.py docs --sarif --output linkguard.sarif
```

Emit JSON and pipe into `jq`:

```console
$ python3 linkguard.py README.md --json | jq '.summary'
```

See `docs/CONFIG.md` for the config-file format and `docs/CI.md` for the
GitHub Action usage.
