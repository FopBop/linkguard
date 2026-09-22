# CHECKPOINT_MVP — integration smoke run of the full MVP CLI

**Task:** 01M31TJFAGKPCE9ZDMHFVZBVV5 — tester
**Goal:** 01M31TH4CG3F0CC8G6B657V4KT
**Date:** 2026-09-22
**Commit under test:** `2511180` (`fix(facade): provide run/run_cli …`), clean tree
**Inputs:** completed feature tasks 1–5, `RECON_NOTES.md`, `ARCHITECTURE_v1.md`

---

## 1. Verdict (read first)

| Area | Result |
|---|---|
| Feature **bodies** F1–F5 (library layer) | ✅ **PASS** — all work when called directly |
| Unit test suite (`python3 -m unittest discover -s tests`) | ✅ **PASS** — 116 tests, 0 failures, 10 skipped |
| `--json` output + schema | ✅ **PASS** — valid vs `schemas/report.schema.json` |
| `--sarif` output + schema | ✅ **PASS** — valid vs `schemas/sarif.schema.json` |
| `--json`/`--sarif` mutual exclusion → exit 2 | ✅ **PASS** |
| **Full CLI surface (`main` / `_parse_output_args`)** | ❌ **FAIL** — see defects D1–D6 |

**Bottom line:** the *features* compose correctly, but the *CLI entry point*
(`linkguard.py::main`, `linkguard.py::_parse_output_args`) only wires
`--json`/`--sarif` and bare file paths. **Every other documented flag is
unimplemented or ignored**, text mode prints nothing, and directory scanning /
config loading are never invoked from the CLI. The documented run command in
`docs/USAGE.md` does **not** work as written.

All defects are enumerated in §5 with exact file paths and line numbers for the
debugger task. The fixed fixture and reproduction commands are in §3.

---

## 2. Fixture used (exercises every implemented feature)

Created under `/tmp/mvpfix/` (not committed; reproducible from §3.1):

```
/tmp/mvpfix/
├── README.md          # links + anchor + good/bad image assets + broken local link
├── docs/guide.md      # anchor target + cross-file asset ref + broken anchor
├── assets/logo.svg    # existing asset (good)
└── linkguard.cfg      # exclude + ignore rules, no_network=true
```

It deliberately covers: inline/titled links (F1), local-broken + anchor-broken
(F2), image/asset refs good+bad (asset check), config `exclude`/`ignore`/
`no_network` (F5), and structured output (F3).

---

## 3. Exact commands run and observed output

All commands run from repo root
`/opt/automaton/workspace/product/linkguard/`.

### 3.1 Fixture creation

```console
$ mkdir -p /tmp/mvpfix/docs /tmp/mvpfix/assets && cd /tmp/mvpfix
$ cat > README.md <<'EOF'
# Fixture Project

See [the docs](docs/guide.md) and [guide anchor](docs/guide.md#usage).

Broken relative link: [missing](docs/nope.md)
Anchor link to own section: [jump](#fixture-project)

Image asset good: ![logo](assets/logo.svg)
Image asset ghost: ![ghost](assets/ghost.png)
EOF
$ cat > docs/guide.md <<'EOF'
# Guide

## Usage

![diagram](../assets/logo.svg)

Broken anchor: [fake](#does-not-exist)
EOF
$ printf '<svg xmlns="http://www.w3.org/2000/svg"></svg>\n' > assets/logo.svg
$ cat > linkguard.cfg <<'EOF'
[linkguard]
exclude = docs/ignored.md
ignore = nope.md
no_network = true
EOF
```

### 3.2 Regression suite

```console
$ python3 -m unittest discover -s tests
...
Ran 116 tests in 4.461s

OK (skipped=10)
```

### 3.3 Text mode (default) — ❌ produces NO output

```console
$ python3 linkguard.py /tmp/mvpfix/README.md
$ echo "EXIT=$?"
EXIT=1
```

> **Defect D1:** exit code `1` is correct, but **no report is printed**. The
> documented human-readable report never appears. (`render_text` exists at
> `linkguard.py:1230` and works — see §4 — but `main()` never calls it.)

Clean file, for contrast:

```console
$ printf '# Clean\n[ok](docs/guide.md)\n' > /tmp/mvpfix/clean.md
$ python3 linkguard.py /tmp/mvpfix/clean.md
$ echo "EXIT=$?"
EXIT=0
```

### 3.4 `--json` — ✅ works and is schema-valid

