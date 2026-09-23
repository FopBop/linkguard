# linkguard — configuration file spec

> **Status:** v1 scaffold. The config schema below is the contracted interface
> (ARCHITECTURE_v1.md §3.6); parsing is implemented in FEATURE 5 of the build
> order.

linkguard accepts two config filenames, auto-discovered by walking up from each
target directory (the nearest file wins) and overridable with `--config`.
Discovery is **target-relative, not cwd-relative**: `linkguard docs/` searches
from `docs/` even when run from an unrelated working directory, and if no target
yields a config the built-in defaults apply (passing no target scans `.` and so
discovers from the current working directory):

- `linkguard.cfg` — INI syntax, parsed with the stdlib `configparser`.
- `.linkguard.yml` — a documented flat subset (`key: value` plus `- item`
  lists) parsed by a ~40-line built-in reader. No third-party YAML library.

## Precedence

```text
CLI flags  >  --config file  >  auto-discovered file  >  built-in defaults
```

## `linkguard.cfg` format

```ini
# linkguard.cfg
[linkguard]
# paths/globs to skip entirely (comma- or newline-separated)
exclude = node_modules/*, vendor/*, .git/*

# per-URL or per-line ignore rules (substring or regex, one per line)
ignore  = https://intranet.example/*, ./archive/*.pdf

# extra schemes treated as "skipped" rather than "broken"
extra_skip_schemes = ftp, ssh

# default timeout when --timeout is not given
timeout = 10
```

## Keys

| Key | Type | Meaning |
|---|---|---|
| `exclude` | list of globs | Paths/globs skipped during directory discovery. |
| `ignore` | list of substrings/regexes | Links matching these are not reported as broken. |
| `extra_skip_schemes` | list of schemes | Schemes treated as `skipped` instead of `broken`. |
| `timeout` | number (seconds) | Default per-request timeout. |

## `.linkguard.yml` format

A documented flat subset parsed by the built-in reader (no third-party YAML
library): top-level `key: value` scalars and `- item` block lists. A single
top-level `linkguard:` wrapper mirrors the INI `[linkguard]` section, with the
real keys indented one level under it:

```yaml
# .linkguard.yml
linkguard:
  exclude:
    - node_modules/*
    - vendor/*
  ignore:
    - https://intranet.example/*
    - ./archive/*.pdf
  extra_skip_schemes:
    - ftp
    - ssh
  timeout: 10
```

The flat form (keys at column 0, no wrapper) is also accepted. The wrapper is
the whole document: any key that dedents back to column 0 inside it is a parse
error with a line number, rather than being silently ignored. Tabs for
indentation, list items without a parent key, and unknown keys are all reported
as malformed config.

Malformed config produces exit code `2` (usage error).

A bundled sample lives at the repo root (`linkguard.cfg`); an example with
ignore rules lives at `examples/broken/linkguard.cfg`.
