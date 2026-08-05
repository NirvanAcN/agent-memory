#!/usr/bin/env python3
"""Validate a project-local memory tree against the memory file contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from pathlib import PurePosixPath

FEATURE_REGISTRY_HEADER = "| Feature | Entry | Status | Capsule | Last Verified |"
FEATURE_REGISTRY_DIVIDER = "| --- | --- | --- | --- | --- |"
DECISION_LOG_HEADER = "| Date | Decision | Context | Impact | Revisit Trigger |"
DECISION_LOG_DIVIDER = "| --- | --- | --- | --- | --- |"
LAST_UPDATED_PREFIX = "Last Updated:"
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
POLICY_VERSION = 1
INDEX_READ_POLICY_ID = "index-read-order"
INDEX_WRITE_POLICY_ID = "index-write-back"
AGENTS_POLICY_ID = "project-memory-workflow"
AGENTS_SECTION_TITLE = "## Project Memory Workflow"
INDEX_READ_RULE_IDS = {
    "locate-before-read",
    "minimum-read",
    "global-read-scope",
}
INDEX_WRITE_RULE_IDS = {
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
}
AGENTS_RULE_IDS = INDEX_READ_RULE_IDS | INDEX_WRITE_RULE_IDS
POLICY_START_RE = re.compile(
    r"^<!-- agent-memory:policy-start id=([a-z0-9-]+) version=([1-9][0-9]*) -->$"
)
POLICY_RULES_RE = re.compile(
    r"^<!-- agent-memory:policy-rules ([a-z0-9-]+(?: [a-z0-9-]+)*) -->$"
)

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


def is_iso_calendar_date(value: object) -> bool:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


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


def h2_section_bounds(
    text: str, heading: str, label: str, errors: list[str]
) -> tuple[int, int] | None:
    structural = markdown_structure_lines(text)
    matches = [line_number for line_number, line in structural if line == heading]
    if not matches:
        errors.append(f"{label}: missing required policy section '{heading}'")
        return None
    if len(matches) > 1:
        errors.append(
            f"{label}: duplicate policy section '{heading}' at lines "
            + ", ".join(str(line_number) for line_number in matches)
        )
        return None

    start = matches[0]
    end = len(text.splitlines()) + 1
    for line_number, line in structural:
        if line_number > start and line.startswith("## "):
            end = line_number
            break
    return start, end


def validate_policy_block(
    label: str,
    text: str,
    *,
    heading: str,
    block_id: str,
    required_rule_ids: set[str],
    errors: list[str],
) -> None:
    bounds = h2_section_bounds(text, heading, label, errors)
    structural = markdown_structure_lines(text)
    starts: list[tuple[int, int]] = []
    ends: list[int] = []
    start_prefix = f"<!-- agent-memory:policy-start id={block_id} "
    end_marker = f"<!-- agent-memory:policy-end id={block_id} -->"

    for line_number, line in structural:
        if line.startswith(start_prefix):
            match = POLICY_START_RE.fullmatch(line)
            if match is None or match.group(1) != block_id:
                errors.append(
                    f"{label}:{line_number}: malformed policy start for '{block_id}'"
                )
                continue
            starts.append((line_number, int(match.group(2))))
        if line == end_marker:
            ends.append(line_number)

    if len(starts) != 1 or len(ends) != 1:
        errors.append(
            f"{label}: policy block '{block_id}' requires exactly one start and end marker"
        )
        return

    start_line, version = starts[0]
    end_line = ends[0]
    if end_line <= start_line:
        errors.append(f"{label}: policy block '{block_id}' has out-of-order markers")
        return
    if bounds is not None and not (
        bounds[0] < start_line < end_line < bounds[1]
    ):
        errors.append(
            f"{label}: policy block '{block_id}' must be inside section '{heading}'"
        )
    if version != POLICY_VERSION:
        errors.append(
            f"{label}: policy block '{block_id}' uses version {version}; "
            f"expected {POLICY_VERSION}; run bootstrap_memory.py --upgrade"
        )

    rules_markers: list[tuple[int, list[str]]] = []
    for line_number, line in structural:
        if not (start_line < line_number < end_line):
            continue
        if not line.startswith("<!-- agent-memory:policy-rules"):
            continue
        match = POLICY_RULES_RE.fullmatch(line)
        if match is None:
            errors.append(
                f"{label}:{line_number}: malformed policy rule marker in '{block_id}'"
            )
            continue
        rules_markers.append((line_number, match.group(1).split()))

    if len(rules_markers) != 1:
        errors.append(
            f"{label}: policy block '{block_id}' requires exactly one policy-rules marker"
        )
        return
    marker_line, rule_ids = rules_markers[0]
    duplicate_ids = sorted(
        rule_id for rule_id, count in Counter(rule_ids).items() if count > 1
    )
    if duplicate_ids:
        errors.append(
            f"{label}:{marker_line}: duplicate policy rule IDs in '{block_id}': "
            + ", ".join(duplicate_ids)
        )
    missing = sorted(required_rule_ids - set(rule_ids))
    if missing:
        errors.append(
            f"{label}:{marker_line}: policy block '{block_id}' is missing rule IDs: "
            + ", ".join(missing)
        )


def validate_last_updated(relative: str, text: str, errors: list[str]) -> None:
    markers: list[tuple[int, str]] = []
    for line_number, line in markdown_structure_lines(text):
        if line.startswith(LAST_UPDATED_PREFIX):
            markers.append(
                (line_number, line[len(LAST_UPDATED_PREFIX) :].strip(" \t"))
            )

    if not markers:
        errors.append(
            f"{relative}: missing required field 'Last Updated: YYYY-MM-DD'"
        )
        return

    if len(markers) > 1:
        line_numbers = ", ".join(str(line_number) for line_number, _value in markers)
        errors.append(
            f"{relative}: duplicate 'Last Updated' fields at lines {line_numbers}; "
            "expected exactly one"
        )

    for line_number, value in markers:
        if not is_iso_calendar_date(value):
            errors.append(
                f"{relative}:{line_number}: field 'Last Updated' must be a real "
                f"ISO calendar date in YYYY-MM-DD format; got {value!r}"
            )


def markdown_table_layout(
    text: str, header: str, divider: str
) -> tuple[list[int], bool, list[tuple[int, str]]]:
    structural = dict(markdown_structure_lines(text))
    header_lines = [
        line_number for line_number, line in structural.items() if line == header
    ]
    if not header_lines:
        return [], False, []

    header_line = header_lines[0]
    divider_present = structural.get(header_line + 1) == divider
    if not divider_present:
        return header_lines, False, []

    rows: list[tuple[int, str]] = []
    line_number = header_line + 2
    while line_number in structural:
        line = structural[line_number]
        if not line.startswith("|"):
            break
        rows.append((line_number, line))
        line_number += 1
    return header_lines, True, rows


def parse_registry(path: Path, errors: list[str]) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    text = path.read_text(encoding="utf-8")
    _headers, _divider_present, rows = markdown_table_layout(
        text, FEATURE_REGISTRY_HEADER, FEATURE_REGISTRY_DIVIDER
    )
    for line_number, line in rows:
        if line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 5:
            errors.append(f"feature-registry.md:{line_number}: malformed table row")
            continue
        feature = cells[0]
        pointer = cells[3].strip("`")
        last_verified = cells[4].strip("`")
        relative = PurePosixPath(pointer)
        if not feature:
            errors.append(f"feature-registry.md:{line_number}: empty feature name")
            continue
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
        if relative.as_posix() != pointer:
            errors.append(
                f"feature-registry.md:{line_number}: non-canonical capsule path "
                f"'{pointer}'"
            )
            continue
        if len(relative.parts) < 2 or relative.parts[0] != "features":
            errors.append(
                f"feature-registry.md:{line_number}: capsule path must be under "
                f"features/ ('{pointer}')"
            )
            continue
        if pointer == "features/_template.md":
            errors.append(
                f"feature-registry.md:{line_number}: reserved capsule path '{pointer}'"
            )
            continue
        if not is_iso_calendar_date(last_verified):
            errors.append(
                f"feature-registry.md:{line_number}: Last Verified must be a real "
                f"ISO calendar date; got {last_verified!r}"
            )
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

    last_updated = config.get("last_updated")
    if not is_iso_calendar_date(last_updated):
        errors.append(
            "context-budget.json: field 'last_updated' must be a real ISO calendar "
            f"date in YYYY-MM-DD format; got {last_updated!r}"
        )

    debt = config.get("debt")
    if not isinstance(debt, dict):
        errors.append("context-budget.json: 'debt' must be an object")
        return None
    for pointer, limits in debt.items():
        relative = PurePosixPath(pointer)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "\\" in pointer
            or relative.as_posix() != pointer
            or len(relative.parts) < 2
            or relative.parts[0] != "features"
        ):
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
    grew = False
    if line_count > max_lines:
        errors.append(f"{relative}: {line_count} lines exceeds context budget {max_lines}")
        grew = True
    if byte_count > max_bytes:
        errors.append(f"{relative}: {byte_count} bytes exceeds context budget {max_bytes}")
        grew = True
    if debt and not grew and (line_count != max_lines or byte_count != max_bytes):
        errors.append(
            f"context-budget.json: debt '{relative}' exceeds the current measured "
            f"size; lower it to max_lines={line_count}, max_bytes={byte_count}"
        )


def validate_capsule_structure(relative: str, path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    validate_last_updated(relative, text, errors)
    lines = {line for _line_number, line in markdown_structure_lines(text)}
    for section in CAPSULE_SECTIONS:
        heading = f"## {section}"
        if heading not in lines:
            errors.append(
                f"{relative}: missing required section '{heading}' "
                "(expected an exact Markdown H2 line)"
            )


def context_report(memory_dir: Path, agents_file: Path | None = None) -> list[str]:
    """Return a compact budget-usage report without changing validation state."""
    budget_errors: list[str] = []
    budget_path = memory_dir / "context-budget.json"
    if not budget_path.is_file():
        return ["Context budget usage: unavailable (missing context-budget.json)"]
    budget = load_context_budget(budget_path, budget_errors)
    if not budget:
        return ["Context budget usage: unavailable (invalid context-budget.json)"]

    lines = ["Context budget usage:"]
    if agents_file and agents_file.is_file():
        size = agents_file.stat().st_size
        limit = budget["max_agents_bytes"]
        lines.append(f"- Agents guide: {size}/{limit} bytes ({size / limit:.1%})")

    routing_paths = (memory_dir / "index.md", memory_dir / "feature-registry.md")
    if all(path.is_file() for path in routing_paths):
        size = sum(path.stat().st_size for path in routing_paths)
        limit = budget["max_routing_bytes"]
        lines.append(f"- Routing: {size}/{limit} bytes ({size / limit:.1%})")

    capsules: list[tuple[float, str, int, int, int, int]] = []
    features_dir = memory_dir / "features"
    if features_dir.is_dir():
        for capsule in sorted(features_dir.rglob("*.md")):
            relative = capsule.relative_to(memory_dir).as_posix()
            if relative == "features/_template.md":
                continue
            text = capsule.read_text(encoding="utf-8")
            line_count = len(text.splitlines())
            byte_count = len(text.encode("utf-8"))
            debt = budget["debt"].get(relative)
            max_lines = debt["max_lines"] if debt else budget["max_capsule_lines"]
            max_bytes = debt["max_bytes"] if debt else budget["max_capsule_bytes"]
            utilization = max(line_count / max_lines, byte_count / max_bytes)
            capsules.append(
                (utilization, relative, line_count, max_lines, byte_count, max_bytes)
            )

    file_label = "file" if len(capsules) == 1 else "files"
    lines.append(
        f"- Feature capsules: {len(capsules)} {file_label}, "
        f"{len(budget['debt'])} debt entries"
    )
    for _usage, relative, line_count, max_lines, byte_count, max_bytes in sorted(
        capsules, reverse=True
    )[:3]:
        lines.append(
            f"  - {relative}: {line_count}/{max_lines} lines, "
            f"{byte_count}/{max_bytes} bytes"
        )
    return lines


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
        validate_last_updated(rel, text, errors)

    index = memory_dir / "index.md"
    if index.is_file():
        index_text = index.read_text(encoding="utf-8")
        validate_policy_block(
            "index.md",
            index_text,
            heading="## Read Order",
            block_id=INDEX_READ_POLICY_ID,
            required_rule_ids=INDEX_READ_RULE_IDS,
            errors=errors,
        )
        validate_policy_block(
            "index.md",
            index_text,
            heading="## Write-Back Rules",
            block_id=INDEX_WRITE_POLICY_ID,
            required_rule_ids=INDEX_WRITE_RULE_IDS,
            errors=errors,
        )

    if agents_file and agents_file.is_file():
        agents_text = agents_file.read_text(encoding="utf-8")
        if any(
            line == AGENTS_SECTION_TITLE
            for _line_number, line in markdown_structure_lines(agents_text)
        ):
            validate_policy_block(
                agents_file.name,
                agents_text,
                heading=AGENTS_SECTION_TITLE,
                block_id=AGENTS_POLICY_ID,
                required_rule_ids=AGENTS_RULE_IDS,
                errors=errors,
            )

    registry = memory_dir / "feature-registry.md"
    entries: list[tuple[str, str]] = []
    if registry.is_file():
        registry_text = registry.read_text(encoding="utf-8")
        registry_headers, registry_divider, _registry_rows = markdown_table_layout(
            registry_text, FEATURE_REGISTRY_HEADER, FEATURE_REGISTRY_DIVIDER
        )
        if not registry_headers:
            errors.append(
                "feature-registry.md: missing required table header; expected exact "
                f"line '{FEATURE_REGISTRY_HEADER}'"
            )
        elif len(registry_headers) > 1:
            errors.append(
                "feature-registry.md: duplicate required table headers at lines "
                + ", ".join(str(line_number) for line_number in registry_headers)
            )
        if registry_headers and not registry_divider:
            errors.append(
                "feature-registry.md: missing required table divider immediately "
                f"after '{FEATURE_REGISTRY_HEADER}'"
            )
        entries = parse_registry(registry, errors)
        for _feature, pointer in entries:
            if not (memory_dir / pointer).is_file():
                errors.append(f"feature-registry.md: points at missing capsule '{pointer}'")

    decisions = memory_dir / "decision-log.md"
    if decisions.is_file():
        decision_text = decisions.read_text(encoding="utf-8")
        decision_headers, decision_divider, _decision_rows = markdown_table_layout(
            decision_text, DECISION_LOG_HEADER, DECISION_LOG_DIVIDER
        )
        if not decision_headers:
            errors.append(
                "decision-log.md: missing required table header; expected exact "
                f"line '{DECISION_LOG_HEADER}'"
            )
        elif len(decision_headers) > 1:
            errors.append(
                "decision-log.md: duplicate required table headers at lines "
                + ", ".join(str(line_number) for line_number in decision_headers)
            )
        if decision_headers and not decision_divider:
            errors.append(
                "decision-log.md: missing required table divider immediately "
                f"after '{DECISION_LOG_HEADER}'"
            )

    features_dir = memory_dir / "features"
    capsule_paths: dict[str, Path] = {}
    if features_dir.is_dir():
        for capsule in sorted(features_dir.rglob("*.md")):
            rel = capsule.relative_to(memory_dir).as_posix()
            capsule_paths[rel] = capsule
            validate_capsule_structure(rel, capsule, errors)

    registered_capsules = {pointer for _feature, pointer in entries}
    discovered_capsules = set(capsule_paths) - {"features/_template.md"}
    for orphan in sorted(discovered_capsules - registered_capsules):
        errors.append(
            f"{orphan}: capsule is not registered in feature-registry.md"
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


def is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def project_local_path(root: Path, value: str, option: str) -> Path:
    if not value:
        raise ValueError(f"{option} must not be empty")
    if "`" in value or any(not character.isprintable() for character in value):
        raise ValueError(f"{option} contains unsafe path characters")

    relative = Path(value).expanduser()
    if relative.is_absolute():
        raise ValueError(
            f"{option} must be relative to --project-root; got {value!r}"
        )
    if ".." in relative.parts:
        raise ValueError(f"{option} must not contain '..': {value!r}")

    resolved = (root / relative).resolve()
    if not is_within(resolved, root):
        raise ValueError(
            f"{option} resolves outside --project-root: {value!r} -> {str(resolved)!r}"
        )
    return resolved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a memory tree against the contract.")
    parser.add_argument("--project-root", default=".", help="Project root to validate. Defaults to cwd.")
    parser.add_argument("--memory-dir", default=".codex/memory", help="Memory directory relative to project root. Defaults to .codex/memory.")
    parser.add_argument(
        "--agents-file",
        default="AGENTS.md",
        help="Agents instructions file relative to project root. Defaults to AGENTS.md.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print context-budget utilization and the three fullest feature capsules.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        root = Path(args.project_root).expanduser().resolve()
        if root.exists() and not root.is_dir():
            raise ValueError(f"--project-root must be a directory: {str(root)!r}")
        memory_dir = project_local_path(root, args.memory_dir, "--memory-dir")
        agents_file = project_local_path(root, args.agents_file, "--agents-file")
        if is_within(agents_file, memory_dir) or is_within(memory_dir, agents_file):
            raise ValueError(
                "--agents-file must not be inside, equal to, or contain --memory-dir"
            )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"validate_memory.py: error: {exc}", file=sys.stderr)
        return 2

    errors = validate(memory_dir, agents_file)
    if args.report:
        for line in context_report(memory_dir, agents_file):
            print(line)
    if errors:
        print("Memory contract violations:")
        for item in errors:
            print(f"- {item}")
        return 1
    print("OK: memory tree satisfies the contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
