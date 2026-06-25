#!/usr/bin/env python3
"""Bootstrap a project-local .codex/memory scaffold."""

from __future__ import annotations

import argparse
import datetime as _dt
import re
from pathlib import Path


FEATURE_REGISTRY_HEADER = "| Feature | Entry | Status | Capsule | Last Verified |"
FEATURE_REGISTRY_DIVIDER = "| --- | --- | --- | --- | --- |"
DECISION_LOG_HEADER = "| Date | Decision | Context | Impact | Revisit Trigger |"
DECISION_LOG_DIVIDER = "| --- | --- | --- | --- | --- |"
AGENTS_SECTION_TITLE = "## Project Memory Workflow"

CAPSULE_SECTIONS = [
    "Status",
    "Responsibilities",
    "Dependencies",
    "Persistence",
    "Key Decisions",
    "Regression Checks",
]


def today() -> str:
    return _dt.date.today().isoformat()


def slugify_feature(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[/\\:]+", "-", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^\w.-]+", "-", slug, flags=re.UNICODE)
    slug = slug.strip("-._")
    if not slug:
        raise ValueError(f"Feature name {name!r} does not produce a usable file name")
    return slug


def refresh_last_updated(text: str, stamp: str) -> str:
    if re.search(r"^Last Updated:[ \t]*\d{4}-\d{2}-\d{2}[ \t]*$", text, flags=re.M):
        return re.sub(
            r"^Last Updated:[ \t]*\d{4}-\d{2}-\d{2}[ \t]*$",
            f"Last Updated: {stamp}",
            text,
            count=1,
            flags=re.M,
        )

    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines.insert(1, "")
        lines.insert(2, f"Last Updated: {stamp}")
        return "\n".join(lines).rstrip() + "\n"

    return f"Last Updated: {stamp}\n\n{text}".rstrip() + "\n"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


DRY_RUN = False


def write_changed(path: Path, text: str, changes: list[str], label: str) -> None:
    old = read_text(path)
    normalized = text.rstrip() + "\n"
    if old != normalized:
        if not DRY_RUN:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(normalized, encoding="utf-8")
        changes.append(label)


def ensure_file(path: Path, default_text: str, stamp: str, changes: list[str], label: str) -> None:
    if path.exists():
        text = refresh_last_updated(read_text(path), stamp)
    else:
        text = default_text
    write_changed(path, text, changes, label)


def append_if_missing(text: str, needle: str, block: str) -> str:
    if needle in text:
        return text
    return text.rstrip() + "\n\n" + block.strip() + "\n"


def index_template(stamp: str) -> str:
    return f"""# Project Memory Index

Last Updated: {stamp}

## Purpose

This directory stores stable project facts and decisions for future Codex tasks.

## Read Order

1. Read this file first.
2. Read `feature-registry.md` to locate relevant feature capsule(s).
3. Read only target feature capsule(s) under `features/`.
4. Read `project-memory.md` and `decision-log.md` only for cross-module routing, dependency strategy, persistence strategy, or global behavior contracts.

## Memory Files

- `project-memory.md`: stable cross-feature project facts.
- `feature-registry.md`: feature list and capsule pointers.
- `decision-log.md`: durable project decisions.
- `features/_template.md`: template for new feature capsules.

## Write-Back Rules

- Feature-only changes update only the matching feature capsule unless registry metadata changed.
- Global changes update `project-memory.md`, `decision-log.md`, and this index.
- If memory conflicts with code, code is the source of truth; fix memory in the same task.
- Refresh `Last Updated: YYYY-MM-DD` in every touched memory file.
- Do not skip `feature-registry.md` and guess capsule names unless the registry is missing or lacks the target feature.
- If the registry lacks the exact target feature, use the closest existing capsule first.
- Update `feature-registry.md` only when adding or changing stable feature metadata.
- Consider splitting capsules that exceed about 100 lines or mix unrelated responsibilities. Split by function or role such as selection, layout, SDK routing, assets, or persistence. Keep the original capsule as the high-level responsibility and routing summary, move only stable facts, update `feature-registry.md`, and refresh every touched `Last Updated`.
- Add `Source` or `Evidence` for key conclusions that are non-obvious, cross-module, risky, or likely to be challenged. Use `Last Verified`, `Valid Since`, `Deprecated`, `Superseded by`, or `Revisit Trigger` when time validity matters; simple stable facts do not need metadata on every bullet.
"""


