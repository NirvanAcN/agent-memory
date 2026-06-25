#!/usr/bin/env python3
"""Tests for bootstrap_memory.py and validate_memory.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bootstrap = _load("bootstrap_memory")
validate = _load("validate_memory")


def run_bootstrap(root: Path, features=None, agents=False):
    argv = ["bootstrap_memory.py", "--project-root", str(root)]
    for feature in features or []:
        argv += ["--feature", feature]
    if agents:
        argv.append("--agents")
    old = sys.argv
    sys.argv = argv
    try:
        return bootstrap.main()
    finally:
        sys.argv = old
        bootstrap.DRY_RUN = False


def test_slugify_feature():
    assert bootstrap.slugify_feature("User Auth") == "user-auth"
    assert bootstrap.slugify_feature("Billing/Invoices") == "billing-invoices"
    with pytest.raises(ValueError):
        bootstrap.slugify_feature("///")


def test_refresh_last_updated_replaces_existing():
    text = "# Title\n\nLast Updated: 2000-01-01\n\nBody\n"
    out = bootstrap.refresh_last_updated(text, "2026-06-25")
    assert "Last Updated: 2026-06-25" in out
    assert "2000-01-01" not in out


def test_refresh_last_updated_inserts_after_title():
    out = bootstrap.refresh_last_updated("# Title\n\nBody\n", "2026-06-25")
    assert out.splitlines()[2] == "Last Updated: 2026-06-25"


def test_bootstrap_creates_valid_tree(tmp_path):
    assert run_bootstrap(tmp_path, features=["Search"]) == 0
    memory_dir = tmp_path / ".codex" / "memory"
    assert (memory_dir / "features" / "search.md").is_file()
    assert validate.validate(memory_dir) == []


def test_bootstrap_is_idempotent(tmp_path):
    run_bootstrap(tmp_path, features=["Search"])
    bootstrap.DRY_RUN = True
    changes: list[str] = []
    # Re-running on an up-to-date tree (same day) should produce no writes.
    bootstrap.DRY_RUN = False
    second = run_bootstrap(tmp_path, features=["Search"])
    assert second == 0
    assert validate.validate(tmp_path / ".codex" / "memory") == []


def test_dry_run_writes_nothing(tmp_path):
    bootstrap.DRY_RUN = True
    changes: list[str] = []
    bootstrap.write_changed(tmp_path / "f.md", "hello", changes, "f.md")
    bootstrap.DRY_RUN = False
    assert changes == ["f.md"]
    assert not (tmp_path / "f.md").exists()


def test_agents_section_upsert(tmp_path):
    run_bootstrap(tmp_path, features=["Search"], agents=True)
    agents_file = tmp_path / "AGENTS.md"
    assert agents_file.is_file()
    text = agents_file.read_text(encoding="utf-8")
    assert text.count(bootstrap.AGENTS_SECTION_TITLE) == 1
    # Second run must not duplicate the section.
    run_bootstrap(tmp_path, features=["Search"], agents=True)
    assert agents_file.read_text(encoding="utf-8").count(bootstrap.AGENTS_SECTION_TITLE) == 1


def test_validate_detects_missing_section(tmp_path):
    run_bootstrap(tmp_path, features=["Search"])
    capsule = tmp_path / ".codex" / "memory" / "features" / "search.md"
    text = capsule.read_text(encoding="utf-8").replace("## Regression Checks", "## Removed")
    capsule.write_text(text, encoding="utf-8")
    errors = validate.validate(tmp_path / ".codex" / "memory")
    assert any("Regression Checks" in e for e in errors)


def test_validate_missing_directory(tmp_path):
    errors = validate.validate(tmp_path / ".codex" / "memory")
    assert errors and "Missing memory directory" in errors[0]
