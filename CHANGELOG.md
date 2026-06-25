# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `--memory-dir` and `--agents-file` flags so the skill works with any agent, not only Codex (defaults stay `.codex/memory` and `AGENTS.md`).
- `scripts/validate_memory.py`: validates an existing memory tree against the file contract, including detecting registry rows that point at missing capsule files.
- `scripts/test_memory.py`: pytest suite covering bootstrap helpers, idempotency, dry-run, and the validator.
- `--dry-run` flag for `scripts/bootstrap_memory.py`.
- Chinese README (`README.zh-CN.md`) and contributing guide (`CONTRIBUTING.zh-CN.md`).
- Open-source infrastructure: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `pyproject.toml`, GitLab CI, and issue/MR templates.

### Changed

- Rewrote `README.md` with a polished layout and usage tables.

### Fixed

- Removed a hardcoded private absolute path from `README.md`.
- Removed dead code in the feature-registry write path of `bootstrap_memory.py`.
