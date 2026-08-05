#!/usr/bin/env python3
"""Bootstrap a project-local agent memory scaffold (default .codex/memory)."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from pathlib import PurePosixPath


FEATURE_REGISTRY_HEADER = "| Feature | Entry | Status | Capsule | Last Verified |"
FEATURE_REGISTRY_DIVIDER = "| --- | --- | --- | --- | --- |"
DECISION_LOG_HEADER = "| Date | Decision | Context | Impact | Revisit Trigger |"
DECISION_LOG_DIVIDER = "| --- | --- | --- | --- | --- |"
AGENTS_SECTION_TITLE = "## Project Memory Workflow"
POLICY_VERSION = 1
INDEX_READ_POLICY_ID = "index-read-order"
INDEX_WRITE_POLICY_ID = "index-write-back"
AGENTS_POLICY_ID = "project-memory-workflow"
INDEX_READ_RULE_IDS = (
    "locate-before-read",
    "minimum-read",
    "global-read-scope",
)
INDEX_WRITE_RULE_IDS = (
    "scoped-write-back",
    "code-source-of-truth",
    "verification-before-write",
    "fail-open-privacy",
    "compare-before-write",
    "freshness",
    "registry-integrity",
    "capsule-splitting",
    "context-budget",
    "evidence-freshness",
    "managed-policy-upgrade",
)
AGENTS_RULE_IDS = INDEX_READ_RULE_IDS + INDEX_WRITE_RULE_IDS
POLICY_START_RE = re.compile(
    r"^<!-- agent-memory:policy-start id=([a-z0-9-]+) version=([1-9][0-9]*) -->$"
)

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

LAST_UPDATED_PREFIX = "Last Updated:"
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


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


def preflight_features(names: list[str]) -> list[tuple[str, str]]:
    features: list[tuple[str, str]] = []
    names_by_slug: dict[str, str] = {}
    seen_names: set[str] = set()

    for raw_name in names:
        if "|" in raw_name:
            raise ValueError(
                f"--feature {raw_name!r} contains '|', which would break the feature registry table"
            )
        if "\r" in raw_name or "\n" in raw_name:
            raise ValueError(
                f"--feature {raw_name!r} contains a newline, which would break "
                "the feature registry table"
            )
        if any(not character.isprintable() for character in raw_name):
            raise ValueError(
                f"--feature {raw_name!r} contains non-printable characters"
            )

        feature_name = raw_name.strip()
        if not feature_name:
            raise ValueError("--feature names must contain at least one usable character")

        try:
            slug = slugify_feature(feature_name)
        except ValueError as exc:
            raise ValueError(f"invalid --feature {raw_name!r}: {exc}") from exc

        previous_name = names_by_slug.get(slug)
        if previous_name is not None and previous_name != raw_name:
            raise ValueError(
                f"--feature values {previous_name!r} and {raw_name!r} both normalize "
                f"to {slug!r}; use distinct feature names"
            )
        names_by_slug[slug] = raw_name

        if raw_name not in seen_names:
            features.append((feature_name, slug))
            seen_names.add(raw_name)

    return features


def is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def resolve_within_project(path: Path, root: Path, label: str) -> Path:
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"cannot resolve {label} {str(path)!r}: {exc}") from exc

    if not is_within(resolved, root):
        raise ValueError(
            f"{label} resolves outside --project-root: {str(path)!r} -> {str(resolved)!r}"
        )
    return resolved


def project_local_path(root: Path, value: str, option: str) -> tuple[Path, str]:
    if not value:
        raise ValueError(f"{option} must not be empty")
    if "`" in value or any(not character.isprintable() for character in value):
        raise ValueError(
            f"{option} contains characters that are unsafe in generated Markdown"
        )

    try:
        relative = Path(value).expanduser()
    except RuntimeError as exc:
        raise ValueError(f"cannot expand {option} {value!r}: {exc}") from exc

    if relative.is_absolute():
        raise ValueError(
            f"{option} must be relative to --project-root; got absolute path {value!r}"
        )
    if ".." in relative.parts:
        raise ValueError(f"{option} must not contain '..': {value!r}")

    resolved = resolve_within_project(root / relative, root, option)
    return resolved, relative.as_posix()


def preflight_output_paths(root: Path, paths: list[tuple[Path, str]]) -> None:
    for path, label in paths:
        resolved = resolve_within_project(path, root, label)
        if resolved.exists() and resolved.is_dir():
            raise ValueError(f"{label} must be a file, but {str(resolved)!r} is a directory")


def markdown_structure_lines(text: str) -> list[tuple[int, str]]:
    """Return Markdown lines outside fenced code blocks with line numbers."""
    structural: list[tuple[int, str]] = []
    fence_character: str | None = None
    fence_length = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = FENCE_RE.match(line)
        if match:
            marker = match.group(1)
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
                continue
            remainder = line[match.end() :]
            if (
                marker[0] == fence_character
                and len(marker) >= fence_length
                and not remainder.strip(" \t")
            ):
                fence_character = None
                fence_length = 0
                continue
        if fence_character is None:
            structural.append((line_number, line.rstrip(" \t")))
    return structural


def is_iso_calendar_date(value: str) -> bool:
    if not DATE_RE.fullmatch(value):
        return False
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def last_updated_markers(text: str) -> list[tuple[int, str]]:
    markers: list[tuple[int, str]] = []
    for line_number, line in markdown_structure_lines(text):
        if line.startswith(LAST_UPDATED_PREFIX):
            markers.append(
                (line_number, line[len(LAST_UPDATED_PREFIX) :].strip(" \t"))
            )
    return markers


def refresh_last_updated(text: str, stamp: str) -> str:
    lines = text.splitlines()
    marker_indexes = [
        line_number - 1 for line_number, _value in last_updated_markers(text)
    ]
    if marker_indexes:
        lines[marker_indexes[0]] = f"Last Updated: {stamp}"
        for index in reversed(marker_indexes[1:]):
            del lines[index]
        return "\n".join(lines).rstrip() + "\n"

    if lines and lines[0].startswith("# "):
        lines.insert(1, "")
        lines.insert(2, f"Last Updated: {stamp}")
        return "\n".join(lines).rstrip() + "\n"

    return f"Last Updated: {stamp}\n\n{text}".rstrip() + "\n"


def refresh_after_repair(original: str, repaired: str, stamp: str) -> str:
    markers = last_updated_markers(original)
    freshness_is_valid = (
        len(markers) == 1 and is_iso_calendar_date(markers[0][1])
    )
    if repaired != original or not freshness_is_valid:
        return refresh_last_updated(repaired, stamp)
    return original


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


DRY_RUN = False


def write_changed(path: Path, text: str, changes: list[str], label: str) -> None:
    old = read_text(path)
    if old != text:
        if not DRY_RUN:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        changes.append(label)


def ensure_file(path: Path, default_text: str, stamp: str, changes: list[str], label: str) -> None:
    if path.exists():
        original = read_text(path)
        text = refresh_after_repair(original, original, stamp)
    else:
        text = default_text
    write_changed(path, text, changes, label)


def policy_start_marker(block_id: str, version: int = POLICY_VERSION) -> str:
    return f"<!-- agent-memory:policy-start id={block_id} version={version} -->"


def policy_rules_marker(rule_ids: tuple[str, ...]) -> str:
    return "<!-- agent-memory:policy-rules " + " ".join(rule_ids) + " -->"


def policy_end_marker(block_id: str) -> str:
    return f"<!-- agent-memory:policy-end id={block_id} -->"


def policy_block(block_id: str, rule_ids: tuple[str, ...], body: str) -> str:
    return "\n".join(
        (
            policy_start_marker(block_id),
            policy_rules_marker(rule_ids),
            body.strip(),
            policy_end_marker(block_id),
        )
    )


def find_h2_section(text: str, heading: str) -> tuple[int, int] | None:
    matches = [
        line_number
        for line_number, line in markdown_structure_lines(text)
        if line == heading
    ]
    if len(matches) > 1:
        raise ValueError(f"duplicate section {heading!r}")
    if not matches:
        return None

    heading_line = matches[0]
    end_index = len(text.splitlines())
    for line_number, line in markdown_structure_lines(text):
        if line_number > heading_line and line.startswith("## "):
            end_index = line_number - 1
            break
    return heading_line - 1, end_index


def find_policy_block(
    text: str, block_id: str
) -> tuple[int, int, int] | None:
    starts: list[tuple[int, int]] = []
    ends: list[int] = []
    start_prefix = f"<!-- agent-memory:policy-start id={block_id} "
    end_marker = policy_end_marker(block_id)

    for line_number, line in markdown_structure_lines(text):
        if line.startswith(start_prefix):
            match = POLICY_START_RE.fullmatch(line)
            if match is None or match.group(1) != block_id:
                raise ValueError(f"malformed managed policy start for {block_id!r}")
            starts.append((line_number - 1, int(match.group(2))))
        if line == end_marker:
            ends.append(line_number - 1)

    if not starts and not ends:
        return None
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError(
            f"managed policy {block_id!r} must have exactly one start and end marker"
        )
    start_index, version = starts[0]
    end_index = ends[0]
    if end_index <= start_index:
        raise ValueError(f"managed policy {block_id!r} has out-of-order markers")
    return start_index, end_index, version


def strip_legacy_generated_lines(body: str, legacy_body: str) -> str:
    generated = {
        line.rstrip() for line in legacy_body.splitlines() if line.strip()
    }
    kept: list[str] = []
    for line in body.splitlines():
        if line.rstrip() in generated:
            continue
        if not line.strip():
            if kept and kept[-1] != "":
                kept.append("")
            continue
        kept.append(line.rstrip())
    while kept and kept[-1] == "":
        kept.pop()
    return "\n".join(kept)


def upsert_policy_section(
    text: str,
    *,
    heading: str,
    block_id: str,
    rule_ids: tuple[str, ...],
    body: str,
    legacy_body: str,
    upgrade: bool,
    allow_create: bool,
) -> str:
    section = find_h2_section(text, heading)
    block = find_policy_block(text, block_id)
    replacement = policy_block(block_id, rule_ids, body)

    if section is None:
        if not (upgrade or allow_create):
            raise ValueError(
                f"existing memory is missing managed section {heading!r}; "
                "preview an explicit policy migration with --upgrade --dry-run"
            )
        return text.rstrip() + f"\n\n{heading}\n\n{replacement}\n"

    heading_index, section_end = section
    if block is not None:
        start_index, end_index, version = block
        if not (heading_index < start_index <= end_index < section_end):
            raise ValueError(
                f"managed policy {block_id!r} is outside section {heading!r}"
            )
        if version > POLICY_VERSION:
            raise ValueError(
                f"managed policy {block_id!r} uses newer version {version}; "
                f"this skill supports version {POLICY_VERSION} and will not downgrade it"
            )
        if version < POLICY_VERSION and not upgrade:
            raise ValueError(
                f"managed policy {block_id!r} uses version {version}; "
                "preview the upgrade with --upgrade --dry-run"
            )
        lines = text.splitlines()
        replacement_lines = replacement.splitlines()
        if end_index + 1 < len(lines) and lines[end_index + 1].strip():
            replacement_lines.append("")
        lines[start_index : end_index + 1] = replacement_lines
        return "\n".join(lines).rstrip() + "\n"

    if not upgrade:
        raise ValueError(
            f"section {heading!r} is an unmanaged legacy policy; "
            "preview an explicit migration with --upgrade --dry-run"
        )

    lines = text.splitlines()
    body_start = heading_index + 1
    preserved = strip_legacy_generated_lines(
        "\n".join(lines[body_start:section_end]), legacy_body
    )
    new_body = ["", *replacement.splitlines()]
    if preserved:
        new_body.append("")
        new_body.extend(preserved.splitlines())
    new_body.append("")
    lines[body_start:section_end] = new_body
    return "\n".join(lines).rstrip() + "\n"


def has_section(text: str, section: str) -> bool:
    heading = f"## {section}"
    return any(
        line == heading for _line_number, line in markdown_structure_lines(text)
    )


def parse_table_row(line: str) -> list[str] | None:
    stripped = line.rstrip(" \t")
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    cells = [cell.strip() for cell in stripped[1:-1].split("|")]
    return cells if len(cells) == 5 else None


def find_registry_table(lines: list[str]) -> tuple[int, int] | None:
    structural = dict(markdown_structure_lines("\n".join(lines)))
    for line_number, line in structural.items():
        if (
            line == FEATURE_REGISTRY_HEADER
            and structural.get(line_number + 1) == FEATURE_REGISTRY_DIVIDER
        ):
            return line_number - 1, line_number + 1
    return None


def ensure_table(text: str, header: str, divider: str) -> str:
    lines = text.splitlines()
    structural = dict(markdown_structure_lines(text))
    for line_number, line in structural.items():
        if line != header:
            continue
        if structural.get(line_number + 1) != divider:
            lines.insert(line_number, divider)
            return "\n".join(lines).rstrip() + "\n"
        return text
    return text.rstrip() + f"\n\n{header}\n{divider}\n"


def registry_rows(text: str) -> list[list[str]]:
    lines = text.splitlines()
    table = find_registry_table(lines)
    if table is None:
        return []

    _, index = table
    rows: list[list[str]] = []
    while index < len(lines):
        cells = parse_table_row(lines[index])
        if cells is None:
            break
        rows.append(cells)
        index += 1
    return rows


def registry_cell_value(cell: str) -> str:
    value = cell.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    return value


def validate_capsule_pointer(pointer: str) -> str:
    relative = PurePosixPath(pointer)
    if (
        not pointer.endswith(".md")
        or relative.is_absolute()
        or ".." in relative.parts
        or "\\" in pointer
        or relative.as_posix() != pointer
        or len(relative.parts) < 2
        or relative.parts[0] != "features"
        or pointer == "features/_template.md"
    ):
        raise ValueError(
            f"feature registry contains unsafe capsule path {pointer!r}"
        )
    return pointer


def insert_registry_row(text: str, row: str) -> str:
    lines = text.splitlines()
    table = find_registry_table(lines)
    if table is None:
        raise ValueError("feature registry table is missing")

    _, index = table
    while index < len(lines) and parse_table_row(lines[index]) is not None:
        index += 1
    lines.insert(index, row)
    return "\n".join(lines).rstrip() + "\n"


def plan_features(
    text: str, features: list[tuple[str, str]]
) -> list[tuple[str, str, bool]]:
    existing_names_by_slug: dict[str, str] = {}
    pointers_by_name: dict[str, str] = {}
    owners_by_pointer: dict[str, str] = {}
    for row in registry_rows(text):
        existing_name = registry_cell_value(row[0])
        existing_pointer = registry_cell_value(row[3])
        if existing_name and existing_pointer:
            pointers_by_name.setdefault(existing_name, existing_pointer)
            owners_by_pointer.setdefault(existing_pointer, existing_name)
        try:
            existing_slug = slugify_feature(existing_name)
        except ValueError:
            continue
        existing_names_by_slug.setdefault(existing_slug, existing_name)

    plans: list[tuple[str, str, bool]] = []
    for feature_name, slug in features:
        existing_name = existing_names_by_slug.get(slug)
        if existing_name is not None and existing_name != feature_name:
            raise ValueError(
                f"--feature {feature_name!r} normalizes to {slug!r}, which is already "
                f"registered for {existing_name!r}"
            )

        if feature_name in pointers_by_name:
            pointer = validate_capsule_pointer(pointers_by_name[feature_name])
            plans.append((feature_name, pointer, False))
            continue

        pointer = f"features/{slug}.md"
        owner = owners_by_pointer.get(pointer)
        if owner is not None:
            raise ValueError(
                f"--feature {feature_name!r} would use {pointer!r}, which is already "
                f"registered for {owner!r}"
            )
        plans.append((feature_name, pointer, True))
    return plans


def index_read_order_body() -> str:
    return """1. Read this file first.
