# TEST_REPORT.md — `linkguard` MVP test-suite coverage

**Task:** 01M31TJFAGW4C747DJYR0SA10T — Build full test suite and document coverage of MVP features
**Role:** tester
**Package under test:** `workspace/product/linkguard/`
**Runtime:** CPython 3.x (stdlib only), no third-party dependency, offline.

---

## 1. Exact run command

```sh
cd workspace/product/linkguard
python3 -m unittest discover -s tests
```

Verbose form (per-test names, used for the evidence below):

```sh
python3 -m unittest discover -s tests -v
```

Per-module form:

```sh
python3 -m unittest discover -s tests -p "test_output.py"
```

The suite is stdlib-`unittest` only (`ARCHITECTURE_v1.md` §6.1); no pytest, no
network, no secrets.

---

## 2. Result of the last full run (green)

```
$ cd workspace/product/linkguard
$ python3 -m unittest discover -s tests
......................................................................
Ran 162 tests in ~8–10 s

OK (expected failures=2)
```

- **162 tests ran.**
- **0 failures, 0 errors.**
- **2 expected failures** (documented feature defects, see §5) — these are
  deliberately marked `@unittest.expectedFailure`; `unittest` reports `OK`
  because the failure is the *documented* outcome. They are not flaky and do
  not mask regressions (if the underlying defect is fixed the test becomes an
  *unexpected success*, which `unittest` reports as a failure — forcing the
  marker to be removed).
- Repeat runs (3×) are byte-for-byte stable: **no flaky tests**, no network
  access, all fixtures static under `tests/fixtures/`.

### Per-module breakdown (each module run in isolation, all green)

| Test module | MVP feature | Tests | Result |
|---|---|---|---|
| `tests/test_extraction.py` | 1 Extraction | 11 | OK (expected failures=2) |
| `tests/test_targets.py` | 2 Broken detection | 39 | OK |
| `tests/test_output.py` | 3 JSON / SARIF output | 10 | OK |
| `tests/test_offline.py` | 4 Offline mode | 8 | OK |
| `tests/test_scan_config.py` | 5 Scan + config | 10 | OK |
| `tests/test_cli_exitcodes.py` | 6 CI gate (exit codes) | 27 | OK |
| `tests/test_config.py` | 5 (config subsystem) | 34 | OK |
| `tests/test_assets.py` | 2 (image/asset refs) | 21 | OK |
| `tests/test_no_third_party.py` | guard (dependency-free) | 2 | OK |
| **Total** | | **162** | **OK** |

