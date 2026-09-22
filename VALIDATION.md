# VALIDATION.md — Independent validation report: `linkguard` v1

**Role:** independent-validator
**Task ID:** 01M3572VY019XC9504W1Y9Z4H6
**Goal ID:** 01M31TH4CG3F0CC8G6B657V4KT
**Method:** fresh `git clone` into a scratch dir, README-only reproduction, a NEW self-authored
adversarial fixture, per-feature observable checks with raw captured output, schema validation of
machine-readable outputs, and a full offline test-suite run from the clean state.
**Independence note:** `TEST_REPORT.md` was **not opened** for any verdict in this document and its
pass/fail claims were **not** copied. `VALIDATION_EVIDENCE.md` (prior task) was used **only as a
pointer to which checks to run**; every result below was **re-executed and re-observed** by this
validator. Feature/source code was **not modified**. Findings are reported, not fixed.

---

## (a) Revision under test, date, environment

| Item | Value |
|---|---|
| Source repo | `/opt/automaton/workspace/product/linkguard` |
| Scratch clone | `/tmp/lgval/repo` |
| Clone command | `git clone -q /opt/automaton/workspace/product/linkguard repo` |
| **Revision under test (`git rev-parse HEAD`)** | `830c5332e12c17a04f41be4f0f3ccd1c5a8dc3eb` (short `830c533`) |
| HEAD subject | `docs(readme): full install, usage, CLI/config reference, examples, CI, tests` |
| Date of validation | **2026-09-22** (UTC) |
| Working tree at clone | **clean** (`git status --porcelain` in the clone → empty) |
| Working tree after validation | **clean** — no tracked file modified (`git status --porcelain \| grep -v '^??'` → empty) |
| OS / kernel | Linux `7.0.0-31-generic` `x86_64`, glibc 2.43 |
| Interpreter | `Python 3.14.4` (`python3`) |
| Network for core checks | **None required** — all MVP checks below run under `--no-network`; one remote HEAD→GET probe was run separately (see F2) |
| Repo-tracked source files modified | **None** |

Authoritative MVP feature source: `workspace/product/PRODUCT_SELECTION.md` §7 (6 features), mapped
1:1 by `ARCHITECTURE_v1.md` §0/§2.1 onto the shipped code. Feature labels F1–F6 below follow that
list.

---

## (b) Exact install/run commands and raw outcome

README "Install and setup" claims the zero-friction path is *"nothing to install … clone and run the
single file."* Reproduction:

```console
$ git clone -q /opt/automaton/workspace/product/linkguard repo && cd repo
$ python3 linkguard.py --version
linkguard 1.0.0
EXIT=0
```

**Outcome:** ✅ Reproducible as written. No `pip install`, no third-party package, no network.
The README documents the install URL with an `OWNER` placeholder (no public URL exists in this
environment); the local repo path was substituted — an expected placeholder, not an inaccuracy. No
other inference was needed.

---

## (c) Per-feature table: Feature | Claimed by spec? | Check used | Observed result | PASS/FAIL