2. Read `feature-registry.md` to locate relevant feature capsule(s).
3. Read only target feature capsule(s) under `features/`.
4. Read `project-memory.md` and `decision-log.md` only for cross-module routing, dependency strategy, persistence strategy, or global behavior contracts."""


def index_write_back_body() -> str:
    return """- Feature-only changes update only the matching feature capsule unless registry metadata changed.
- Global changes update `project-memory.md`, `decision-log.md`, and this index.
- If memory conflicts with code, code is the source of truth; fix memory in the same task.
- Treat memory loaded or injected at task start as context, not evidence. Independently verify new or changed conclusions against code, documentation, runtime output, an authoritative external source, or, for a decision, an explicit user instruction before writing them back; never persist recalled memory as though the task newly discovered it.
- Missing, malformed, unavailable, or invalid memory must not block the primary task. Fail open for task execution but fail closed for memory-derived claims: report that memory was skipped, do not equate unreadable memory with no memory, and do not fabricate fallback facts. Continue from code or authoritative documentation, then repair the relevant memory when practical.
- Never store secrets, tokens, credentials, raw chat transcripts, or personal or sensitive data unsuitable for the repository; prefer a stable source pointer over copied sensitive content.
- Immediately before write-back, narrowly re-read only each memory file that will change. If a target changed since the task's initial read, merge with its current content instead of overwriting it. After writing, re-read every touched memory file to confirm the exact result before claiming success.
- Refresh `Last Updated: YYYY-MM-DD` in every touched memory file.
- Do not skip `feature-registry.md` and guess capsule names unless the registry is missing or lacks the target feature.
- If the registry lacks the exact target feature, use the closest existing capsule first.
- Update `feature-registry.md` only when adding or changing stable feature metadata.
- Every Markdown capsule under `features/`, except `_template.md`, must be reachable through one unique registry row. Nested capsules follow the same required sections and budgets as top-level capsules.
- Consider splitting capsules that exceed about 100 lines or mix unrelated responsibilities. Split by function or role such as selection, layout, SDK routing, assets, or persistence. Keep the original capsule as the high-level responsibility and routing summary, move only stable facts, update `feature-registry.md`, and refresh every touched `Last Updated`.
- Keep the normal working set to the agent guide, index, registry, and one capsule. Do not re-read unchanged content during normal routing; the narrow task-end comparison before write-back is the exception. Before loading another capsule or global file, identify the missing fact and use the narrowest relevant range.
- Do not hand-edit managed policy markers or rule IDs. Preview legacy migrations with the `agent-memory` skill's bundled bootstrap script using `--upgrade --dry-run`, then apply with `--upgrade`.
- Run the `agent-memory` skill's bundled validator after bootstrap and every memory write-back; use `--report` during audits to inspect current headroom. Standard context limits live in `context-budget.json`; explicit legacy debt may shrink but must not grow, and both ceilings must be lowered to the new measured size whenever a debt file shrinks.
- Add `Source` or `Evidence` for key conclusions that are non-obvious, cross-module, risky, or likely to be challenged. Use `Last Verified`, `Valid Since`, `Deprecated`, `Superseded by`, or `Revisit Trigger` when time validity matters; simple stable facts do not need metadata on every bullet."""


def index_template(stamp: str) -> str:
    return f"""# Project Memory Index

