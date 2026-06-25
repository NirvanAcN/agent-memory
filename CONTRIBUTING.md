# Contributing

Thanks for your interest in improving **agent-memory**! This document explains how
to propose changes and get them merged.

> 中文版见 [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md)。

## Ground rules

- Be respectful. This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- Keep changes focused. One logical change per merge request.
- Discuss large or breaking changes in an issue before opening a merge request.

## Development setup

The scripts have **no runtime dependencies** and target **Python 3.9+**. Only the
test tooling needs extra packages.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Before you open a merge request

Run the full local check the CI also runs:

```bash
# Unit tests
python3 -m pytest scripts/test_memory.py

# Lint (if installed)
ruff check .

# Smoke test the scaffold end-to-end
python3 scripts/bootstrap_memory.py --project-root /tmp/agent-memory-demo --feature Demo
python3 scripts/validate_memory.py --project-root /tmp/agent-memory-demo
```

All new behavior in `scripts/` must come with a test in `scripts/test_memory.py`.
The bootstrap script must stay **idempotent**: re-running it on an up-to-date tree
produces no changes.

## Changing the memory contract

The file contract is the single source of truth. If you change required files,
headers, or capsule sections, you must update **all** of these together:

1. `references/memory-file-contract.md`
2. `scripts/bootstrap_memory.py` (templates and section lists)
3. `scripts/validate_memory.py` (validation rules)
4. `SKILL.md` and the README files if user-facing behavior changes

Add a matching entry to [`CHANGELOG.md`](CHANGELOG.md) under `Unreleased`.

## Commit and MR conventions

- Use clear, imperative commit subjects (for example `fix: ...`, `docs: ...`, `chore: ...`).
- Reference related issues in the MR description.
- Keep the MR description focused on **why** and **what**, not a diff replay.

## Reporting bugs

Open an issue using the **Bug** template with reproduction steps, expected vs.
actual behavior, and your Python version.
