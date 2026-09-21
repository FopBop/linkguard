# RECON_NOTES — `linkguard`

**Task:** 01M31TJFADFF39TKK3RG2570DQ — Recon existing repo, produce concrete gap list.
**Author:** researcher (worker agent)
**Date:** 2026-09-20
**Scope:** Read-only audit of `workspace/product/linkguard/` against
`ARCHITECTURE_v1.md` §2.1/§7 and `PRODUCT_SELECTION.md` §7/§8.
**Constraint honored:** no product selection, no architecture, no scaffolding,
no feature code written. This file only.

> **Repo root (actual on-disk path):** `/opt/automaton/workspace/product/linkguard/`
> The task text referred to `workspace/…`; the real location is under
> `/opt/automaton/`. Equivalent aliases seen on disk:
> `/opt/automaton/workspace/linkguard/` (separate dir) — canonical repo is
> `/opt/automaton/workspace/product/linkguard/`.

---

## 0. Executive summary (read this first)

The repo is **far less complete than `BUILD_LOG.md` implies**, and — importantly —
`linkguard.py` **does not currently run at all as a CLI**.

| Fact | Evidence |
|---|---|
| Repo is at **build-order Step 1 (scaffold) only**; Step 2 is marked `_(pending)_` | `BUILD_LOG.md` §Step 2 |
| Git has **one commit** (`581781a chore: scaffold…`); `linkguard.py` is **modified but uncommitted** on top of it | `git log --oneline`, `git status` → ` M linkguard.py` |
| `linkguard.py` is **615 lines** and grew by **+498 / −135** vs the committed scaffold | `git diff --stat` |
| **The CLI entry point does not exist**: no `main`, `run`, `run_cli`, `build_parser` | `grep`/`hasattr` probe → all `False` |
| **FEATURE 5 (scan/config) does not exist**: no `discover_paths`, `load_config`, `apply_ignores` | `grep` → 0 hits |
| Working pure functions: `extract_links`, `classify`, `render_text`, `render_json`, `render_sarif` | runtime probe |
| `argparse` + `configparser` are **imported but never used** (dead imports; CLI absent) | `grep "argparse\." → 0`, `grep "configparser\." → 0` |
| `import fnmatch` is **present but never used** and is **NOT on the stdlib allow-list** in the guard test → `test_no_third_party` **FAILS** | test run output |
| Feature tests are **scaffold placeholders** (`@unittest.skip`), i.e. **16 skipped**, not real coverage | `tests/*.py` |

**Bottom line:** FEATURE 1, 2, 3 have real *library* code but **no runnable
entry point**; FEATURE 4 is a by-product of `classify()`'s `allow_network`
flag (works, untested); **FEATURE 5 is 100% missing**; **FEATURE 6 (CLI/exit
codes/action runtime) is missing the CLI half**. The suite is "green" only
because feature tests are skipped.

---

## (a) Full file inventory (one-line purpose each)

### Python source
| File | Purpose | State |
|---|---|---|
| `linkguard.py` | Single-file CLI + all logic (F1–F6). 615 lines. | **PARTIAL, uncommitted, non-runnable** (no CLI) |
| `linkguard/__init__.py` | Thin programmatic facade re-exporting `Link, extract_links, classify, run, main, run_cli, __version__`. | **BROKEN**: imports `run`, `main`, `run_cli` that do **not** exist in core → `import linkguard` raises `ImportError`/`AttributeError` |
| `linkguard/py.typed` | PEP 561 marker. | DONE (trivial) |

### Tests
| File | Purpose | State |
|---|---|---|
| `tests/test_no_third_party.py` | AST guard: assert `linkguard.py` imports stdlib only. | **ACTIVE + FAILING** (`fnmatch` flagged) |
| `tests/test_extraction.py` | F1 coverage (inline/titled/angle/nested/autolink; code+image ignored). | **STUB** (2 skips, `NotImplementedError`) |
| `tests/test_targets.py` | F2 coverage (local file ok/broken, anchor ok/broken). | **STUB** (3 skips) |
| `tests/test_output.py` | F3 coverage (`--json`/`--sarif` schema; mutual-exclusion exit 2). | **STUB** (3 skips) |
| `tests/test_offline.py` | F4 coverage (`--no-network` skips remote, keeps local/anchor). | **STUB** (2 skips) |
| `tests/test_scan_config.py` | F5 coverage (dir scan, exclude globs, malformed config → exit 2). | **STUB** (3 skips) |
| `tests/test_cli_exitcodes.py` | F6 coverage (exit 0/1/2, `--quiet`, `--timeout`). | **STUB** (3 skips) |