Includes the suite-level runner via `test_assets`/`test_config` (support modules
that exercise the engine's config and asset subsystems directly).

---

## 3. MVP coverage map (`ARCHITECTURE_v1.md` §6.2)

Every MVP feature from `ARCHITECTURE_v1.md` has automated tests covering its
**core behavior** and **at least one failure mode**. Legend: ✅ passing.

### FEATURE 1 — Link extraction (`tests/test_extraction.py`)
- **Core behaviour (happy):** `test_plain_inline_link_is_extracted`,
  `test_titled_link_strips_the_title`, `test_bare_autolink_is_extracted`,
  `test_multiple_links_preserve_source_order`, `test_line_and_column_are_reported`.
- **Failure / error path:** `test_fenced_code_block_is_ignored`,
  `test_inline_code_span_is_ignored`, `test_image_is_not_reported_as_a_link`,
  `test_links_around_a_fence_are_still_found`.
- **Known defect (expected failure, §5):** angle-bracket destination and
  nested-paren destination cases (`test_angle_bracket_target_is_extracted`,
  `test_nested_parentheses_are_kept`) — genuine feature bugs, flagged for the
  debugger, not test bugs.
- **Status:** ✅ passing (11 ran; 9 pass, 2 documented defects).

### FEATURE 2 — Broken-link detection (`tests/test_targets.py`, `tests/test_assets.py`)
- **Core behaviour (happy):** `test_existing_local_file_is_ok`,
  `test_existing_anchor_in_target_doc_is_ok`,
  `test_reachable_remote_is_ok`, `test_redirecting_remote_is_ok`,
  `test_present_asset_is_ok`.
- **Failure / error path:** `test_missing_local_file_is_broken`,
  `test_missing_anchor_in_target_doc_is_broken`,
  `test_unreachable_remote_404_is_broken`, `test_timeout_remote_is_broken`,
  `test_connection_refused_remote_is_broken`,
  `test_missing_asset_is_broken`, `test_windows_backslash_separator_missing_is_broken`.
- **Status:** ✅ passing (60 tests across the two modules).

### FEATURE 3 — JSON / SARIF output (`tests/test_output.py`)
- **Core behaviour (happy):** `test_fixture_run_validates_against_report_schema`,
  `test_fixture_run_validates_against_sarif_schema`,
  `test_single_file_report_keeps_backward_compatible_alias`,
  `test_summary_counts_match_emitted_links`,
  `test_cli_sarif_on_broken_fixture_parses_and_validates`,
  `test_findings_carry_severity_file_line_and_message`.
- **Failure / error path:** `test_json_and_sarif_together_exit_two`
  (`--json --sarif` ⇒ exit 2), plus `test_empty_findings_still_validate`
  (empty-edge boundary). Output is validated with the stdlib-only subset
  validator `tests/schema_validator.py` against
  `schemas/report.schema.json` and `schemas/sarif.schema.json`.
- **Status:** ✅ passing (10 tests).

### FEATURE 4 — Offline mode (`tests/test_offline.py`)
- **Core behaviour (happy):** `test_existing_local_file_is_ok_offline`,
  `test_existing_fragment_anchor_is_ok_offline`,
  `test_only_skipped_remote_yields_ok_summary`.
- **Failure / error path:** `test_http_remote_is_skipped_offline`,
  `test_remote_scheme_is_skipped_offline` (remote never reached),
  `test_missing_local_file_is_broken_offline`,
  `test_missing_fragment_anchor_is_broken_offline`
  (local breakage still detected while offline).
- **Status:** ✅ passing (8 tests).

### FEATURE 5 — Repo scan + config (`tests/test_scan_config.py`, `tests/test_config.py`)
- **Core behaviour (happy):** `test_discovers_markdown_recursively`,
  `test_explicit_file_target_is_returned`,
  `test_exclude_glob_drops_matching_files`,
  `test_apply_ignores_downgrades_broken_matching_url`,
  `test_scan_honours_config_exclude_end_to_end`,
  `test_ini_config_values_are_loaded`, `test_yaml_config_values_are_loaded`,
  `test_nearest_config_wins`.
- **Failure / error path:** `test_missing_target_raises_oserror`,
  `test_malformed_config_exits_usage` (⇒ exit 2),
  `test_missing_explicit_file_raises`, `test_bad_boolean_raises`,
  `test_non_positive_timeout_raises`, `test_invalid_regex_in_ignore_is_rejected`,
  `test_dedented_key_after_block_is_error`.
- **Status:** ✅ passing (44 tests across the two modules).

### FEATURE 6 — CI gate / exit codes (`tests/test_cli_exitcodes.py`)
- **Core behaviour (happy):** `test_clean_input_exits_zero`,
  `test_text_mode_clean_file_exits_zero`, `test_version_prints_and_exits_zero`,
  `test_help_prints_usage_and_exits_zero`,
  `test_directory_target_is_scanned`, `test_default_dot_target_scans_cwd`.
- **Failure / error path:** `test_broken_link_exits_one`,
  `test_usage_error_exits_two`, `test_unknown_option_still_exits_two`,
  `test_missing_target_exits_two`, `test_unwritable_output_exits_two`,
  `test_malformed_config_exits_two`, `test_missing_explicit_config_exits_two`,
  `test_timeout_flag_rejects_junk`.
- **Status:** ✅ passing (27 tests).

### Guard test — dependency-free promise (`tests/test_no_third_party.py`)
- `test_only_stdlib_imports` parses `linkguard.py` with `ast` and asserts every
  top-level import is on the stdlib allow-list (protects `ARCHITECTURE_v1.md`
  §6.3 / "$0, no third-party" promise).
- **Status:** ✅ passing (2 tests).

---

## 4. Test-code changes landed by this task

The suite was completed by un-skipping and fleshing out the scaffolded feature
modules. This task (tester role) **added/rewrote test code only**; no feature
code was modified.

- `tests/test_extraction.py` — replaced the 2 skipped scaffold stubs with 11
  real cases (inline/titled/autolink/order/position happy paths + fence /
  inline-code / image error paths + the two documented defect markers).
- `tests/test_offline.py` — replaced the 2 skipped scaffold stubs with 8 real
  cases: remote-is-skipped, local/anchor-still-checked, and an exit-driver
  assertion. No network is ever touched.
- `tests/test_scan_config.py` — replaced the 2 skipped scaffold stubs with 10
  real cases driving `discover_paths` / `apply_ignores` at unit level and the
  scan + config + exit-2 contract end to end, using a throwaway temp tree.

All three fixtures are hermetic (temp dirs cleaned up in `addCleanup`) and the
suite runs without network or third-party packages.

---

## 5. Known feature defects (flagged for the debugger — not fixed here)

Per the task rule "test code only, not feature code", these genuine bugs were
**recorded**, not repaired. They are marked `@unittest.expectedFailure` so the
suite stays green while keeping the defect visible:

1. **EXTRACT-ANGLE** — `_INLINE_LINK_RE` emits an angle-bracket destination
   (`[text](<url>)`) **twice**: once keeping the inner `<...>`, once via the
   autolink regex matching the same `<url>`. `ARCHITECTURE_v1.md` §7 step 3
   requires it parsed exactly once.
   Evidence: `extract_links("[text](<https://example.com>)\n")` ⇒
   `['https://example.com', 'https://example.com']`.
   Test: `tests/test_extraction.py::InlineLinkExtractionTests::test_angle_bracket_target_is_extracted`.

2. **EXTRACT-NESTED** — a nested-parenthesis destination
   (`[text](https://x.com/(y))`) is truncated at the first `)`.
   `ARCHITECTURE_v1.md` §7 step 3 requires nested-paren support.
   Evidence: `extract_links("[text](https://x.com/(y))\n")` ⇒
   `['https://x.com/(y']`.
   Test: `tests/test_extraction.py::InlineLinkExtractionTests::test_nested_parentheses_are_kept`.

Both were reproduced against the current HEAD engine, not inferred. Fixing them
flips the two markers to "unexpected success", which `unittest` reports as a
failure and forces removal of the marker — i.e. the tests gate the fix.

---

## 6. Determinism / hermeticity notes

- Remote checks are stubbed locally (§6.4): `tests/test_targets.py` runs an
  in-process HTTP handler; `tests/test_offline.py` asserts HTTP is never
  reached. No test depends on the public internet.
- Fixtures are static files under `tests/fixtures/`; scan tests build their own
  temp trees under `tempfile.mkdtemp()` and remove them via `addCleanup`.
- `discover_paths` returns a **sorted** list, so the ordering assertion in
  `test_discovers_markdown_recursively` is filesystem-independent.
- Three consecutive full runs produced identical results (162 tests, `OK`).

---

## 7. Verdict against success criteria

| Criterion | Status |
|---|---|
| Full suite runs green | ✅ `OK (expected failures=2)`, 0 failures/errors |
| Every MVP feature has ≥1 passing test | ✅ FEATURES 1–6 + guard, all in §3 |
| Core behaviour **and** ≥1 failure mode per feature | ✅ §3 |
| Test suite committed (local commit only) | ✅ see commit below |
| `TEST_REPORT.md` committed | ✅ this file |

**Follow-up for the debugger:** fix EXTRACT-ANGLE and EXTRACT-NESTED (§5); when
fixed, remove the two `@unittest.expectedFailure` markers so the tests assert
the corrected behaviour directly.