| Feature | Claimed by spec? | Check used | Observed result | PASS/FAIL |
|---|---|---|---|---|
| **F1** Multi-link extraction + code/inline masking (`extract_links`, `_strip_code`, `extract_assets`) | YES (PRODUCT_SELECTION §7; ARCHITECTURE §2.2; README "How it works") | Self-authored `README.md` with a fenced pseudo-link `in-fence.md` + inline-code pseudo-link `in-code.md`; `python3 linkguard.py fix/README.md --no-network` | `in-fence.md` and `in-code.md` **absent** from findings; all 10 real links extracted | **PASS** |
| **F2** Broken-link detection: local file, intra-doc anchor, cross-doc anchor, remote HEAD→GET, skipped schemes | YES (PRODUCT_SELECTION §7; ARCHITECTURE §2.2) | Fixture matrix: valid/broken local; valid/broken self anchor; valid/broken cross anchor; valid/missing asset; `mailto:`; remote probe | valid⇒`[ok]`, missing⇒`[broken]`, missing anchor⇒`[broken]` (both self & cross), missing asset⇒`[broken]`, `mailto:`⇒`[skipped]`; remote `https://example.com/`⇒`[ok] (HTTP 200)` | **PASS** |
| **F3** Machine-readable output `--json` + `--sarif` (SARIF 2.1.0), mutually exclusive | YES (PRODUCT_SELECTION §7; ARCHITECTURE §2.2/§3.3/§3.4) | Emit both; validate against `schemas/report.schema.json` & `schemas/sarif.schema.json` via `tests/schema_validator.py`; `--json --sarif` together | `report.json => VALID`, `report.sarif => VALID`; SARIF header `"version":"2.1.0"` with LG001/LG002/LG003 rules; `--json --sarif` ⇒ `EXIT=2` | **PASS** |
| **F4** Offline mode `--no-network` | YES (PRODUCT_SELECTION §7; ARCHITECTURE §1.2) | Run fixture offline; run `examples/clean` offline | Remote⇒`[skipped] (remote check disabled (--no-network))` while local/anchor still classified; clean offline scan ⇒ `EXIT=0` | **PASS** |
| **F5** Repo-wide scan + config (`discover_paths`, `load_config`, `apply_ignores`; `--quiet`, `--timeout`, `--exclude`) | YES (PRODUCT_SELECTION §7; ARCHITECTURE §2.2) | Recursive dir scan incl. `sub/deep.md` with `../` relative link; `--config` `exclude = sub/*`; `--quiet`; `--timeout` validation | Recursion + relative resolution correct (`../README.md`… `../gone.md`); `exclude` dropped total `12 → 10` links; `--timeout = -5` ⇒ `EXIT=2` with error message | **PASS** (with a **documentation caveat on auto-discovery — see (f) D2**) |
| **F6** CI gate: deterministic exit codes 0/1/2 + `action.yml` | YES (PRODUCT_SELECTION §7; ARCHITECTURE §2.2) | Run clean / broken / usage-error / bad-config cases | `clean ⇒ 0`, `broken ⇒ 1`, `--json --sarif ⇒ 2`, bad config ⇒ `2`; `action.yml` present (composite action) | **PASS** |

**Per-feature summary: F1 PASS, F2 PASS, F3 PASS, F4 PASS, F5 PASS (doc caveat), F6 PASS.**

### Raw evidence excerpts (re-observed by this validator)

F1/F2 (fixture, offline):
```console
$ python3 linkguard.py /tmp/lgval/fix/README.md --no-network
[ok] .../README.md:3:14 ok.md
[broken] .../README.md:4:15 ./missing-file.md (local file not found: ./missing-file.md)
[ok] .../README.md:5:20 #fixture-root
[broken] .../README.md:6:21 #no-such-anchor (anchor not found: #no-such-anchor)
[ok] .../README.md:7:21 ok.md#heading-two
[broken] .../README.md:8:22 ok.md#nope-anchor (anchor not found: ok.md#nope-anchor)
[skipped] .../README.md:11:17 mailto:z@example.org (skipped scheme)
[skipped] .../README.md:12:9 https://example.com/ (remote check disabled (--no-network))
[ok] .../README.md:9:14 img/present.png
[broken] .../README.md:10:15 img/absent.png (asset not found: img/absent.png)
10 links: 4 ok, 4 broken, 2 skipped
```
*(fenced `in-fence.md` and inline-code `in-code.md` did not appear ⇒ masking held.)*

F2 (remote, network on):
```console
$ printf '# T\n[ok](https://example.com/)\n' > /tmp/lgval/remote.md
$ python3 linkguard.py /tmp/lgval/remote.md --timeout 10
[ok] /tmp/lgval/remote.md:2:1 https://example.com/ (HTTP 200)
1 links: 1 ok, 0 broken, 0 skipped
EXIT=0
```

F3 (schema validation):
```console
report.json  => VALID   (schemas/report.schema.json)
report.sarif => VALID   (schemas/sarif.schema.json)
```

F6 (exit codes):
```console
clean  EXIT=0
broken EXIT=1
--json --sarif EXIT=2
bad config EXIT=2
```

---

## (d) Full test-suite result from the clean state

**Command (exactly as README documents):**
```console
$ cd /tmp/lgval/repo
$ python3 -m unittest discover -s tests
```