```console
$ python3 linkguard.py /tmp/mvpfix/README.md --json
{
  "version": "1",
  "exit_code": 1,
  "summary": { "total": 6, "ok": 4, "broken": 2, "skipped": 0 },
  "files": [
    {
      "file": "/tmp/mvpfix/README.md",
      "links": [
        { "url": "docs/guide.md", "line": 3, "column": 5, "status": "ok",
          "type": "local", "method": "LOCAL", "error": null },
        { "url": "docs/guide.md#usage", "line": 3, "column": 35, "status": "ok",
          "type": "local", "method": "LOCAL", "error": null },
        { "url": "docs/nope.md", "line": 5, "column": 23, "status": "broken",
          "type": "local", "method": "LOCAL",
          "error": "local file not found: docs/nope.md" },
        { "url": "#fixture-project", "line": 6, "column": 29, "status": "ok",
          "type": "anchor", "method": "LOCAL", "error": null },
        { "url": "assets/logo.svg", "line": 8, "column": 19, "status": "ok",
          "type": "local", "method": "LOCAL", "error": null },
        { "url": "assets/ghost.png", "line": 9, "column": 18, "status": "broken",
          "type": "local", "method": "LOCAL",
          "error": "asset not found: assets/ghost.png" }
      ]
    }
  ],
  "file": "/tmp/mvpfix/README.md"
}
$ echo "EXIT=$?"
EXIT=1
```

(Full output captured verbatim during the run; abridged here for readability.)
Schema validation against `schemas/report.schema.json`: **no errors**.

### 3.5 `--sarif` — ✅ works and is schema-valid

```console
$ python3 linkguard.py /tmp/mvpfix/README.md --sarif
{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [ { "tool": { "driver": { "name": "linkguard",
      "informationUri": "https://github.com/OWNER/linkguard",
      "version": "1.0.0",
      "rules": [ {"id":"LG001",...}, {"id":"LG002",...}, {"id":"LG003",...} ] } },
    "results": [
      { "ruleId": "LG002", "level": "error",
        "message": { "text": "local file not found: docs/nope.md" },
        "locations": [ { "physicalLocation": {
            "artifactLocation": { "uri": "/tmp/mvpfix/README.md" },
            "region": { "startLine": 5, "startColumn": 23 } } } ] },
      { "ruleId": "LG002", "level": "error",
        "message": { "text": "asset not found: assets/ghost.png" },
        "locations": [ { "physicalLocation": {
            "artifactLocation": { "uri": "/tmp/mvpfix/README.md" },
            "region": { "startLine": 9, "startColumn": 18 } } } ] }
    ] } ]
}
$ echo "EXIT=$?"
EXIT=1
```

Schema validation against `schemas/sarif.schema.json`: **no errors**.

### 3.6 Mutual exclusion — ✅ works

```console
$ python3 linkguard.py /tmp/mvpfix/README.md --json --sarif
linkguard: error: --json and --sarif are mutually exclusive
$ echo "EXIT=$?"
EXIT=2
```

### 3.7 Documented flags from `docs/USAGE.md` — ❌ all fail

```console
$ python3 linkguard.py /tmp/mvpfix/README.md --no-network
linkguard: error: unknown option: --no-network            # EXIT=2
$ python3 linkguard.py /tmp/mvpfix/README.md --quiet
linkguard: error: unknown option: --quiet                 # EXIT=2
$ python3 linkguard.py /tmp/mvpfix/README.md --timeout 3
linkguard: error: unknown option: --timeout               # EXIT=2
$ python3 linkguard.py /tmp/mvpfix/README.md --config /tmp/mvpfix/linkguard.cfg
linkguard: error: unknown option: --config                # EXIT=2
$ python3 linkguard.py /tmp/mvpfix/README.md --exclude 'docs/*'
linkguard: error: unknown option: --exclude               # EXIT=2
$ python3 linkguard.py /tmp/mvpfix/README.md --output /tmp/out.json --json
linkguard: error: unknown option: --output                # EXIT=2
$ python3 linkguard.py --help
linkguard: error: unknown option: --help                  # EXIT=2   (should be 0 + usage)
$ python3 linkguard.py --version
linkguard: error: unknown option: --version               # EXIT=2   (should be 0 + "linkguard 1.0.0")
```

### 3.8 Directory scan and default-`.` target — ❌ fail

```console
$ python3 linkguard.py /tmp/mvpfix
linkguard: error: cannot read /tmp/mvpfix: [Errno 21] Is a directory: '/tmp/mvpfix'
# EXIT=2

$ cd /tmp/mvpfix && python3 /opt/automaton/workspace/product/linkguard/linkguard.py
linkguard: error: no input files
# EXIT=2
```

> Documented behavior (`docs/USAGE.md`): “Directories are scanned recursively
> for `**/*.md`. When omitted, the target defaults to `.`.” Neither holds.

---

## 4. Proof the feature bodies themselves work (library layer)

Because `main()` never calls them, the F4/F5/render code paths are only
reachable programmatically. Direct probes (importing `linkguard.py` by path)
confirm they are correct and only *unwired*:

```console
$ python3 - <<'PY'
import importlib.util as u
s=u.spec_from_file_location("lg","linkguard.py"); lg=u.module_from_spec(s); s.loader.exec_module(lg)

cfg = lg.load_config('/tmp/mvpfix')                 # F5 config discovery
print(cfg.to_dict())
# {'exclude': ['docs/ignored.md'], 'ignore': ['nope.md'],
#  'extra_skip_schemes': [], 'timeout': 10.0, 'no_network': True,
#  'path': '/tmp/mvpfix/linkguard.cfg', 'source': 'linkguard.cfg'}

l = lg.Link(url="http://example.com/x", line=1, column=1)
lg.classify(l, allow_network=False, timeout=10)     # F4 offline mode
print(l.status)                                      # skipped

l2 = lg.Link(url="docs/nope.md", line=1, column=1); l2.status="broken"
lg.apply_ignores([l2], cfg)                          # F5 ignore rules
print(l2.status)                                     # skipped

print(repr(lg.render_text([l2])[:100]))              # F3 text renderer
# '[skipped] -:1:1 docs/nope.md (ignored by config)\n1 links: 0 ok, 0 broken, 1 skipped\n'
PY
```

Observed: config discovery, offline mode, ignore application and text rendering
all behave as documented — **when invoked directly**.

---

## 5. Integration defects (for the debugger task)

All in a single file: **`workspace/product/linkguard/linkguard.py`**.

| ID | Severity | Location | Defect |
|---|---|---|---|
| **D1** | High | `main` body, `linkguard.py:1400-1452` (after the `fmt == "json"`/`"sarif"` branches) | Text mode never calls `render_text` (`linkguard.py:1230`). Running the CLI on a broken file exits `1` but prints **nothing**. Fix: add `else: sys.stdout.write(render_text(all_links))`, honouring `--quiet`. |
| **D2** | High | `_parse_output_args`, `linkguard.py:1362-1397` | The parser only recognises `--json`/`--sarif`. Every other documented flag (`--no-network`, `--quiet`, `--timeout`, `--config`, `--exclude`, `--output`, `--version`, `-h/--help`) raises `UsageError("unknown option: …")` → exit 2. Fix: parse the full surface (argparse or a hand-rolled parser). |
| **D3** | High | `main`, `linkguard.py:1425-1434` | `load_config` (`linkguard.py:1135`) and `apply_ignores` (`linkguard.py:1192`) are **never called**. A discovered/explicit `linkguard.cfg` has no effect; `--config` (once D2 is fixed) must set `Config.no_network`/`timeout` and feed `apply_ignores`. `ConfigError` must map to exit 2. |
| **D4** | High | `main`, `linkguard.py:1419-1424` | Directory `PATH`s are opened with `open()` → `IsADirectoryError` → exit 2. No recursive `**/*.md` discovery exists (`grep` for `discover_paths`/`os.walk`/`glob` in `linkguard.py` → 0 hits; `fnmatch` is imported at the top only for `_matches_ignore`). Fix: add a `discover_paths(paths)` that expands dirs, applies `Config.exclude` globs, and defaults to `.`. |
| **D5** | Medium | `main`, `linkguard.py:1400-1452` | `classify()` is always called with `allow_network=False, timeout=DEFAULT_TIMEOUT` hard-coded — the `--no-network` and `--timeout` flags can never reach it. Fix: thread `cfg.no_network` / `cfg.timeout` (and flag overrides) through. |
| **D6** | Medium | `main`, `linkguard.py:1444-1450` | `--output PATH` is unimplemented: no file-writing path exists, so SARIF/JSON can only go to stdout. `docs/USAGE.md` and `docs/CI.md` both document `--output linkguard.sarif`. Fix: write the rendered report to the file when `--output` is given. |
| **D7** | Low | `linkguard.py:1400-1452` | No `--version` / `-h` handling and no usage/help text. `__version__ == "1.0.0"` (`linkguard.py:36`) is available but never surfaced. Fix: print `linkguard <ver>` / usage, exit 0. |

**Cross-reference:** `RECON_NOTES.md` §(b) already flagged FEATURE 6 as
“MISSING (CLI half)” and FEATURE 5 as “MISSING”; this checkpoint confirms the
gap is isolated to the CLI wiring while the underlying feature bodies are
present and correct.

---

## 6. Recommended re-test command (after the debugger fix)

```console
$ cd /opt/automaton/workspace/product/linkguard
$ python3 -m unittest discover -s tests            # expect: OK (no failures)
$ python3 linkguard.py /tmp/mvpfix                 # dir scan, text report, EXIT=1
$ python3 linkguard.py /tmp/mvpfix --no-network --quiet   # broken only, EXIT=1
$ python3 linkguard.py /tmp/mvpfix --config linkguard.cfg --json  # ignore applies -> EXIT=0
$ python3 linkguard.py /tmp/mvpfix/README.md --sarif --output /tmp/lg.sarif
$ python3 linkguard.py --version && python3 linkguard.py --help
```

Expected once D1–D7 are fixed: text report printed, all flags accepted, config
`ignore = nope.md` (D3) downgrades `docs/nope.md` to `skipped` so the config run
exits `0`, and `--output` writes a file.

---

## 7. Test-harness note (no changes made)

No source files were modified by this checkpoint (verification-only task). The
fixture lives outside the repo under `/tmp/mvpfix/` and is fully reproducible
from §3.1. The 116-test suite remains green at commit `2511180`.
