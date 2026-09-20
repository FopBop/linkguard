# linkguard — configuration file spec

> **Status:** v1 scaffold. The config schema below is the contracted interface
> (ARCHITECTURE_v1.md §3.6); parsing is implemented in FEATURE 5 of the build
> order.

linkguard accepts two config filenames, auto-discovered by walking up from each
target directory (the nearest file wins) and overridable with `--config`:

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

Malformed config produces exit code `2` (usage error).

A bundled sample lives at the repo root (`linkguard.cfg`); an example with
ignore rules lives at `examples/broken/linkguard.cfg`.