**Raw tail:**
```
...
Ran 162 tests in 10.952s

OK (expected failures=2)
```

| Metric | Value |
|---|---|
| Tests run | **162** |
| Result | **OK** |
| Failures / Errors | **0 / 0** |
| Expected failures | **2** (deliberate, per README) |
| Network required | **No** (offline) |
| Runner | stdlib `unittest` only |

The two deliberate expected failures are `test_extraction.InlineLinkExtractionTests.test_angle_bracket_target_is_extracted`
and `test_extraction.InlineLinkExtractionTests.test_nested_parentheses_are_kept`. README's claim of
"162 tests … (2 are deliberately `@unittest.expectedFailure`)" **matches exactly**. Non-fatal
`ResourceWarning`s from `tempfile.py` during remote-stub tests do not affect pass/fail.

**Stdlib-only guard (ARCHITECTURE §6.3):**
```console
$ python3 -m unittest tests.test_no_third_party
Ran 2 tests in 0.028s
OK
```

---

## (e) Self-authored fixture: path, contents, command, observed output

A brand-new fixture was authored by this validator (nothing repo-provided was reused).
Path: `/tmp/lgval/fix/`. Tree:
```
/tmp/lgval/fix/README.md
/tmp/lgval/fix/ok.md
/tmp/lgval/fix/img/present.png
/tmp/lgval/fix/sub/deep.md
/tmp/lgval/fix/my.cfg
```

`fix/README.md` (exercises valid/broken link, valid/broken self anchor, valid/broken cross anchor,
valid/missing asset, skipped scheme, offline-skipped remote, fenced-code masking, inline-code
masking):
```markdown
# Fixture Root

Valid local: [a](ok.md)
Broken local: [b](./missing-file.md)
Valid self anchor: [c](#fixture-root)
Broken self anchor: [d](#no-such-anchor)
Valid cross anchor: [e](ok.md#heading-two)
Broken cross anchor: [f](ok.md#nope-anchor)
Valid asset: ![g](img/present.png)
Broken asset: ![h](img/absent.png)
Skipped scheme: [i](mailto:z@example.org)
Remote: [j](https://example.com/)

```text
[not a link](in-fence.md)
```

Inline `[also not](in-code.md)` span.
```

`fix/ok.md`:
```markdown
# Heading Two

body
```

`fix/sub/deep.md` (recursion + relative path resolution):
```markdown
# Deep

up: [r](../README.md)
bad: [x](../gone.md)
```

`fix/my.cfg`:
```ini
[linkguard]
exclude = sub/*
```

**Commands and observed output:**
```console
$ python3 linkguard.py /tmp/lgval/fix/README.md --no-network
[ok] .../fix/README.md:3:14 ok.md
[broken] .../fix/README.md:4:15 ./missing-file.md (local file not found: ./missing-file.md)
[ok] .../fix/README.md:5:20 #fixture-root
[broken] .../fix/README.md:6:21 #no-such-anchor (anchor not found: #no-such-anchor)
[ok] .../fix/README.md:7:21 ok.md#heading-two
[broken] .../fix/README.md:8:22 ok.md#nope-anchor (anchor not found: ok.md#nope-anchor)
[skipped] .../fix/README.md:11:17 mailto:z@example.org (skipped scheme)
[skipped] .../fix/README.md:12:9 https://example.com/ (remote check disabled (--no-network))
[ok] .../fix/README.md:9:14 img/present.png
[broken] .../fix/README.md:10:15 img/absent.png (asset not found: img/absent.png)
10 links: 4 ok, 4 broken, 2 skipped

$ python3 linkguard.py /tmp/lgval/fix --no-network                 # recursive scan
... [ok] .../fix/sub/deep.md:3:5 ../README.md
... [broken] .../fix/sub/deep.md:4:6 ../gone.md (local file not found: ../gone.md)
12 links: 5 ok, 5 broken, 2 skipped

$ python3 linkguard.py /tmp/lgval/fix --no-network --config /tmp/lgval/fix/my.cfg   # exclude sub/*
10 links: 4 ok, 4 broken, 2 skipped
```

