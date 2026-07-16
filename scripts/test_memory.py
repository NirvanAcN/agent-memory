#!/usr/bin/env python3
"""Tests for bootstrap_memory.py and validate_memory.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bootstrap = _load("bootstrap_memory")
validate = _load("validate_memory")


def run_bootstrap(
    root: Path, features=None, agents=False, memory_dir=None, *, quiet=True
):
    argv = ["bootstrap_memory.py", "--project-root", str(root)]
    for feature in features or []:
        argv += ["--feature", feature]
    if memory_dir:
        argv += ["--memory-dir", memory_dir]
    if agents:
        argv.append("--agents")
    old = sys.argv
    sys.argv = argv
    try:
        output = io.StringIO()
        with contextlib.redirect_stdout(output) if quiet else contextlib.nullcontext():
            return bootstrap.main()
    finally:
        sys.argv = old
        bootstrap.DRY_RUN = False


def read_budget(memory_dir: Path) -> dict:
    return json.loads((memory_dir / "context-budget.json").read_text(encoding="utf-8"))


def write_budget(memory_dir: Path, budget: dict) -> None:
    (memory_dir / "context-budget.json").write_text(
        json.dumps(budget, indent=2) + "\n", encoding="utf-8"
    )


class MemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @property
    def memory_dir(self) -> Path:
        return self.root / ".codex" / "memory"

    def bootstrap_search(self, *, agents: bool = False) -> None:
        self.assertEqual(
            run_bootstrap(self.root, features=["Search"], agents=agents), 0
        )

    def test_slugify_feature(self) -> None:
        self.assertEqual(bootstrap.slugify_feature("User Auth"), "user-auth")
        self.assertEqual(
            bootstrap.slugify_feature("Billing/Invoices"), "billing-invoices"
        )
        with self.assertRaises(ValueError):
            bootstrap.slugify_feature("///")

    def test_refresh_last_updated_replaces_existing(self) -> None:
        text = "# Title\n\nLast Updated: 2000-01-01\n\nBody\n"
        out = bootstrap.refresh_last_updated(text, "2026-06-25")
        self.assertIn("Last Updated: 2026-06-25", out)
        self.assertNotIn("2000-01-01", out)

    def test_refresh_last_updated_inserts_after_title(self) -> None:
        out = bootstrap.refresh_last_updated("# Title\n\nBody\n", "2026-06-25")
        self.assertEqual(out.splitlines()[2], "Last Updated: 2026-06-25")

    def test_bootstrap_creates_valid_tree(self) -> None:
        self.bootstrap_search()
        self.assertTrue((self.memory_dir / "features" / "search.md").is_file())
        self.assertTrue((self.memory_dir / "context-budget.json").is_file())
        self.assertEqual(read_budget(self.memory_dir)["max_capsule_bytes"], 12 * 1024)
        self.assertEqual(validate.validate(self.memory_dir), [])

    def test_bootstrap_is_idempotent(self) -> None:
        self.bootstrap_search()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(
                run_bootstrap(self.root, features=["Search"], quiet=False), 0
            )
        self.assertEqual(output.getvalue().strip(), "No changes.")
        self.assertEqual(validate.validate(self.memory_dir), [])

    def test_dry_run_writes_nothing(self) -> None:
        bootstrap.DRY_RUN = True
        changes: list[str] = []
        path = self.root / "f.md"
        bootstrap.write_changed(path, "hello", changes, "f.md")
        bootstrap.DRY_RUN = False
        self.assertEqual(changes, ["f.md"])
        self.assertFalse(path.exists())

    def test_agents_section_upsert(self) -> None:
        self.bootstrap_search(agents=True)
        agents_file = self.root / "AGENTS.md"
        self.assertTrue(agents_file.is_file())
        text = agents_file.read_text(encoding="utf-8")
        self.assertEqual(text.count(bootstrap.AGENTS_SECTION_TITLE), 1)
        self.assertIn("Do not re-read unchanged files", text)
        self.assertIn("context-budget.json", text)
        run_bootstrap(self.root, features=["Search"], agents=True)
        text = agents_file.read_text(encoding="utf-8")
        self.assertEqual(text.count(bootstrap.AGENTS_SECTION_TITLE), 1)

    def test_validate_detects_missing_section(self) -> None:
        self.bootstrap_search()
        capsule = self.memory_dir / "features" / "search.md"
        text = capsule.read_text(encoding="utf-8").replace(
            "## Regression Checks", "## Removed"
        )
        capsule.write_text(text, encoding="utf-8")
        errors = validate.validate(self.memory_dir)
        self.assertTrue(any("Regression Checks" in error for error in errors))

    def test_validate_missing_directory(self) -> None:
        errors = validate.validate(self.memory_dir)
        self.assertTrue(errors)
        self.assertIn("Missing memory directory", errors[0])

    def test_validate_detects_dangling_registry_pointer(self) -> None:
        self.bootstrap_search()
        (self.memory_dir / "features" / "search.md").unlink()
        errors = validate.validate(self.memory_dir)
        self.assertTrue(
            any("missing capsule" in error and "search.md" in error for error in errors)
        )

    def test_validate_rejects_standard_capsule_over_budget(self) -> None:
        self.bootstrap_search()
        capsule = self.memory_dir / "features" / "search.md"
        capsule.write_text(
            capsule.read_text(encoding="utf-8")
            + "\n".join("- extra" for _ in range(128)),
            encoding="utf-8",
        )
        errors = validate.validate(self.memory_dir)
        self.assertTrue(
            any("lines exceeds context budget" in error for error in errors)
        )

    def test_validate_rejects_capsule_byte_over_budget(self) -> None:
        self.bootstrap_search()
        capsule = self.memory_dir / "features" / "search.md"
        capsule.write_text(
            capsule.read_text(encoding="utf-8")
            + "x" * validate.DEFAULT_CONTEXT_BUDGET["max_capsule_bytes"],
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any("bytes exceeds context budget" in error for error in errors)
        )

    def test_budget_debt_freezes_growth_and_becomes_stale_after_shrink(self) -> None:
        self.bootstrap_search()
        capsule = self.memory_dir / "features" / "search.md"
        original = capsule.read_text(encoding="utf-8")
        oversized = original + "\n".join("- legacy" for _ in range(128))
        capsule.write_text(oversized, encoding="utf-8")
        budget = read_budget(self.memory_dir)
        budget["debt"]["features/search.md"] = {
            "max_lines": len(oversized.splitlines()),
            "max_bytes": len(oversized.encode("utf-8")),
        }
        write_budget(self.memory_dir, budget)
        self.assertEqual(validate.validate(self.memory_dir), [])

        capsule.write_text(oversized + "\n- growth\n", encoding="utf-8")
        errors = validate.validate(self.memory_dir)
        self.assertTrue(any("exceeds context budget" in error for error in errors))

        capsule.write_text(original, encoding="utf-8")
        errors = validate.validate(self.memory_dir)
        self.assertTrue(
            any("below the standard budget; remove it" in error for error in errors)
        )

    def test_validate_rejects_routing_and_agents_budget_growth(self) -> None:
        self.bootstrap_search(agents=True)
        budget = read_budget(self.memory_dir)
        budget["max_routing_bytes"] = 1
        budget["max_agents_bytes"] = 1
        write_budget(self.memory_dir, budget)
        errors = validate.validate(self.memory_dir, self.root / "AGENTS.md")
        self.assertTrue(
            any("index.md + feature-registry.md" in error for error in errors)
        )
        self.assertTrue(any("AGENTS.md" in error for error in errors))

    def test_validate_rejects_unknown_budget_version(self) -> None:
        self.bootstrap_search()
        budget = read_budget(self.memory_dir)
        budget["version"] = 2
        write_budget(self.memory_dir, budget)

        errors = validate.validate(self.memory_dir)

        self.assertTrue(any("unsupported version '2'" in error for error in errors))

    def test_validate_rejects_duplicate_and_unsafe_registry_rows(self) -> None:
        self.bootstrap_search()
        registry = self.memory_dir / "feature-registry.md"
        registry.write_text(
            registry.read_text(encoding="utf-8")
            + "| Search | Duplicate | Active | `features/search.md` | 2026-07-16 |\n"
            + "| Escape | Unsafe | Active | `../AGENTS.md` | 2026-07-16 |\n",
            encoding="utf-8",
        )
        errors = validate.validate(self.memory_dir)
        self.assertTrue(any("duplicate feature 'Search'" in error for error in errors))
        self.assertTrue(
            any(
                "duplicate capsule 'features/search.md'" in error for error in errors
            )
        )
        self.assertTrue(
            any("unsafe capsule path '../AGENTS.md'" in error for error in errors)
        )

    def test_custom_memory_dir(self) -> None:
        self.assertEqual(
            run_bootstrap(
                self.root, features=["Search"], memory_dir=".agent/memory"
            ),
            0,
        )
        memory_dir = self.root / ".agent" / "memory"
        self.assertTrue((memory_dir / "features" / "search.md").is_file())
        self.assertTrue((memory_dir / "context-budget.json").is_file())
        self.assertFalse((self.root / ".codex").exists())
        self.assertEqual(validate.validate(memory_dir), [])


if __name__ == "__main__":
    unittest.main()