Last Updated: {stamp}

## Purpose

This directory stores stable project facts and decisions for future Codex tasks.

## Read Order

{policy_block(INDEX_READ_POLICY_ID, INDEX_READ_RULE_IDS, index_read_order_body())}

## Memory Files

- `project-memory.md`: stable cross-feature project facts.
- `feature-registry.md`: feature list and capsule pointers.
- `decision-log.md`: durable project decisions.
- `features/_template.md`: template for new feature capsules.
- `context-budget.json`: machine-readable limits; agents do not read it during normal task routing.

## Write-Back Rules

{policy_block(INDEX_WRITE_POLICY_ID, INDEX_WRITE_RULE_IDS, index_write_back_body())}
"""


def prepare_index_text(path: Path, stamp: str, upgrade: bool) -> str:
    if not path.exists():
        return index_template(stamp)

    original = read_text(path)
    text = upsert_policy_section(
        original,
        heading="## Read Order",
        block_id=INDEX_READ_POLICY_ID,
        rule_ids=INDEX_READ_RULE_IDS,
        body=index_read_order_body(),
        legacy_body=index_read_order_body(),
        upgrade=upgrade,
        allow_create=False,
    )
    text = upsert_policy_section(
        text,
        heading="## Write-Back Rules",
        block_id=INDEX_WRITE_POLICY_ID,
        rule_ids=INDEX_WRITE_RULE_IDS,
        body=index_write_back_body(),
        legacy_body=index_write_back_body(),
        upgrade=upgrade,
        allow_create=False,
    )
    return refresh_after_repair(original, text, stamp)


def context_budget_template(stamp: str) -> str:
    config = {"last_updated": stamp, **DEFAULT_CONTEXT_BUDGET}
    return json.dumps(config, indent=2) + "\n"


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

- Optional: add `Source`, `Evidence`, `Last Verified`, `Valid Since`, `Deprecated`, `Superseded by`, or `Revisit Trigger` for important conclusions whose provenance or time validity matters. Memory recall is context, not evidence; use an independently verified source.

## Regression Checks

- Add checks that protect this feature from regressions.
"""