### Fixtures (`tests/fixtures/`)
`sample.md`, `anchors_only.md`, `empty.md`, `doc_with_headings.md`,
`nested/a.md`, `nested/b.md`, `linkguard.cfg` — static test inputs (carried
from the `mdlinkcheck` prototype where applicable). Present; **not yet
referenced by any non-stub test**.

### Packaging / distribution
| File | Purpose | State |
|---|---|---|
| `pyproject.toml` | PEP 621 metadata, `dependencies = []`, `requires-python >=3.8`, `[project.scripts] linkguard = "linkguard:...main"`. | Present; entry point target **broken** (CLI fn missing) |
| `LICENSE` | MIT. | DONE |
| `.gitignore` | caches, reports, venvs. | DONE |
| `.editorconfig` | whitespace consistency. | DONE |
| `CHANGELOG.md` | human history (starts 0.1.0). | Present |
| `README.md` | landing page / install+usage. | **PLACEHOLDER** (35 lines; real usage lands in Step 9) |
| `action.yml` | F6 GitHub Action wrapper (`composite`; runs `python3 linkguard.py <path> <args>`). | Present **but references a CLI that does not exist yet** |

### Schemas
| File | Purpose | State |
|---|---|---|
| `schemas/report.schema.json` | `--json` output schema (§3.3). | DONE (static) |
| `schemas/sarif.schema.json` | SARIF 2.1.0 subset (§3.4). | DONE (static) |

### Docs
| File | Purpose | State |
|---|---|---|
| `docs/USAGE.md` | CLI reference (flags, exit codes). | Present (70 lines) |
| `docs/CONFIG.md` | Config file spec (F5). | Present (50 lines) |
| `docs/CI.md` | GitHub Action usage (F6). | Present (50 lines) |

### Examples
`examples/clean/{README.md,CONTRIBUTING.md}`,
`examples/broken/{README.md,linkguard.cfg}`,
`examples/anchor/{README.md,guide.md}` — demo inputs. Present.

### CI
`.github/workflows/ci.yml` — matrix 3.8/3.11/3.13, `unittest` + self-check.
Present (will run against a non-existent CLI today).

### Top-level scaffold config
`linkguard.cfg` (bundled sample config, documentation only). Present.

---

## (b) Feature-by-feature status table

Features are the 6 MVP items in `PRODUCT_SELECTION.md` §7 (== `ARCHITECTURE_v1.md` §7 build steps 3–8).

| # | MVP feature (PRODUCT_SELECTION §7) | Status | Notes |
|---|---|---|---|
| **1** | Multi-link extraction (inline/titled/angle/nested/autolink; ignore fences/inline-code/images) | **DONE (library) / PARTIAL (unsurfaced)** | `extract_links`, `_strip_code`, `_split_target`, `_line_col` implemented; runtime probe extracts correctly. Untested (tests are stubs). No CLI to invoke it. |
| **2** | Broken-link detection: remote (HEAD→GET, redirect, timeout, non-HTTP→skipped) + local file existence + intra-doc anchors | **PARTIAL** | Local + anchor helpers (`_classify_local`, `_classify_anchor`, `_headings`, `_find_anchor`, `_slugify_heading`) implemented and **verified working** (probe: `./exists.md`→ok, `./missing.md`→broken, `#hello-world`→ok). Remote path exists (`_classify_remote`, `_classify_remote_get`) but **untested**; no CLI wiring. |
| **3** | Machine-readable output: `--json` + new `--sarif` | **PARTIAL** | `render_json` and `render_sarif` implemented; schemas vendored. **`--json`/`--sarif` flags do not exist** (no parser) so the contract (incl. mutual-exclusion → exit 2) is unenforced. Untested. |
| **4** | Offline mode `--no-network` | **PARTIAL** | `classify(..., allow_network=False)` implemented; probe shows remote→`skipped`, local/anchor still checked. **`--no-network` flag does not exist** (no parser). Untested. |
| **5** | Repo-wide scan + config: dir/glob input, `linkguard.cfg`/`.linkguard.yml` ignore rules, `--quiet`, `--timeout` | **MISSING** | No `discover_paths`, `load_config`, `apply_ignores`. `configparser`/`fnmatch` imported but unused. `--quiet`/`--timeout`/`--config`/`--exclude` flags absent. `docs/CONFIG.md` documents behavior that does not exist. |
| **6** | CI gate: exit codes 0/1/2 + `action.yml` | **MISSING (CLI half)** | Constants `EXIT_OK/BROKEN/USAGE` exist, but **no `main`/`run`/`run_cli`** → no exit-code behavior. `action.yml` + `docs/CI.md` present but invoke a non-existent CLI. |

