# Changelog

All notable changes to `linkguard` are documented here. The format is loosely
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