**Result:** every intended case produced the expected classification (valid ⇒ ok; missing
file/anchor/asset ⇒ broken; fenced & inline-code pseudo-links ⇒ masked; remote-offline ⇒ skipped;
`exclude` removed the sub-directory findings). **PASS.**

---

## (f) Discrepancies between README/spec claims and observed behavior

| ID | Severity | Claim (source) | Observed (re-verified) | Impact |
|---|---|---|---|---|
| **D1** | Low (upstream wording only) | `PRODUCT_SELECTION.md` §7 F5 mentions a **`linkguard.toml`** config | Shipped code/docs support `linkguard.cfg` + `.linkguard.yml`; `grep -c 'linkguard.toml' README.md docs/*.md` = **0** in every shipped doc. No TOML support exists in code. | **Cosmetic** — upstream product-selection wording differs from the shipped, self-consistent docs. Not a functional defect. |
| **D2** | **Medium (real doc-vs-behavior mismatch)** | README §Configuration (lines 136–137): *"`linkguard` auto-discovers a config file by **walking up from each scan target directory** (the nearest file wins)."* | `linkguard.py` line 1631 calls `load_config(start_dir=os.getcwd(), …)` — it walks up from the **current working directory**, NOT from each target path. Repro: cwd=`repo/`, `python3 linkguard.py /tmp/lgval/yfix --no-network` did **not** apply `/tmp/lgval/yfix/.linkguard.yml` (link stayed `[broken]`); the same target scanned with cwd **inside** the fixture applied it (`[skipped] … (ignored by config)`, exit 0); explicit `--config` always applied it. | **Documented behavior is inaccurate.** Auto-discovery is CWD-relative, not target-relative. Explicit `--config` is always correct. **Flagged for the doc owner / next iteration.** |
| **D3** | None (false alarm, resolved) | — | Initially suspected `ok.md#heading-two`-style cross anchors mis-classified; verified valid cross anchor ⇒ `[ok]`, invalid cross anchor ⇒ `[broken]` (GitHub slug semantics). | **Correct behavior**, not a defect. |
| **D4** | Informational | README "Running the tests" module list (incl. `test_config.py`, `test_assets.py`) | All documented test modules present and running; count 162 matches README. | **Consistent.** |
| **D5** | Informational | README "Example output" blocks (`examples/clean` → 2 ok; `examples/broken` → 2 broken) | Re-ran: `examples/clean` → `2 links: 2 ok, 0 broken, 0 skipped`; `examples/broken` → `2 links: 0 ok, 2 broken, 0 skipped` — exact match. | **Consistent.** |