**Status legend:** DONE = implemented and exercised; PARTIAL = some code
exists but the user-facing contract is incomplete or unverified; MISSING = no
implementation.

---

## (c) Exact file paths — where each feature lives / should live

| Feature | Lives now (partial) | Target location (per ARCH §2.1/§2.2) | Gap to close |
|---|---|---|---|
| F1 Extraction | `linkguard.py`: `_strip_code`, `_split_target`, `_line_col`, `extract_links`, regex consts (l.44–58, 123–246) | same file; tested by `tests/test_extraction.py` | write real test bodies |
| F2 Targets | `linkguard.py`: `_slugify_heading`, `_headings`, `_find_anchor`, `_classify_remote`, `_classify_remote_get`, `_classify_local`, `_classify_anchor`, `classify` (l.248–474) | same file; tested by `tests/test_targets.py` | write tests; wire into CLI |
| F3 Output | `linkguard.py`: `render_text`, `render_json`, `render_sarif`, `_summarize`, `_sarif_rule_id`, `SARIF_RULES` (l.61–72, 476–615) | same file + `schemas/report.schema.json`, `schemas/sarif.schema.json`; tested by `tests/test_output.py` | add `--json`/`--sarif` flags + mutual-exclusion |
| F4 Offline | `linkguard.py`: `classify(allow_network=…)` (l.428) | same file; tested by `tests/test_offline.py` | add `--no-network` flag; tests |
| F5 Scan+config | **nowhere** (`configparser`/`fnmatch` imported, unused) | `linkguard.py`: `discover_paths`, `load_config`, `apply_ignores`; sample `linkguard.cfg`; `docs/CONFIG.md`; tested by `tests/test_scan_config.py` | implement all three + flags |
| F6 CI gate | constants only (`EXIT_*`) | `linkguard.py`: `build_parser`, `run`, `main`; `action.yml`; `docs/CI.md`; tested by `tests/test_cli_exitcodes.py` | implement CLI + exit-code logic |
| Programmatic API | `linkguard/__init__.py` re-exports `run, main, run_cli` | same | core must export `run`/`main`/`run_cli` or facade must change |

---

## (d) How to run the tool + existing test command

**Repo root:** `/opt/automaton/workspace/product/linkguard/`

**Run the tool (documented form):**
```bash
cd /opt/automaton/workspace/product/linkguard
python3 linkguard.py [PATH ...] [--json|--sarif] [--no-network] [--quiet]
```
> ⚠️ **This currently does nothing** — `linkguard.py` has no `main()`;
> executing it just defines functions and exits with **no output / no exit
> code semantics**. There is no `if __name__ == "__main__":` block.

**Test command (stdlib `unittest`, offline):**
```bash
cd /opt/automaton/workspace/product/linkguard
python3 -m unittest discover -s tests -v
```
Current result: **`Ran 18 tests … FAILED (failures=1, skipped=16)`** —
`test_no_third_party` fails on `fnmatch`; the other 16 are skipped stubs.

**Manifest check (works):**
```bash
python3 -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(d['project']['name'], d['project']['dependencies'])"
# -> linkguard []
```

**Library-only smoke test (works today):**
```bash
python3 -c "
import importlib.util as u
s=u.spec_from_file_location('lg','linkguard.py'); m=u.module_from_spec(s); s.loader.exec_module(m)
print([(l.url) for l in m.extract_links('[a](https://x)')])"
```

