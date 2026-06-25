#!/usr/bin/env python3
"""Validate a project-local .codex/memory tree against the memory file contract."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

FEATURE_REGISTRY_HEADER = "| Feature | Entry | Status | Capsule | Last Verified |"
DECISION_LOG_HEADER = "| Date | Decision | Context | Impact | Revisit Trigger |"

LAST_UPDATED_RE = re.compile(r"^Last Updated:[ \t]*\d{4}-\d{2}-\d{2}[ \t]*$", re.M)

REQUIRED_FILES = [
    "index.md",
    "project-memory.md",
    "feature-registry.md",
    "decision-log.md",
    "features/_template.md",
]

CAPSULE_SECTIONS = [
    "Status",
    "Responsibilities",
    "Dependencies",
    "Persistence",
    "Key Decisions",
    "Regression Checks",
]


def validate(memory_dir: Path) -> list[str]:
    errors: list[str] = []

    if not memory_dir.is_dir():
        return [f"Missing memory directory: {memory_dir}"]

    for rel in REQUIRED_FILES:
        path = memory_dir / rel
        if not path.is_file():
            errors.append(f"Missing required file: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if not LAST_UPDATED_RE.search(text):
            errors.append(f"{rel}: missing or malformed 'Last Updated: YYYY-MM-DD'")

    registry = memory_dir / "feature-registry.md"
    if registry.is_file() and FEATURE_REGISTRY_HEADER not in registry.read_text(encoding="utf-8"):
        errors.append("feature-registry.md: missing required table header")

    decisions = memory_dir / "decision-log.md"
    if decisions.is_file() and DECISION_LOG_HEADER not in decisions.read_text(encoding="utf-8"):
        errors.append("decision-log.md: missing required table header")

    features_dir = memory_dir / "features"
    if features_dir.is_dir():
        for capsule in sorted(features_dir.glob("*.md")):
            text = capsule.read_text(encoding="utf-8")
            rel = f"features/{capsule.name}"
            if not LAST_UPDATED_RE.search(text):
                errors.append(f"{rel}: missing or malformed 'Last Updated: YYYY-MM-DD'")
            for section in CAPSULE_SECTIONS:
                if f"## {section}" not in text:
                    errors.append(f"{rel}: missing required section '## {section}'")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a .codex/memory tree against the contract.")
    parser.add_argument("--project-root", default=".", help="Project root to validate. Defaults to cwd.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    memory_dir = Path(args.project_root).expanduser().resolve() / ".codex" / "memory"
    errors = validate(memory_dir)
    if errors:
        print("Memory contract violations:")
        for item in errors:
            print(f"- {item}")
        return 1
    print("OK: memory tree satisfies the contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