**Discrepancy summary:** one **medium** documentation-vs-behavior mismatch (**D2**: config
auto-discovery is CWD-relative, contradicting README's "from each scan target directory") and one
cosmetic upstream-wording difference (**D1**). No MVP feature is missing or non-functional.

---

## (g) Top-line verdict

> ### Does `linkguard` v1 meet its documented MVP criteria? — **YES**

**Citing evidence:**
- **F1 PASS** — new fixture: fenced `in-fence.md` and inline-code `in-code.md` were masked; all 10
  real links extracted (§c, §e).
- **F2 PASS** — valid local / valid self anchor / valid cross anchor / valid asset ⇒ `[ok]`;
  broken local / broken self anchor / broken cross anchor / missing asset ⇒ `[broken]`; `mailto:`
  ⇒ `[skipped]`; remote `https://example.com/` ⇒ `[ok] (HTTP 200)` (§c, §e).
- **F3 PASS** — `report.json` and `report.sarif` both **VALID** against the vendored schemas; SARIF
  `"version":"2.1.0"` with LG001/LG002/LG003; `--json --sarif` ⇒ exit 2 (§c).
- **F4 PASS** — `--no-network` yields `[skipped]` for remotes while local/anchor checks still run;
  clean offline scan exits 0 (§c).
- **F5 PASS** — recursive discovery + relative-path resolution correct; `exclude` honored
  (12→10 links); `--timeout` validated. *(Carries the D2 documentation caveat, which is a doc
  defect, not a functional failure.)* (§c, §e).
- **F6 PASS** — exit codes 0/1/2 deterministic across clean/broken/usage/config-error; `action.yml`
  present (§c).
- **Full suite (clean state)** — **162 tests, OK, 2 expected failures, 0 failures/errors, offline**
  (§d).
- **No source file modified** — working tree clean at start and end of validation; revision pinned
  at `830c5332e12c17a04f41be4f0f3ccd1c5a8dc3eb` (§a).

All six MVP features have an independent, re-executed check with captured raw output and a PASS
verdict. The single medium-severity finding (D2) concerns **documentation accuracy**, not MVP
function, so it does **not** flip the MVP verdict; it is nonetheless listed as a blocking item for
the next iteration in (h).

---

## (h) Blocking items for the next improvement iteration

The MVP verdict is **YES**, but the following are **BLOCKING** for the next iteration and must be
resolved before further feature work is declared "done":

1. **BLOCKING — D2 (config auto-discovery doc/behavior mismatch).** README line 136–137 states
   discovery walks up from **each scan target directory**; the code uses the **current working
   directory** (`linkguard.py:1631` → `load_config(start_dir=os.getcwd(), …)`). Either fix the code
   to discover from the target path, or correct the README to state CWD-relative discovery.
   *Evidence:* §f D2 repro (target-scanned-from-elsewhere stays `[broken]`; explicit `--config`
   and CWD-inside runs apply the ignore).
2. **BLOCKING — D1 (documentation inconsistency).** `PRODUCT_SELECTION.md` §7 references
   `linkguard.toml`, which does not exist anywhere in the shipped code/docs (`linkguard.cfg` +
   `.linkguard.yml` are the supported formats). Reconcile the upstream spec wording with the
   shipped docs.

No functional (code-level) MVP defect was found; the two items above are documentation/spec-accuracy
blockers. Any *later* code change must re-run this validation because the revision pin (`830c533`)
would then change.

---

## (i) What was NOT verified / limitations

- **Single revision only.** Validation is pinned to `830c533`. Any subsequent commit invalidates
  these verdicts — re-run required.
- **Remote-link checking was exercised with a stub/minimal probe.** Live-network behavior was
  verified only against `https://example.com/` (HTTP 200). **Not** verified: real 404/5xx responses,
  redirect-following tolerance (HEAD→GET fallback), per-request timeouts on slow hosts, TLS
  failures, and rate-limiting — no external network to arbitrary hosts was used.
- **D2 was tested with `.linkguard.yml` and `--config`.** The full matrix of every discovery
  location (nested parents, symlinks, multiple candidate files) was not exhaustively enumerated.
- **SARIF/JSON semantic correctness beyond schema validity** (e.g., tooling consumption of the SARIF
  log in real GitHub Code Scanning) was **not** performed; only schema conformance and expected
  rule/field presence were checked.
- **CI integration was NOT executed end-to-end.** `action.yml` presence and shape were inspected;
  the action was not actually run inside GitHub Actions, and no live CI pipeline was triggered.
- **Windows/macOS behavior** (path separators, case sensitivity) was **not** tested — only
  Linux/Python 3.14.4.
- **Performance/large-repo scaling** (thousands of files, exhaustive remote checks) was **not**
  benchmarked.
- **Two test cases are knowingly expected-failures** (angle-bracket target extraction; nested
  parentheses) — they are documented as deliberate and were **not** treated as defects, but the
  underlying behaviors are consequently **not** guaranteed.
- `TEST_REPORT.md` was intentionally **not** used as evidence; where the prior `VALIDATION_EVIDENCE.md`
  and this report overlap, the results agreed, but this report reflects **only** checks re-run by
  this validator.

---

## Artifacts (this validation)

| Artifact | Path |
|---|---|
| Scratch clone (clean, HEAD `830c533`) | `/tmp/lgval/repo` |
| Self-authored fixture | `/tmp/lgval/fix/` |
| YAML-config fixture (D2 repro) | `/tmp/lgval/yfix/` |
| JSON report | `/tmp/lgval/r.json` |
| SARIF report | `/tmp/lgval/r.sarif` |
| Bad-config repro | `/tmp/lgval/bad.cfg` |
| This report | `workspace/product/linkguard/VALIDATION.md` |

*End of VALIDATION.md.*
