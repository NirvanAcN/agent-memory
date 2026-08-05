#!/usr/bin/env python3
"""Tests for bootstrap_memory.py and validate_memory.py."""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
    root: Path,
    features=None,
    agents=False,
    memory_dir=None,
    upgrade=False,
    *,
    quiet=True,
):
    argv = ["bootstrap_memory.py", "--project-root", str(root)]
    for feature in features or []:
        argv += ["--feature", feature]
    if memory_dir:
        argv += ["--memory-dir", memory_dir]
    if agents:
        argv.append("--agents")
    if upgrade:
        argv.append("--upgrade")
    old = sys.argv
    sys.argv = argv
    try:
        output = io.StringIO()
        with contextlib.redirect_stdout(output) if quiet else contextlib.nullcontext():
            return bootstrap.main()
    finally:
        sys.argv = old
        bootstrap.DRY_RUN = False


def run_bootstrap_cli(
    root: Path,
    features=None,
    agents=False,
    memory_dir=None,
    agents_file=None,
    upgrade=False,
    dry_run=False,
):
    argv = [
        sys.executable,
        str(SCRIPTS_DIR / "bootstrap_memory.py"),
        "--project-root",
        str(root),
    ]
    for feature in features or []:
        argv += ["--feature", feature]
    if memory_dir is not None:
        argv += ["--memory-dir", memory_dir]
    if agents:
        argv.append("--agents")
    if agents_file is not None:
        argv += ["--agents-file", agents_file]
    if upgrade:
        argv.append("--upgrade")
    if dry_run:
        argv.append("--dry-run")
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def run_validate_cli(root: Path, memory_dir=None, agents_file=None):
    argv = [
        sys.executable,
        str(SCRIPTS_DIR / "validate_memory.py"),
        "--project-root",
        str(root),
    ]
    if memory_dir is not None:
        argv += ["--memory-dir", memory_dir]
    if agents_file is not None:
        argv += ["--agents-file", agents_file]
    return subprocess.run(argv, capture_output=True, text=True, check=False)


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

    def make_policy_legacy(self, *, custom_content: bool = False) -> None:
        for path in (self.memory_dir / "index.md", self.root / "AGENTS.md"):
            text = path.read_text(encoding="utf-8")
            text = "\n".join(
                line
                for line in text.splitlines()
                if not line.startswith("<!-- agent-memory:policy-")
            ).rstrip() + "\n"
            if custom_content:
                custom = (
                    "- Preserve this project-specific index policy."
                    if path.name == "index.md"
                    else "Preserve this project-specific agents policy."
                )
                text = text.rstrip() + f"\n\n{custom}\n"
                if path.name == "AGENTS.md":
                    text += "\n## Existing Project Section\n\nKeep this section.\n"
            path.write_text(text, encoding="utf-8")

    def test_scripts_parse_with_python_37_grammar(self) -> None:
        parser_options = (
            {"feature_version": (3, 7)} if sys.version_info >= (3, 8) else {}
        )
        for script in sorted(SCRIPTS_DIR.glob("*.py")):
            with self.subTest(script=script.name):
                ast.parse(
                    script.read_text(encoding="utf-8"),
                    filename=str(script),
                    **parser_options,
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
        index = (self.memory_dir / "index.md").read_text(encoding="utf-8")
        self.assertIn("reachable through one unique registry row", index)
        self.assertIn("use `--report` during audits", index)
        self.assertIn(
            bootstrap.policy_start_marker(bootstrap.INDEX_READ_POLICY_ID), index
        )
        self.assertIn(
            bootstrap.policy_start_marker(bootstrap.INDEX_WRITE_POLICY_ID), index
        )
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

    def test_generated_workflow_contains_write_safety_rules(self) -> None:
        self.bootstrap_search(agents=True)
        generated = {
            "index": (self.memory_dir / "index.md").read_text(encoding="utf-8"),
            "agents": (self.root / "AGENTS.md").read_text(encoding="utf-8"),
        }
        required_phrases = (
            "context, not evidence",
            "must not block the primary task",
            "Fail open for task execution but fail closed for memory-derived claims",
            "Never store secrets, tokens, credentials, raw chat transcripts",
            "Immediately before write-back, narrowly re-read only each memory file",
            "merge with its current content instead of overwriting it",
            "After writing, re-read every touched memory file",
            "Do not hand-edit managed policy markers or rule IDs",
        )
        for name, text in generated.items():
            for phrase in required_phrases:
                with self.subTest(file=name, phrase=phrase):
                    self.assertIn(phrase, text)

        capsule = (self.memory_dir / "features" / "search.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Memory recall is context, not evidence", capsule)

    def test_legacy_policy_requires_explicit_upgrade_before_writes(self) -> None:
        self.bootstrap_search(agents=True)
        self.make_policy_legacy(custom_content=True)
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

        result = run_bootstrap_cli(
            self.root, features=["Search", "Billing"], agents=True
        )

        diagnostics = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, diagnostics)
        self.assertIn("--upgrade --dry-run", diagnostics)
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_upgrade_migrates_legacy_policy_and_preserves_custom_content(
        self,
    ) -> None:
        with mock.patch.object(bootstrap, "today", return_value="2026-08-01"):
            self.bootstrap_search(agents=True)
        self.make_policy_legacy(custom_content=True)

        with mock.patch.object(bootstrap, "today", return_value="2026-08-02"):
            self.assertEqual(
                run_bootstrap(self.root, features=["Search"], upgrade=True), 0
            )

        index = (self.memory_dir / "index.md").read_text(encoding="utf-8")
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Preserve this project-specific index policy.", index)
        self.assertIn("Preserve this project-specific agents policy.", agents)
        self.assertEqual(index.count("1. Read this file first."), 1)
        self.assertEqual(
            agents.count("Before any task: read `.codex/memory/index.md` first"), 1
        )
        self.assertIn(
            bootstrap.policy_end_marker(bootstrap.INDEX_READ_POLICY_ID)
            + "\n\n## Memory Files",
            index,
        )
        self.assertIn(
            "Preserve this project-specific agents policy.\n\n"
            "## Existing Project Section",
            agents,
        )
        self.assertIn("Keep this section.", agents)
        self.assertEqual(
            index.count(bootstrap.policy_start_marker(bootstrap.INDEX_READ_POLICY_ID)),
            1,
        )
        self.assertEqual(
            agents.count(bootstrap.policy_start_marker(bootstrap.AGENTS_POLICY_ID)),
            1,
        )
        self.assertIn("Last Updated: 2026-08-02", index)
        self.assertEqual(
            validate.validate(self.memory_dir, self.root / "AGENTS.md"), []
        )

        output = io.StringIO()
        with mock.patch.object(bootstrap, "today", return_value="2026-08-03"):
            with contextlib.redirect_stdout(output):
                self.assertEqual(
                    run_bootstrap(
                        self.root,
                        features=["Search"],
                        upgrade=True,
                        quiet=False,
                    ),
                    0,
                )
        self.assertEqual(output.getvalue().strip(), "No changes.")

    def test_upgrade_dry_run_preserves_legacy_tree(self) -> None:
        self.bootstrap_search(agents=True)
        self.make_policy_legacy(custom_content=True)
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

        result = run_bootstrap_cli(self.root, upgrade=True, dry_run=True)

        diagnostics = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, diagnostics)
        self.assertIn("Would update:", result.stdout)
        self.assertIn("index.md", result.stdout)
        self.assertIn("AGENTS.md", result.stdout)
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_upgrade_refuses_newer_policy_version_without_writes(self) -> None:
        self.bootstrap_search(agents=True)
        index = self.memory_dir / "index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                "id=index-read-order version=1",
                "id=index-read-order version=99",
                1,
            ),
            encoding="utf-8",
        )
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

        result = run_bootstrap_cli(self.root, upgrade=True)

        diagnostics = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, diagnostics)
        self.assertIn("will not downgrade", diagnostics)
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_validate_rejects_missing_policy_rule_id(self) -> None:
        self.bootstrap_search(agents=True)
        index = self.memory_dir / "index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                " verification-before-write", "", 1
            ),
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir, self.root / "AGENTS.md")

        self.assertTrue(
            any(
                "index-write-back" in error
                and "verification-before-write" in error
                for error in errors
            )
        )

    def test_validate_rejects_policy_version_mismatch(self) -> None:
        self.bootstrap_search()
        index = self.memory_dir / "index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                "id=index-read-order version=1",
                "id=index-read-order version=2",
                1,
            ),
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any(
                "index-read-order" in error
                and "uses version 2" in error
                and "expected 1" in error
                for error in errors
            )
        )

    def test_unmanaged_agents_section_requires_explicit_upgrade(self) -> None:
        self.bootstrap_search(agents=True)
        agents_file = self.root / "AGENTS.md"
        agents_file.write_text(
            "\n".join(
                line
                for line in agents_file.read_text(encoding="utf-8").splitlines()
                if not line.startswith("<!-- agent-memory:policy-")
            ).rstrip()
            + "\n",
            encoding="utf-8",
        )
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }

        result = run_bootstrap_cli(self.root, features=["Billing"], agents=True)

        diagnostics = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, diagnostics)
        self.assertIn("unmanaged legacy policy", diagnostics)
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_unchanged_cross_date_rerun_preserves_all_freshness_values(self) -> None:
        with mock.patch.object(bootstrap, "today", return_value="2026-07-01"):
            self.assertEqual(
                run_bootstrap(self.root, features=["Search"], agents=True), 0
            )

        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }
        output = io.StringIO()
        with mock.patch.object(bootstrap, "today", return_value="2026-07-02"):
            with contextlib.redirect_stdout(output):
                self.assertEqual(
                    run_bootstrap(
                        self.root,
                        features=["Search"],
                        agents=True,
                        quiet=False,
                    ),
                    0,
                )

        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        }
        self.assertEqual(output.getvalue().strip(), "No changes.")
        self.assertEqual(after, before)
        for path in self.memory_dir.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Last Updated: 2026-07-01", text, str(path))
            self.assertNotIn("Last Updated: 2026-07-02", text, str(path))
        self.assertEqual(read_budget(self.memory_dir)["last_updated"], "2026-07-01")

    def test_absolute_and_outside_paths_are_rejected_before_any_write(self) -> None:
        for kind in (
            "absolute-memory",
            "outside-memory",
            "absolute-agents",
            "outside-agents",
        ):
            with self.subTest(kind=kind):
                container = self.root / kind
                project = container / "project"
                project.mkdir(parents=True)
                outside_path = None
                options = {}

                if kind == "absolute-memory":
                    options["memory_dir"] = str(project / "memory")
                elif kind == "outside-memory":
                    options["memory_dir"] = "../outside-memory"
                    outside_path = container / "outside-memory"
                elif kind == "absolute-agents":
                    options["agents"] = True
                    options["agents_file"] = str(project / "INSTRUCTIONS.md")
                else:
                    options["agents"] = True
                    options["agents_file"] = "../outside-AGENTS.md"
                    outside_path = container / "outside-AGENTS.md"

                result = run_bootstrap_cli(project, **options)
                diagnostics = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, diagnostics)
                self.assertEqual(list(project.iterdir()), [], diagnostics)
                if outside_path is not None:
                    self.assertFalse(outside_path.exists(), diagnostics)

    def test_invalid_feature_name_is_rejected_before_any_write(self) -> None:
        project = self.root / "invalid-feature"
        project.mkdir()

        result = run_bootstrap_cli(project, features=["Search", "///"])

        diagnostics = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, diagnostics)
        self.assertEqual(list(project.iterdir()), [], diagnostics)

    def test_markdown_breaking_feature_names_are_rejected_before_write(self) -> None:
        for index, feature in enumerate(("Search | Archive", "Search\nArchive")):
            with self.subTest(feature=feature):
                project = self.root / f"invalid-markdown-feature-{index}"
                project.mkdir()

                result = run_bootstrap_cli(project, features=[feature])

                diagnostics = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, diagnostics)
                self.assertEqual(list(project.iterdir()), [], diagnostics)

    def test_symlink_escape_is_rejected_before_any_write(self) -> None:
        container = self.root / "symlink-escape"
        project = container / "project"
        outside = container / "outside"
        project.mkdir(parents=True)
        outside.mkdir()
        link = project / "linked"
        link.symlink_to(outside, target_is_directory=True)

        result = run_bootstrap_cli(project, memory_dir="linked/memory")

        diagnostics = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, diagnostics)
        self.assertEqual(list(project.iterdir()), [link], diagnostics)
        self.assertEqual(list(outside.iterdir()), [], diagnostics)

    def test_agents_file_and_memory_directory_must_not_overlap(self) -> None:
        for index, agents_file in enumerate(
            (".codex", ".codex/memory/agent-guide.md")
        ):
            with self.subTest(agents_file=agents_file):
                project = self.root / f"overlapping-agents-path-{index}"
                project.mkdir()

                result = run_bootstrap_cli(
                    project, agents=True, agents_file=agents_file
                )

                diagnostics = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, diagnostics)
                self.assertEqual(list(project.iterdir()), [], diagnostics)

    def test_bootstrap_ignores_agents_path_when_not_managing_it(self) -> None:
        agents_directory = self.root / "AGENTS.md"
        agents_directory.mkdir()

        result = run_bootstrap_cli(self.root, features=["Search"])

        diagnostics = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, diagnostics)
        self.assertTrue((self.memory_dir / "features" / "search.md").is_file())
        self.assertTrue(agents_directory.is_dir())

    def test_markdown_breaking_output_paths_are_rejected_before_write(self) -> None:
        for index, options in enumerate(
            (
                {"memory_dir": ".agent/context`\n\n## Injected"},
                {
                    "agents": True,
                    "agents_file": "AGENTS`\n\n## Injected.md",
                },
            )
        ):
            with self.subTest(options=options):
                project = self.root / f"markdown-path-injection-{index}"
                project.mkdir()

                result = run_bootstrap_cli(project, **options)

                diagnostics = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, diagnostics)
                self.assertEqual(list(project.iterdir()), [], diagnostics)

    def test_normalized_feature_slug_collision_is_rejected_before_any_write(
        self,
    ) -> None:
        project = self.root / "feature-collision"
        project.mkdir()

        result = run_bootstrap_cli(project, features=["User Auth", "user-auth"])

        diagnostics = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, diagnostics)
        self.assertEqual(list(project.iterdir()), [], diagnostics)

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
        self.assertIn("reachable through one unique registry row", text)
        self.assertIn("both ceilings must be lowered", text)
        self.assertIn(
            bootstrap.policy_start_marker(bootstrap.AGENTS_POLICY_ID), text
        )
        agents_file.write_text(
            text.rstrip() + "\n\nKeep this project-specific workflow note.\n",
            encoding="utf-8",
        )
        run_bootstrap(self.root, features=["Search"], agents=True)
        text = agents_file.read_text(encoding="utf-8")
        self.assertEqual(text.count(bootstrap.AGENTS_SECTION_TITLE), 1)
        self.assertIn("Keep this project-specific workflow note.", text)

    def test_custom_memory_dir_is_rendered_in_agents_workflow(self) -> None:
        self.assertEqual(
            run_bootstrap(
                self.root,
                features=["Search"],
                agents=True,
                memory_dir=".agent/memory",
            ),
            0,
        )

        agents_text = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("`.agent/memory/index.md`", agents_text)
        self.assertIn("`.agent/memory/feature-registry.md`", agents_text)
        self.assertIn("`.agent/memory/features/<Feature>.md`", agents_text)
        self.assertNotIn(".codex/memory", agents_text)
        self.assertFalse((self.root / ".codex").exists())

    def test_registry_prose_path_does_not_suppress_feature_row(self) -> None:
        with mock.patch.object(bootstrap, "today", return_value="2026-07-01"):
            self.assertEqual(run_bootstrap(self.root), 0)
        registry = self.memory_dir / "feature-registry.md"
        registry.write_text(
            registry.read_text(encoding="utf-8").rstrip()
            + "\n\nPlanned capsule path: `features/search.md`.\n",
            encoding="utf-8",
        )

        with mock.patch.object(bootstrap, "today", return_value="2026-07-01"):
            self.assertEqual(run_bootstrap(self.root, features=["Search"]), 0)

        rows = [
            line
            for line in registry.read_text(encoding="utf-8").splitlines()
            if line.startswith("| Search |")
        ]
        self.assertEqual(
            rows,
            ["| Search | Unknown | Active | `features/search.md` | 2026-07-01 |"],
        )
        self.assertEqual(validate.validate(self.memory_dir), [])

    def test_existing_feature_keeps_its_registered_custom_capsule(self) -> None:
        self.bootstrap_search()
        default_capsule = self.memory_dir / "features" / "search.md"
        custom_capsule = self.memory_dir / "features" / "search" / "routing.md"
        custom_capsule.parent.mkdir()
        custom_capsule.write_text(
            default_capsule.read_text(encoding="utf-8").replace(
                "## Dependencies", "## Broken Dependencies", 1
            ),
            encoding="utf-8",
        )
        default_capsule.unlink()
        registry = self.memory_dir / "feature-registry.md"
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                "features/search.md", "features/search/routing.md", 1
            ).replace(bootstrap.FEATURE_REGISTRY_DIVIDER + "\n", "", 1),
            encoding="utf-8",
        )

        self.assertEqual(run_bootstrap(self.root, features=["Search"]), 0)

        registry_text = registry.read_text(encoding="utf-8")
        self.assertEqual(registry_text.count("| Search |"), 1)
        self.assertIn("`features/search/routing.md`", registry_text)
        self.assertFalse(default_capsule.exists())
        self.assertIn(
            "## Dependencies", custom_capsule.read_text(encoding="utf-8").splitlines()
        )
        self.assertEqual(validate.validate(self.memory_dir), [])

    def test_requested_feature_rejects_existing_default_path_owner(self) -> None:
        project = self.root / "registry-path-owner"
        project.mkdir()
        self.assertEqual(run_bootstrap(project, features=["Legacy"]), 0)
        memory_dir = project / ".codex" / "memory"
        registry = memory_dir / "feature-registry.md"
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                "features/legacy.md", "features/search.md", 1
            ),
            encoding="utf-8",
        )
        (memory_dir / "features" / "legacy.md").rename(
            memory_dir / "features" / "search.md"
        )
        before = {
            path.relative_to(project).as_posix(): path.read_bytes()
            for path in sorted(project.rglob("*"))
            if path.is_file()
        }

        result = run_bootstrap_cli(project, features=["Search"])

        diagnostics = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, diagnostics)
        after = {
            path.relative_to(project).as_posix(): path.read_bytes()
            for path in sorted(project.rglob("*"))
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_bootstrap_repairs_damaged_capsule_template(self) -> None:
        self.assertEqual(run_bootstrap(self.root), 0)
        template = self.memory_dir / "features" / "_template.md"
        damaged = template.read_text(encoding="utf-8").replace(
            "## Dependencies", "## Broken Dependencies", 1
        )
        damaged += "\nCustom template guidance must remain.\n"
        template.write_text(damaged, encoding="utf-8")

        self.assertEqual(run_bootstrap(self.root), 0)

        repaired = template.read_text(encoding="utf-8")
        self.assertIn("## Dependencies", repaired.splitlines())
        self.assertIn("Custom template guidance must remain.", repaired)
        self.assertEqual(validate.validate(self.memory_dir), [])

    def test_bootstrap_repairs_heading_hidden_in_code_fence(self) -> None:
        self.assertEqual(run_bootstrap(self.root), 0)
        template = self.memory_dir / "features" / "_template.md"
        template.write_text(
            template.read_text(encoding="utf-8").replace(
                "## Dependencies",
                "## Broken Dependencies\n\n```markdown\n```python\n## Dependencies\n```",
                1,
            ),
            encoding="utf-8",
        )

        self.assertEqual(run_bootstrap(self.root), 0)

        structural_lines = {
            line
            for _line_number, line in validate.markdown_structure_lines(
                template.read_text(encoding="utf-8")
            )
        }
        self.assertIn("## Dependencies", structural_lines)
        self.assertEqual(validate.validate(self.memory_dir), [])

    def test_bootstrap_repairs_malformed_and_duplicate_last_updated(self) -> None:
        self.assertEqual(run_bootstrap(self.root), 0)
        index = self.memory_dir / "index.md"
        text = index.read_text(encoding="utf-8")
        current_stamp = next(
            line for line in text.splitlines() if line.startswith("Last Updated:")
        )
        index.write_text(
            text.replace(current_stamp, "Last Updated: not-a-date", 1)
            + "\nLast Updated: 2026-07-01\n",
            encoding="utf-8",
        )

        with mock.patch.object(bootstrap, "today", return_value="2026-07-02"):
            self.assertEqual(run_bootstrap(self.root), 0)

        markers = [
            line
            for _line_number, line in validate.markdown_structure_lines(
                index.read_text(encoding="utf-8")
            )
            if line.startswith("Last Updated:")
        ]
        self.assertEqual(markers, ["Last Updated: 2026-07-02"])
        self.assertEqual(validate.validate(self.memory_dir), [])

    def test_validate_detects_missing_section(self) -> None:
        self.bootstrap_search()
        capsule = self.memory_dir / "features" / "search.md"
        text = capsule.read_text(encoding="utf-8").replace(
            "## Regression Checks", "## Removed"
        )
        capsule.write_text(text, encoding="utf-8")
        errors = validate.validate(self.memory_dir)
        self.assertTrue(any("Regression Checks" in error for error in errors))

    def test_validate_rejects_suffixed_required_heading(self) -> None:
        self.bootstrap_search()
        capsule = self.memory_dir / "features" / "search.md"
        capsule.write_text(
            capsule.read_text(encoding="utf-8").replace(
                "## Dependencies", "## Dependencies Legacy", 1
            ),
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any(
                "features/search.md" in error
                and "missing required section '## Dependencies'" in error
                for error in errors
            )
        )

    def test_validate_ignores_required_heading_inside_code_fence(self) -> None:
        self.bootstrap_search()
        capsule = self.memory_dir / "features" / "search.md"
        capsule.write_text(
            capsule.read_text(encoding="utf-8").replace(
                "## Dependencies",
                "## Broken Dependencies\n\n```markdown\n```python\n## Dependencies\n```",
                1,
            ),
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any(
                "features/search.md" in error
                and "missing required section '## Dependencies'" in error
                for error in errors
            )
        )

    def test_validate_rejects_table_header_embedded_in_prose(self) -> None:
        self.bootstrap_search()
        registry = self.memory_dir / "feature-registry.md"
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                validate.FEATURE_REGISTRY_HEADER,
                f"Documented header: {validate.FEATURE_REGISTRY_HEADER}",
                1,
            ),
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(any("missing required table header" in error for error in errors))

    def test_validate_rejects_missing_registry_table_divider(self) -> None:
        self.bootstrap_search()
        registry = self.memory_dir / "feature-registry.md"
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                validate.FEATURE_REGISTRY_DIVIDER + "\n", "", 1
            ),
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(any("table divider" in error for error in errors))

    def test_registry_row_outside_table_does_not_register_capsule(self) -> None:
        self.assertEqual(run_bootstrap(self.root), 0)
        capsule = self.memory_dir / "features" / "search.md"
        capsule.write_text(
            (self.memory_dir / "features" / "_template.md").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        registry = self.memory_dir / "feature-registry.md"
        registry.write_text(
            registry.read_text(encoding="utf-8")
            + "\nThis prose ends the registry table.\n\n"
            + "| Search | Unknown | Active | `features/search.md` | 2026-07-26 |\n",
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any("features/search.md" in error and "not registered" in error for error in errors)
        )

    def test_validate_rejects_duplicate_last_updated_fields(self) -> None:
        self.bootstrap_search()
        capsule = self.memory_dir / "features" / "search.md"
        capsule.write_text(
            capsule.read_text(encoding="utf-8")
            + "\nLast Updated: 2026-07-02\n",
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any(
                "features/search.md" in error and "duplicate 'Last Updated'" in error
                for error in errors
            )
        )

    def test_validate_rejects_impossible_markdown_date(self) -> None:
        self.bootstrap_search()
        capsule = self.memory_dir / "features" / "search.md"
        text = capsule.read_text(encoding="utf-8")
        current_stamp = next(
            line for line in text.splitlines() if line.startswith("Last Updated:")
        )
        capsule.write_text(
            text.replace(current_stamp, "Last Updated: 2026-99-99", 1),
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any(
                "features/search.md" in error and "Last Updated" in error
                for error in errors
            )
        )

    def test_validate_rejects_impossible_budget_date(self) -> None:
        self.bootstrap_search()
        budget = read_budget(self.memory_dir)
        budget["last_updated"] = "2026-99-99"
        write_budget(self.memory_dir, budget)

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any(
                "context-budget.json" in error and "last_updated" in error
                for error in errors
            )
        )

    def test_validate_rejects_impossible_registry_verification_date(self) -> None:
        self.bootstrap_search()
        registry = self.memory_dir / "feature-registry.md"
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                f"| {bootstrap.today()} |", "| 2026-99-99 |", 1
            ),
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any("Last Verified" in error and "2026-99-99" in error for error in errors)
        )

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

    def test_validate_rejects_unregistered_capsule(self) -> None:
        self.bootstrap_search()
        orphan = self.memory_dir / "features" / "orphan.md"
        orphan.write_text(
            (self.memory_dir / "features" / "search.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any("orphan.md" in error and "not registered" in error for error in errors)
        )

    def test_validate_checks_nested_registered_capsule_structure(self) -> None:
        self.bootstrap_search()
        source = self.memory_dir / "features" / "search.md"
        nested = self.memory_dir / "features" / "search" / "routing.md"
        nested.parent.mkdir()
        nested.write_text(
            source.read_text(encoding="utf-8").replace(
                "## Dependencies", "## Removed Dependencies"
            ),
            encoding="utf-8",
        )
        source.unlink()
        registry = self.memory_dir / "feature-registry.md"
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                "features/search.md", "features/search/routing.md"
            ),
            encoding="utf-8",
        )

        errors = validate.validate(self.memory_dir)

        self.assertTrue(
            any(
                "features/search/routing.md" in error and "Dependencies" in error
                for error in errors
            )
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

        budget["debt"]["features/search.md"] = {
            "max_lines": len(oversized.splitlines()) + 1,
            "max_bytes": len(oversized.encode("utf-8")) + 1,
        }
        write_budget(self.memory_dir, budget)
        errors = validate.validate(self.memory_dir)
        self.assertTrue(any("current measured size" in error for error in errors))

        budget["debt"]["features/search.md"] = {
            "max_lines": len(oversized.splitlines()),
            "max_bytes": len(oversized.encode("utf-8")),
        }
        write_budget(self.memory_dir, budget)

        capsule.write_text(oversized + "\n- growth\n", encoding="utf-8")
        errors = validate.validate(self.memory_dir)
        self.assertTrue(any("exceeds context budget" in error for error in errors))

        smaller_oversized = oversized.rsplit("\n", 1)[0]
        capsule.write_text(smaller_oversized, encoding="utf-8")
        errors = validate.validate(self.memory_dir)
        self.assertTrue(any("lower it to max_lines" in error for error in errors))

        budget["debt"]["features/search.md"] = {
            "max_lines": len(smaller_oversized.splitlines()),
            "max_bytes": len(smaller_oversized.encode("utf-8")),
        }
        write_budget(self.memory_dir, budget)
        self.assertEqual(validate.validate(self.memory_dir), [])

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
            + "| Escape | Unsafe | Active | `../AGENTS.md` | 2026-07-16 |\n"
            + "| Outside | Unsafe | Active | `index.md` | 2026-07-16 |\n"
            + "| Alias | Unsafe | Active | `features/./search.md` | 2026-07-16 |\n",
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
        self.assertTrue(any("must be under features/" in error for error in errors))
        self.assertTrue(any("non-canonical capsule path" in error for error in errors))

    def test_context_report_shows_budget_headroom(self) -> None:
        self.bootstrap_search(agents=True)

        report = "\n".join(
            validate.context_report(self.memory_dir, self.root / "AGENTS.md")
        )

        self.assertIn("Agents guide:", report)
        self.assertIn("Routing:", report)
        self.assertIn("Feature capsules: 1 file, 0 debt entries", report)
        self.assertIn("features/search.md", report)
        self.assertNotIn("features/_template.md", report)

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

    def test_validator_cli_rejects_paths_outside_project_root(self) -> None:
        container = self.root / "validator-paths"
        owner = container / "owner"
        requester = container / "requester"
        owner.mkdir(parents=True)
        requester.mkdir()
        self.assertEqual(run_bootstrap(owner, agents=True), 0)
        self.assertEqual(run_bootstrap(requester, agents=True), 0)
        (requester / "linked-owner").symlink_to(owner, target_is_directory=True)

        cases = (
            {"memory_dir": "../owner/.codex/memory"},
            {"memory_dir": str(owner / ".codex" / "memory")},
            {"memory_dir": "linked-owner/.codex/memory"},
            {"agents_file": "../owner/AGENTS.md"},
            {"agents_file": str(owner / "AGENTS.md")},
        )
        for options in cases:
            with self.subTest(options=options):
                result = run_validate_cli(requester, **options)
                diagnostics = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, diagnostics)


if __name__ == "__main__":
    unittest.main()