def template_capsule(stamp: str) -> str:
    return capsule_template("Feature Capsule Template", stamp)


def ensure_feature_registry(
    path: Path,
    features: list[tuple[str, str, bool]],
    stamp: str,
    changes: list[str],
) -> None:
    if path.exists():
        original = read_text(path)
        text = ensure_table(
            original, FEATURE_REGISTRY_HEADER, FEATURE_REGISTRY_DIVIDER
        )
    else:
        original = ""
        text = feature_registry_template(stamp)

    for feature_name, capsule, should_register in features:
        if not should_register:
            continue
        row = f"| {feature_name} | Unknown | Active | `{capsule}` | {stamp} |"
        text = insert_registry_row(text, row)

    text = refresh_after_repair(original, text, stamp)
    write_changed(path, text, changes, str(path))


def ensure_decision_log(path: Path, stamp: str, changes: list[str]) -> None:
    if path.exists():
        original = read_text(path)
        text = ensure_table(original, DECISION_LOG_HEADER, DECISION_LOG_DIVIDER)
    else:
        original = ""
        text = decision_log_template(stamp)
    text = refresh_after_repair(original, text, stamp)
    write_changed(path, text, changes, str(path))


def ensure_capsule(path: Path, feature_name: str, stamp: str, changes: list[str]) -> None:
    if path.exists():
        original = read_text(path)
        text = original
        for section in CAPSULE_SECTIONS:
            heading = f"## {section}"
            if not has_section(text, section):
                text = text.rstrip() + f"\n\n{heading}\n\n- Add verified facts here.\n"
    else:
        original = ""
        text = capsule_template(feature_name, stamp)
    text = refresh_after_repair(original, text, stamp)
    write_changed(path, text, changes, str(path))


