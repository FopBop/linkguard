# Changelog

All notable changes to `linkguard` are documented here. The format is loosely
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Config auto-discovery now walks up from the **scan target** directory as
  documented, instead of always from the current working directory. Previously,
  running `linkguard docs/` from an unrelated cwd silently ignored
  `docs/linkguard.cfg`, so target-local `ignore`/`exclude` rules were not
  applied (VALIDATION.md finding **D2**). Discovery now honours the first
  target whose walk-up finds a config and falls through to the next target
  otherwise; passing no target still discovers from the cwd.

### Added
- v1 scaffold: repository tree, package manifest (`pyproject.toml`, zero
  dependencies), MIT `LICENSE`, `.gitignore`, `.editorconfig`.
- Entry point stub `linkguard.py` with documented public interfaces
  (constants, `Link`, `extract_links`, `classify`, `render_*`,
  `discover_paths`, `load_config`, `apply_ignores`, `run`, `main`).
- Importable facade package `linkguard/` re-exporting the stable API.
- Placeholder `README.md`, sample `linkguard.cfg`, `action.yml`, vendored JSON
  schemas, and empty documented test modules.

## [0.1.0] - 2026-09-20

### Added
- Initial scaffold commit. Prototype provenance:
  `workspace/mdlinkcheck` (`mdlinkcheck.py`, commit `0353d9b`).

[Unreleased]: https://github.com/OWNER/linkguard/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/linkguard/releases/tag/v0.1.0
