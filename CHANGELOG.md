# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Configurable guide, routing, and capsule budgets in `context-budget.json`, with
  exact no-growth debt for legacy oversized capsules.
- Registry completeness checks for top-level and nested feature capsules.
- Evidence/freshness metadata guidance and capsule splitting rules.
- Verification-before-write anti-feedback, fail-open/privacy, and compare-before-write safeguards.
- Versioned managed policy blocks, stable rule IDs, and explicit `--upgrade`
  migration that preserves project-owned index and agents guidance.
- `--memory-dir` and `--agents-file` flags so the skill works with any agent, not only Codex (defaults stay `.codex/memory` and `AGENTS.md`).
- `scripts/validate_memory.py`: validates an existing memory tree against the file contract, including detecting registry rows that point at missing capsule files.
- `scripts/test_memory.py`: standard-library unittest suite covering bootstrap helpers, idempotency, dry-run, and the validator.
- `--dry-run` flag for `scripts/bootstrap_memory.py`.
- Chinese README (`README.zh-CN.md`) and contributing guide (`CONTRIBUTING.zh-CN.md`).
- Open-source infrastructure: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `pyproject.toml`, GitLab CI, and issue/MR templates.

### Changed

- Lowered the supported Python floor from 3.9 to 3.7 and added Python 3.7/3.8
  jobs to the compatibility matrix.
- Bootstrap now validates project-local paths and all feature inputs before
  writing, preserves custom registry routes, and remains byte-stable across
  unchanged reruns on later dates.
- Validation now checks exact Markdown structure outside code fences, real ISO
  calendar dates, safe paths, policy versions/rule IDs, and bounded report output.
- Rewrote `README.md` with a polished layout and usage tables.

### Fixed

- Removed a hardcoded private absolute path from `README.md`.
- Removed dead code in the feature-registry write path of `bootstrap_memory.py`.