def project_memory_template(stamp: str) -> str:
    return f"""# Project Memory

Last Updated: {stamp}

## Stable Facts

- Bootstrap was created with limited known information. Add verified project facts as future tasks discover them.

## Architecture Notes

- Record cross-feature architecture, routing, dependency, and persistence facts here.

## Global Regression Checks

- Add checks that protect global behavior across features.
"""


def feature_registry_template(stamp: str) -> str:
    return f"""# Feature Registry

Last Updated: {stamp}

{FEATURE_REGISTRY_HEADER}
{FEATURE_REGISTRY_DIVIDER}
"""


def decision_log_template(stamp: str) -> str:
    return f"""# Decision Log

Last Updated: {stamp}

{DECISION_LOG_HEADER}
{DECISION_LOG_DIVIDER}
"""


def capsule_template(feature_name: str, stamp: str) -> str:
    return f"""# {feature_name}

Last Updated: {stamp}

## Status

- Unknown until verified.

## Responsibilities

- Add stable responsibilities when verified.

## Dependencies

- Add verified dependencies only.

## Persistence

- Add storage, cache, and schema facts when verified.

## Key Decisions

- Add durable feature decisions here.

## Evidence / Freshness

- Optional: add `Source`, `Evidence`, `Last Verified`, `Valid Since`, `Deprecated`, `Superseded by`, or `Revisit Trigger` for important conclusions whose provenance or time validity matters.

## Regression Checks

- Add checks that protect this feature from regressions.
"""


def template_capsule(stamp: str) -> str:
    return capsule_template("Feature Capsule Template", stamp)


def ensure_feature_registry(path: Path, features: list[str], stamp: str, changes: list[str]) -> None:
    if path.exists():
        text = refresh_last_updated(read_text(path), stamp)
        text = append_if_missing(text, FEATURE_REGISTRY_HEADER, f"{FEATURE_REGISTRY_HEADER}\n{FEATURE_REGISTRY_DIVIDER}")
    else:
        text = feature_registry_template(stamp)

    for feature in features:
        slug = slugify_feature(feature)
        capsule = f"features/{slug}.md"
        row = f"| {feature} | Unknown | Active | `{capsule}` | {stamp} |"
        if capsule not in text:
            text = text.rstrip() + "\n" + row + "\n"

    write_changed(path, text, changes, str(path))


def ensure_decision_log(path: Path, stamp: str, changes: list[str]) -> None:
    if path.exists():
        text = refresh_last_updated(read_text(path), stamp)
        text = append_if_missing(text, DECISION_LOG_HEADER, f"{DECISION_LOG_HEADER}\n{DECISION_LOG_DIVIDER}")
    else:
        text = decision_log_template(stamp)
    write_changed(path, text, changes, str(path))


def ensure_capsule(path: Path, feature_name: str, stamp: str, changes: list[str]) -> None:
    if path.exists():
        text = refresh_last_updated(read_text(path), stamp)
        for section in CAPSULE_SECTIONS:
            heading = f"## {section}"
            if heading not in text:
                text = text.rstrip() + f"\n\n{heading}\n\n- Add verified facts here.\n"
    else:
        text = capsule_template(feature_name, stamp)
    write_changed(path, text, changes, str(path))


