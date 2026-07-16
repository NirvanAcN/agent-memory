#!/usr/bin/env python3
"""Validate a project-local memory tree against the memory file contract."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from pathlib import PurePosixPath

FEATURE_REGISTRY_HEADER = "| Feature | Entry | Status | Capsule | Last Verified |"
DECISION_LOG_HEADER = "| Date | Decision | Context | Impact | Revisit Trigger |"
LAST_UPDATED_RE = re.compile(r"^Last Updated:[ \t]*\d{4}-\d{2}-\d{2}[ \t]*$", re.M)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_FILES = [
    "index.md",
    "project-memory.md",
    "feature-registry.md",
    "decision-log.md",
    "features/_template.md",
    "context-budget.json",
]

CAPSULE_SECTIONS = [
    "Status",
    "Responsibilities",
    "Dependencies",
    "Persistence",
    "Key Decisions",
    "Regression Checks",
]

DEFAULT_CONTEXT_BUDGET = {
    "version": 1,
    "max_agents_bytes": 8 * 1024,
    "max_routing_bytes": 8 * 1024,
    "max_capsule_lines": 128,
    "max_capsule_bytes": 12 * 1024,
    "debt": {},
}
INTEGER_BUDGET_KEYS = (
    "version",
    "max_agents_bytes",
    "max_routing_bytes",
    "max_capsule_lines",
    "max_capsule_bytes",
)
SUPPORTED_CONTEXT_BUDGET_VERSION = 1


def parse_registry(path: Path, errors: list[str]) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        if FEATURE_REGISTRY_HEADER in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 5:
            errors.append(f"feature-registry.md:{line_number}: malformed table row")
            continue
        feature = cells[0]
        pointer = cells[3].strip("`")
        relative = PurePosixPath(pointer)
        if (
            not pointer.endswith(".md")
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in pointer
        ):
            errors.append(
                f"feature-registry.md:{line_number}: unsafe capsule path '{pointer}'"
            )
            continue
        entries.append((feature, pointer))

    feature_counts = Counter(feature for feature, _pointer in entries)
    pointer_counts = Counter(pointer for _feature, pointer in entries)
    for feature, count in feature_counts.items():
        if count > 1:
            errors.append(f"feature-registry.md: duplicate feature '{feature}'")
    for pointer, count in pointer_counts.items():
        if count > 1:
            errors.append(f"feature-registry.md: duplicate capsule '{pointer}'")
    return entries


def load_context_budget(path: Path, errors: list[str]) -> dict | None:
    initial_error_count = len(errors)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"context-budget.json: invalid JSON: {error}")
        return None
    if not isinstance(config, dict):
        errors.append("context-budget.json: root must be an object")
        return None

    for key in INTEGER_BUDGET_KEYS:
        value = config.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            errors.append(f"context-budget.json: '{key}' must be a positive integer")

    if config.get("version") != SUPPORTED_CONTEXT_BUDGET_VERSION:
        errors.append(
            f"context-budget.json: unsupported version '{config.get('version')}'"
        )

    if not DATE_RE.fullmatch(str(config.get("last_updated", ""))):
        errors.append("context-budget.json: missing or malformed 'last_updated'")

    debt = config.get("debt")
    if not isinstance(debt, dict):
        errors.append("context-budget.json: 'debt' must be an object")
        return None
    for pointer, limits in debt.items():
        relative = PurePosixPath(pointer)
        if relative.is_absolute() or ".." in relative.parts or "\\" in pointer:
            errors.append(f"context-budget.json: unsafe debt path '{pointer}'")
            continue
        if not isinstance(limits, dict):
            errors.append(f"context-budget.json: debt '{pointer}' must be an object")
            continue
        for key in ("max_lines", "max_bytes"):
            value = limits.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(
                    f"context-budget.json: debt '{pointer}.{key}' must be a positive integer"
                )

    return config if len(errors) == initial_error_count else None


def validate_capsule_budget(
    relative: str, text: str, budget: dict, errors: list[str]
) -> None:
    standard_lines = budget["max_capsule_lines"]
    standard_bytes = budget["max_capsule_bytes"]
    debt = budget["debt"].get(relative)
    line_count = len(text.splitlines())
    byte_count = len(text.encode("utf-8"))

    if debt and line_count <= standard_lines and byte_count <= standard_bytes:
        errors.append(
            f"context-budget.json: debt '{relative}' is below the standard budget; remove it"
        )
        return

    max_lines = debt["max_lines"] if debt else standard_lines
    max_bytes = debt["max_bytes"] if debt else standard_bytes
    if line_count > max_lines:
        errors.append(f"{relative}: {line_count} lines exceeds context budget {max_lines}")
    if byte_count > max_bytes:
        errors.append(f"{relative}: {byte_count} bytes exceeds context budget {max_bytes}")


def validate(memory_dir: Path, agents_file: Path | None = None) -> list[str]:
    errors: list[str] = []

    if not memory_dir.is_dir():
        return [f"Missing memory directory: {memory_dir}"]

    for rel in REQUIRED_FILES:
        path = memory_dir / rel
        if not path.is_file():
            errors.append(f"Missing required file: {rel}")
            continue
        if path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        if not LAST_UPDATED_RE.search(text):
            errors.append(f"{rel}: missing or malformed 'Last Updated: YYYY-MM-DD'")

    registry = memory_dir / "feature-registry.md"
    entries: list[tuple[str, str]] = []
    if registry.is_file():
        registry_text = registry.read_text(encoding="utf-8")
        if FEATURE_REGISTRY_HEADER not in registry_text:
            errors.append("feature-registry.md: missing required table header")
        entries = parse_registry(registry, errors)
        for _feature, pointer in entries:
            if not (memory_dir / pointer).is_file():
                errors.append(f"feature-registry.md: points at missing capsule '{pointer}'")

    decisions = memory_dir / "decision-log.md"
    if decisions.is_file() and DECISION_LOG_HEADER not in decisions.read_text(encoding="utf-8"):
        errors.append("decision-log.md: missing required table header")

    features_dir = memory_dir / "features"
    capsule_paths: dict[str, Path] = {}
    if features_dir.is_dir():
        for capsule in sorted(features_dir.glob("*.md")):
            text = capsule.read_text(encoding="utf-8")
            rel = f"features/{capsule.name}"
            capsule_paths[rel] = capsule
            if not LAST_UPDATED_RE.search(text):
                errors.append(f"{rel}: missing or malformed 'Last Updated: YYYY-MM-DD'")
            for section in CAPSULE_SECTIONS:
                if f"## {section}" not in text:
                    errors.append(f"{rel}: missing required section '## {section}'")

    for _feature, pointer in entries:
        capsule = memory_dir / pointer
        if capsule.is_file():
            capsule_paths[pointer] = capsule
            text = capsule.read_text(encoding="utf-8")
            if not LAST_UPDATED_RE.search(text):
                errors.append(
                    f"{pointer}: missing or malformed 'Last Updated: YYYY-MM-DD'"
                )

    budget_path = memory_dir / "context-budget.json"
    budget = load_context_budget(budget_path, errors) if budget_path.is_file() else None
    if budget:
        routing_paths = (memory_dir / "index.md", registry)
        if all(path.is_file() for path in routing_paths):
            routing_bytes = sum(path.stat().st_size for path in routing_paths)
            if routing_bytes > budget["max_routing_bytes"]:
                errors.append(
                    f"index.md + feature-registry.md: {routing_bytes} bytes exceeds "
                    f"context budget {budget['max_routing_bytes']}"
                )

        if agents_file and agents_file.is_file():
            agents_bytes = agents_file.stat().st_size
            if agents_bytes > budget["max_agents_bytes"]:
                errors.append(
                    f"{agents_file.name}: {agents_bytes} bytes exceeds context budget "
                    f"{budget['max_agents_bytes']}"
                )

        debt_paths = set(budget["debt"])
        capsule_relatives = set(capsule_paths)
        for stale in sorted(debt_paths - capsule_relatives):
            errors.append(f"context-budget.json: stale debt path '{stale}'")
        for relative, capsule in sorted(capsule_paths.items()):
            validate_capsule_budget(
                relative, capsule.read_text(encoding="utf-8"), budget, errors
            )

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a memory tree against the contract.")
    parser.add_argument("--project-root", default=".", help="Project root to validate. Defaults to cwd.")
    parser.add_argument("--memory-dir", default=".codex/memory", help="Memory directory relative to project root. Defaults to .codex/memory.")
    parser.add_argument(
        "--agents-file",
        default="AGENTS.md",
        help="Agents instructions file relative to project root. Defaults to AGENTS.md.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.project_root).expanduser().resolve()
    memory_dir = (root / args.memory_dir).resolve()
    errors = validate(memory_dir, (root / args.agents_file).resolve())
    if errors:
        print("Memory contract violations:")
        for item in errors:
            print(f"- {item}")
        return 1
    print("OK: memory tree satisfies the contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