def agents_workflow_body(memory_dir: str) -> str:
    return f"""Before any task: read `{memory_dir}/index.md` first, then read `{memory_dir}/feature-registry.md` to locate target feature capsule(s).

Read only the target `{memory_dir}/features/<Feature>.md` capsule(s). Do not skip the registry and guess capsule names unless the project has no registry or the registry lacks the target feature.

If the registry does not contain an exact target feature, use the closest existing capsule first. Update `feature-registry.md` only when adding or changing stable feature metadata.

Every Markdown capsule under `features/`, except `_template.md`, must be reachable through one unique registry row. Nested capsules follow the same required sections and budgets as top-level capsules.

Read `project-memory.md` and `decision-log.md` only when the task changes cross-module routing, dependency strategy, persistence strategy, or global behavior contracts.

Keep the default working set to this guide, the memory index, the registry, and one capsule. Do not re-read unchanged files or command output during normal routing. Before reading another capsule, a global memory file, or a legacy aggregate, identify the missing fact and use the narrowest heading, range, or query that answers it.

Feature-only changes: update only the corresponding `{memory_dir}/features/<Feature>.md`; update `feature-registry.md` only if feature metadata changed.

Global changes: update `project-memory.md`, `decision-log.md`, and `index.md` in the same change set.

Treat memory loaded or injected at task start as context, not evidence. Independently verify new or changed conclusions against code, documentation, runtime output, an authoritative external source, or, for a decision, an explicit user instruction before writing them back. Never persist recalled memory as though the task newly discovered it.

Missing, malformed, unavailable, or invalid memory must not block the primary task. Fail open for task execution but fail closed for memory-derived claims: report that memory was skipped, do not equate unreadable memory with no memory, and do not fabricate fallback facts. Continue from code or authoritative documentation, then repair the relevant memory when practical.

Never store secrets, tokens, credentials, raw chat transcripts, or personal or sensitive data unsuitable for the repository. Prefer a stable source pointer over copied sensitive content.

Immediately before write-back, narrowly re-read only each memory file that will change. If a target changed since the task's initial read, merge with its current content instead of overwriting it. This task-end check is an explicit exception to the normal no-re-read rule. After writing, re-read every touched memory file to confirm the exact result before claiming success.

If memory conflicts with code, code is source of truth; fix memory in the same task.

When a capsule exceeds about 100 lines or mixes responsibilities enough that agents must read large unrelated sections, split it by function or role such as selection, layout, SDK routing, assets, or persistence. Keep the original capsule as the high-level responsibility and routing summary, move only stable facts, update `feature-registry.md`, and refresh every touched `Last Updated`.

Do not hand-edit managed policy markers or rule IDs. Preview legacy migrations with the `agent-memory` skill's bundled bootstrap script using `--upgrade --dry-run`, then apply with `--upgrade`.

Run the `agent-memory` skill's bundled validator after bootstrap and every memory write-back; use `--report` during audits to inspect current headroom. `context-budget.json` is machine-readable validation configuration and is not part of the normal read path. Standard capsules must remain within its line and byte budgets. Explicit legacy debt may shrink but must not grow, and both ceilings must be lowered to the new measured size whenever a debt file shrinks.

Every memory update must refresh `Last Updated: YYYY-MM-DD`.

For key conclusions that are non-obvious, cross-module, risky, or likely to be challenged, include `Source` or `Evidence` such as commit hashes, PRs, file paths, command outputs, issue links, docs, or external URLs. Use `Last Verified`, `Valid Since`, `Deprecated`, `Superseded by`, or `Revisit Trigger` when time validity matters; simple stable facts can remain plain bullets.

Do not store temporary execution steps in memory; store only stable facts, decisions, and regression checks.
"""