def agents_workflow_text() -> str:
    return """## Project Memory Workflow

Before any task: read `.codex/memory/index.md` first, then read `.codex/memory/feature-registry.md` to locate target feature capsule(s).

Read only the target `.codex/memory/features/<Feature>.md` capsule(s). Do not skip the registry and guess capsule names unless the project has no registry or the registry lacks the target feature.

If the registry does not contain an exact target feature, use the closest existing capsule first. Update `feature-registry.md` only when adding or changing stable feature metadata.

Read `project-memory.md` and `decision-log.md` only when the task changes cross-module routing, dependency strategy, persistence strategy, or global behavior contracts.

Feature-only changes: update only the corresponding `.codex/memory/features/<Feature>.md`; update `feature-registry.md` only if feature metadata changed.

Global changes: update `project-memory.md`, `decision-log.md`, and `index.md` in the same change set.

If memory conflicts with code, code is source of truth; fix memory in the same task.

When a capsule exceeds about 100 lines or mixes responsibilities enough that agents must read large unrelated sections, split it by function or role such as selection, layout, SDK routing, assets, or persistence. Keep the original capsule as the high-level responsibility and routing summary, move only stable facts, update `feature-registry.md`, and refresh every touched `Last Updated`.

Every memory update must refresh `Last Updated: YYYY-MM-DD`.

For key conclusions that are non-obvious, cross-module, risky, or likely to be challenged, include `Source` or `Evidence` such as commit hashes, PRs, file paths, command outputs, issue links, docs, or external URLs. Use `Last Verified`, `Valid Since`, `Deprecated`, `Superseded by`, or `Revisit Trigger` when time validity matters; simple stable facts can remain plain bullets.

Do not store temporary execution steps in memory; store only stable facts, decisions, and regression checks.
"""


def upsert_agents_section(path: Path, changes: list[str]) -> None:
    section = agents_workflow_text().rstrip()
    if path.exists():
        text = read_text(path).rstrip()
    else:
        text = "# Agent Guidelines"

    pattern = re.compile(
        rf"^{re.escape(AGENTS_SECTION_TITLE)}\n.*?(?=^## |\Z)",
        flags=re.M | re.S,
    )
    if pattern.search(text):
        updated = pattern.sub(section + "\n", text).rstrip() + "\n"
    else:
        updated = text.rstrip() + "\n\n" + section + "\n"

    write_changed(path, updated, changes, str(path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a .codex/memory scaffold.")
    parser.add_argument("--project-root", default=".", help="Project root to update. Defaults to cwd.")
    parser.add_argument("--feature", action="append", default=[], help="Feature name to create/register. May be repeated.")
    parser.add_argument("--memory-dir", default=".codex/memory", help="Memory directory relative to project root. Defaults to .codex/memory.")
    parser.add_argument("--agents", action="store_true", help="Create or refresh the Project Memory Workflow section in the agents file.")
    parser.add_argument("--agents-file", default="AGENTS.md", help="Agents instructions file relative to project root. Defaults to AGENTS.md.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing any files.")
    return parser.parse_args()


def main() -> int:
    global DRY_RUN
    args = parse_args()
    DRY_RUN = args.dry_run
    root = Path(args.project_root).expanduser().resolve()
    stamp = today()
    memory_dir = (root / args.memory_dir).resolve()
    features_dir = memory_dir / "features"
    changes: list[str] = []

    ensure_file(memory_dir / "index.md", index_template(stamp), stamp, changes, str(memory_dir / "index.md"))
    ensure_file(memory_dir / "project-memory.md", project_memory_template(stamp), stamp, changes, str(memory_dir / "project-memory.md"))
    ensure_feature_registry(memory_dir / "feature-registry.md", args.feature, stamp, changes)
    ensure_decision_log(memory_dir / "decision-log.md", stamp, changes)
    ensure_file(features_dir / "_template.md", template_capsule(stamp), stamp, changes, str(features_dir / "_template.md"))

    for feature in args.feature:
        ensure_capsule(features_dir / f"{slugify_feature(feature)}.md", feature, stamp, changes)

    if args.agents:
        upsert_agents_section((root / args.agents_file).resolve(), changes)

    prefix = "Would update:" if DRY_RUN else "Updated:"
    if changes:
        print(prefix)
        for item in changes:
            print(f"- {item}")
    else:
        print("No changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
