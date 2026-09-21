# linkguard recon — concrete gap list (parent-verified)

Recon of `workspace/product/linkguard/` against active goal "Resume linkguard: MVP
in small increments". Produced from direct file inspection + a real test run
(stdlib unittest; pytest not installable — no pip/network in sandbox).

## Exists (real code, not scaffold)
- linkguard.py: large single-file engine, UNCOMMITTED (+498/-135 vs committed stub).
- tests/: 7 modules, 18 tests; 16 still @unittest.skip("scaffold: implemented with FEATURE N").
- docs/, schemas/(report+sarif), examples/, action.yml, CI, pyproject.toml.

## Concrete gaps (ordered)
1. BLOCKER: test_no_third_party flags `fnmatch` as third-party — it IS stdlib.
   Fix allow-list (add fnmatch, audit urllib.*/configparser/argparse/re/json/os).
   1/18 fails on this. Zero-risk.
2. linkguard.py engine uncommitted — commit once guard test green.
3. 16 skipped tests = the "small increments": un-skip per feature as verified.
4. Verification route: use `python3 -m unittest discover -s tests`; pytest unavailable.

## Increments (one commit each)
- Inc1: fix fnmatch allow-list -> suite green -> commit engine+fix.
- Inc2: un-skip test_targets (feat 2). Inc3: test_output (feat 3).
- Inc4: test_cli_exitcodes/test_scan_config (feat 5). Inc5: test_extraction (feat 1).
- Inc6: CLI smoke + README/usage docs.

## Risk
Phantom completions: 2 prior workers reported done with zero files. Everything above
was verified by reading files and RUNNING tests, not reports. No third-party deps — ever.