---

## (e) Broken / incomplete code found

1. **No CLI entry point (blocker).** `linkguard.py` defines no `main`, `run`,
   `run_cli`, or `build_parser`, and has **no `if __name__ == "__main__"`
   block**. Consequences:
   - `python3 linkguard.py` produces **no usable behavior** (contradicts
     `BUILD_LOG.md` Step 1's "prints a not-implemented message and exits 0").
   - `action.yml` and both CI jobs reference a CLI that cannot run → CI would
     fail once un-skipped/self-check runs.
   - `pyproject.toml` `[project.scripts] linkguard = "linkguard:…main"` points
     at a missing function.
2. **`linkguard/__init__.py` is broken.** It executes
   `run = _core.run`, `main = _core.main`, `run_cli = _core.run_cli` — none of
   which exist in `linkguard.py`. `import linkguard` therefore raises
   `AttributeError` at import time.
3. **Failing guard test.** `import fnmatch` (l.25) is present but unused and is
   **not on the stdlib allow-list** in `tests/test_no_third_party.py` →
   `test_no_third_party` **FAILS** (`['fnmatch'] != []`). Either use it (F5
   exclude-glob matching) or remove it and whitelist it in the guard.
4. **Dead imports.** `argparse` (l.23) and `configparser` (l.25→l.24) are
   imported but never used — evidence the CLI/scanner layers were never
   written.
5. **Tests are placeholders, not coverage.** All 16 feature tests are
   `@unittest.skip(...)` with `raise NotImplementedError` bodies. The suite
   reports "green-ish" only because nothing runs. There is **no real
   happy/error-path coverage for any feature**, so `PRODUCT_SELECTION.md` §8
   ("at least one happy path and one error path per feature") is unmet.
6. **Uncommitted work.** `linkguard.py` is modified vs the single commit
   `581781a` (+498/−135) and not committed → `BUILD_LOG.md` understates the
   real state; the tree is dirty.
7. **Docs/action advertise unimplemented behavior.** `docs/USAGE.md`,
   `docs/CONFIG.md`, `docs/CI.md`, `examples/broken/linkguard.cfg` describe
   flags (`--json`, `--sarif`, `--no-network`, `--config`, `--exclude`,
   `--quiet`, `--timeout`, directory scan) that do not exist yet.

### Consistency notes vs. BUILD_LOG
- `BUILD_LOG.md` Step 1 claims "interface stubs only … every public function
  raises `NotImplementedError`". **This is no longer true**: `linkguard.py` now
  contains real extract/classify/render implementations (uncommitted). The log
  should be corrected or the work committed and logged as Step 3+.
- The prototype port ("seed with `mdlinkcheck.py` → rename `linkguard.py`")
  appears to have been done, but **`run`/`main` were dropped** in the port —
  this is the single most impactful gap.

---

## Gap list (prioritized, for the build worker — NOT done here)

1. **Implement the CLI layer in `linkguard.py`:** `build_parser`, `run`,
   `main`, and `if __name__ == "__main__": sys.exit(main(sys.argv[1:]))`;
   wire flags `--json/--sarif/--no-network/--quiet/--timeout/--config/
   --exclude/--output/--version/-h`. (F3, F4, F6 surfacing.)
2. **Implement FEATURE 5** in `linkguard.py`: `discover_paths` (recursive
   `**/*.md`, respect excludes — use or drop `fnmatch`), `load_config`
   (`linkguard.cfg` via `configparser`, `.linkguard.yml` built-in reader),
   `apply_ignores`. (F5.)
3. **Fix `linkguard/__init__.py`** once `run/main/run_cli` exist (or align
   `pyproject.toml` `[project.scripts]` target).
4. **Resolve the `fnmatch` guard failure** (use it or remove + allow-list).
5. **Replace all 16 skipped test stubs** with real happy/error-path bodies
   (F1–F6) so §8 done-criteria are actually met.
6. **Commit** the `linkguard.py` work and update `BUILD_LOG.md` (Step 2/3).
7. **Then** finalize README with actually-executed commands (Step 9) and
   verify CI self-check runs (Step 10).

---

*End of RECON_NOTES.md — recon only; no feature code written.*