def prepare_agents_text(path: Path, memory_dir: str, upgrade: bool) -> str:
    if path.exists():
        text = read_text(path).rstrip()
    else:
        text = "# Agent Guidelines"
    return upsert_policy_section(
        text,
        heading=AGENTS_SECTION_TITLE,
        block_id=AGENTS_POLICY_ID,
        rule_ids=AGENTS_RULE_IDS,
        body=agents_workflow_body(memory_dir),
        legacy_body=agents_workflow_body(memory_dir),
        upgrade=upgrade,
        allow_create=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a .codex/memory scaffold.")
    parser.add_argument("--project-root", default=".", help="Project root to update. Defaults to cwd.")
    parser.add_argument("--feature", action="append", default=[], help="Feature name to create/register. May be repeated.")
    parser.add_argument("--memory-dir", default=".codex/memory", help="Memory directory relative to project root. Defaults to .codex/memory.")
    parser.add_argument("--agents", action="store_true", help="Create or refresh the Project Memory Workflow section in the agents file.")
    parser.add_argument("--agents-file", default="AGENTS.md", help="Agents instructions file relative to project root. Defaults to AGENTS.md.")
    parser.add_argument("--upgrade", action="store_true", help="Explicitly migrate legacy managed policy sections to the current version.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing any files.")
    return parser.parse_args()


def main() -> int:
    global DRY_RUN
    args = parse_args()
    DRY_RUN = args.dry_run
    stamp = today()

    try:
        features = preflight_features(args.feature)
        root = Path(args.project_root).expanduser().resolve()
        if root.exists() and not root.is_dir():
            raise ValueError(f"--project-root must be a directory: {str(root)!r}")

        memory_dir, memory_dir_label = project_local_path(
            root, args.memory_dir, "--memory-dir"
        )
        agents_path, _ = project_local_path(root, args.agents_file, "--agents-file")
        if memory_dir.exists() and not memory_dir.is_dir():
            raise ValueError(
                f"--memory-dir must resolve to a directory: {str(memory_dir)!r}"
            )

        features_dir = resolve_within_project(
            memory_dir / "features", root, "memory features directory"
        )
        if features_dir.exists() and not features_dir.is_dir():
            raise ValueError(
                f"memory features path must be a directory: {str(features_dir)!r}"
            )

        index_path = memory_dir / "index.md"
        memory_targets = [
            (index_path, "memory index"),
            (memory_dir / "project-memory.md", "project memory"),
            (memory_dir / "feature-registry.md", "feature registry"),
            (memory_dir / "decision-log.md", "decision log"),
            (features_dir / "_template.md", "feature capsule template"),
            (memory_dir / "context-budget.json", "context budget"),
        ]
        registry_path = memory_dir / "feature-registry.md"
        registry_for_planning = ensure_table(
            read_text(registry_path),
            FEATURE_REGISTRY_HEADER,
            FEATURE_REGISTRY_DIVIDER,
        )
        feature_plans = plan_features(registry_for_planning, features)
        memory_targets.extend(
            (memory_dir / pointer, f"feature capsule {feature_name!r}")
            for feature_name, pointer, _should_register in feature_plans
        )
        preflight_output_paths(root, memory_targets)

        agents_has_workflow = False
        if args.upgrade:
            existing_agents_text = read_text(agents_path)
            agents_has_workflow = any(
                line == AGENTS_SECTION_TITLE
                for _line_number, line in markdown_structure_lines(
                    existing_agents_text
                )
            )
        manage_agents = args.agents or agents_has_workflow
        prepared_agents: str | None = None
        if manage_agents:
            preflight_output_paths(root, [(agents_path, "--agents-file")])
            if is_within(agents_path, memory_dir) or is_within(
                memory_dir, agents_path
            ):
                raise ValueError(
                    "--agents-file must not be inside, equal to, or contain "
                    "--memory-dir"
                )
            resolved_memory_targets = {
                resolve_within_project(path, root, label)
                for path, label in memory_targets
            }
            if agents_path in resolved_memory_targets:
                raise ValueError(
                    "--agents-file must not overlap a generated memory scaffold file"
                )

        prepared_index = prepare_index_text(index_path, stamp, args.upgrade)
        if manage_agents:
            prepared_agents = prepare_agents_text(
                agents_path, memory_dir_label, args.upgrade
            )

    except (OSError, RuntimeError, ValueError) as exc:
        print(f"bootstrap_memory.py: error: {exc}", file=sys.stderr)
        return 2

    changes: list[str] = []

    write_changed(index_path, prepared_index, changes, str(index_path))
    ensure_file(memory_dir / "project-memory.md", project_memory_template(stamp), stamp, changes, str(memory_dir / "project-memory.md"))
    ensure_feature_registry(registry_path, feature_plans, stamp, changes)
    ensure_decision_log(memory_dir / "decision-log.md", stamp, changes)
    ensure_capsule(
        features_dir / "_template.md",
        "Feature Capsule Template",
        stamp,
        changes,
    )
    if not (memory_dir / "context-budget.json").exists():
        write_changed(
            memory_dir / "context-budget.json",
            context_budget_template(stamp),
            changes,
            str(memory_dir / "context-budget.json"),
        )

    for feature_name, pointer, _should_register in feature_plans:
        ensure_capsule(
            memory_dir / pointer,
            feature_name,
            stamp,
            changes,
        )

    if manage_agents and prepared_agents is not None:
        write_changed(agents_path, prepared_agents, changes, str(agents_path))

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
