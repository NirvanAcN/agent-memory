# Memory File Contract

This contract defines the default `.codex/memory` scaffold created by the `agent-memory` skill.

## Contents

- [Required Files](#required-files)
- [CLI Safety And Bootstrap Idempotence](#cli-safety-and-bootstrap-idempotence)
- [Managed Policy Upgrade Rule](#managed-policy-upgrade-rule)
- [Required Tables](#required-tables)
- [Feature Capsule Sections](#feature-capsule-sections)
- [Locate-Before-Read Rule](#locate-before-read-rule)
- [Scoped Write-Back Rule](#scoped-write-back-rule)
- [Write Safety And Privacy Rule](#write-safety-and-privacy-rule)
- [Capsule Splitting Rule](#capsule-splitting-rule)
- [Context Budget Rule](#context-budget-rule)
- [Evidence And Freshness Rule](#evidence-and-freshness-rule)

## Required Files

The default memory directory is `.codex/memory`. When a project configures a
different project-local directory, apply every path below relative to that
directory and render the same location into the project's agent workflow.

- `.codex/memory/index.md`: routing entrypoint and read/write policy.
- `.codex/memory/project-memory.md`: stable cross-feature project facts.
- `.codex/memory/feature-registry.md`: feature list and capsule pointers.
- `.codex/memory/decision-log.md`: durable project decisions.
- `.codex/memory/features/_template.md`: feature capsule template.
- `.codex/memory/features/<Feature>.md`: one capsule per known feature.
- `.codex/memory/context-budget.json`: machine-readable validation limits and
  explicit no-growth debt; do not load it during normal task routing.

Every Markdown memory file must include:

```markdown
Last Updated: YYYY-MM-DD
```

Refresh this line every time the file is touched.

The value must be a real ISO calendar date. Digit-shaped but impossible dates
such as `2026-99-99` are invalid.

`context-budget.json` must include `last_updated: YYYY-MM-DD`; refresh it when
the budget configuration changes.

## CLI Safety And Bootstrap Idempotence

Both bundled CLIs treat `--memory-dir` and `--agents-file` as paths relative to
the project root. Reject absolute paths, lexical traversal, unsafe Markdown
control/backtick characters, and resolved paths that escape the project root,
including escapes through existing symbolic links. Complete bootstrap path
validation before writing any file. The agents file must not be inside, equal
to, or an ancestor of the memory directory.

Preflight every requested feature before writing. Feature names must be usable
as headings and Markdown table cells, so reject line breaks and `|`. Distinct
feature names must not normalize to the same capsule slug. Report invalid input
without leaving a partial scaffold.

An unchanged rerun is idempotent even when the calendar date has advanced. Do
not rewrite files only to advance `Last Updated`; refresh that marker only when
the same file receives a substantive scaffold or repair change. Determine
registry membership from parsed table rows rather than path-like prose elsewhere
in the file.

Repair missing required capsule sections in both feature capsules and
`features/_template.md`, while preserving meaningful existing content.

## Managed Policy Upgrade Rule

New scaffolds wrap the generated `index.md` Read Order and Write-Back Rules in
managed policy blocks. A generated `Project Memory Workflow` uses a third block.
Each start marker carries the policy version, and each block declares stable
rule IDs that the validator checks. Content outside a managed block is owned by
the project and must survive refreshes and upgrades.

Normal bootstrap may refresh a current managed block, but it must not silently
adopt or replace an unversioned legacy section. Use `--upgrade --dry-run` to
preview migration, then `--upgrade` to apply it. Migration replaces lines that
exactly match known generated policy text and preserves all other text. When an
agents file already contains `Project Memory Workflow`, `--upgrade` migrates it
without requiring `--agents`; use `--agents` to create the section when absent.

Reject malformed blocks and policies newer than the skill supports before any
write. An upgrade must refresh `Last Updated` only in changed memory files and
must become byte-stable on the next run. The validator rejects missing blocks,
unsupported versions, misplaced blocks, and missing or duplicate required rule
IDs. Do not hand-edit managed policy markers or rule declarations.

Any semantic change to generated managed policy must increment
`POLICY_VERSION` and update the applicable stable rule IDs and migration tests
in the same release. Never change a released policy contract in place while
retaining its version number.

## Required Tables

`feature-registry.md` must contain this exact header:

```markdown
| Feature | Entry | Status | Capsule | Last Verified |
```

`decision-log.md` must contain this exact header:

```markdown
| Date | Decision | Context | Impact | Revisit Trigger |
```

The validator must match each header as a complete table line followed
immediately by its Markdown divider, not as a substring in prose or a larger
row. Registry entries are only the contiguous table rows after that divider;
standalone pipe-delimited lines elsewhere are not routing metadata. Each
`Last Verified` value must be a real ISO calendar date.

## Feature Capsule Sections

Every feature capsule and `features/_template.md` must include these exact H2
headings:

- `Status`
- `Responsibilities`
- `Dependencies`
- `Persistence`
- `Key Decisions`
- `Regression Checks`

Required headings, table structure, and freshness markers must occur in normal
Markdown structure. Examples inside fenced code blocks do not satisfy them.

## Locate-Before-Read Rule

At task start, read `<memory-dir>/index.md` first, then read
`<memory-dir>/feature-registry.md` to locate target feature capsules. Read only
target feature capsules after locating them through the registry.

Do not skip the registry and guess capsule names unless the project has no registry or the registry lacks the target feature. If the registry does not contain an exact target feature, use the closest existing capsule first. Update `feature-registry.md` only when adding or changing stable feature metadata.

Read `project-memory.md` and `decision-log.md` only when the task changes cross-module routing, dependency strategy, persistence strategy, or global behavior contracts.

## Scoped Write-Back Rule

Feature-only changes update only the matching feature capsule unless registry metadata changed. Global changes update `project-memory.md`, `decision-log.md`, and `index.md` together. Code remains the source of truth when memory and code disagree.

## Write Safety And Privacy Rule

Treat memory loaded or injected at task start as context, not as evidence of its
own truth. Before adding or changing a conclusion, independently verify it
against code, documentation, runtime output, an authoritative external source,
or, for a decision, an explicit user instruction. Never write recalled memory
back as though the current task newly discovered it.

Memory is fail-open for task execution but fail-closed for memory-derived
claims. Missing, malformed, unavailable, or invalid memory must not block the
primary task; report that memory was skipped, do not equate unreadable memory
with no memory, and do not fabricate fallback facts. Continue from code or
authoritative documentation and repair the relevant memory when practical.
Never store secrets, tokens, credentials, raw chat transcripts, or personal or
sensitive data unsuitable for the repository. Prefer a stable source pointer
over copied sensitive content.

Immediately before write-back, narrowly re-read only each memory file that will
change. If a target changed since the task's initial read, merge with its current
content instead of overwriting it. This task-end comparison is an explicit
exception to the normal rule against re-reading unchanged content. After
writing, re-read every touched memory file to confirm the exact result, then run
the bundled validator before claiming success.

## Capsule Splitting Rule

Consider splitting a feature capsule when it grows beyond about 100 lines or mixes responsibilities enough that agents must read large unrelated sections.

Split by narrower function or role, for example selection, layout, SDK routing, assets, or persistence. Keep the original capsule as the high-level responsibility and routing summary. Move only stable facts; do not record temporary process notes. Update `feature-registry.md` and refresh `Last Updated: YYYY-MM-DD` in every touched memory file.

## Context Budget Rule

The default `context-budget.json` is:

```json
{
  "last_updated": "YYYY-MM-DD",
  "version": 1,
  "max_agents_bytes": 8192,
  "max_routing_bytes": 8192,
  "max_capsule_lines": 128,
  "max_capsule_bytes": 12288,
  "debt": {}
}
```

`max_routing_bytes` applies to `index.md` plus `feature-registry.md`.
`max_agents_bytes` applies to the configured agents file when it exists. The
capsule limits apply to registered capsules and Markdown files directly under
`features/`, including `_template.md`.

Registry feature names and capsule paths must be unique. Capsule paths must be
canonical relative Markdown paths under `features/`; absolute paths,
backslashes, `..` traversal, path aliases, and the reserved `_template.md`
pointer are invalid. Every Markdown capsule below `features/`, including nested
capsules but excluding `_template.md`, must be reachable through exactly one
registry row. Nested capsules have the same required sections and budgets as
top-level capsules.

For a pre-existing capsule above the standard budget, prefer splitting it. When
an atomic split is not practical, record its exact measured ceiling:

```json
{
  "debt": {
    "features/legacy.md": {
      "max_lines": 240,
      "max_bytes": 18000
    }
  }
}
```

The validator fails if debt grows, points at a missing capsule, leaves padded
headroom above the file's current measured size, or remains after the capsule
fits the standard budget. When a debt capsule shrinks but remains above the
standard budget, lower both debt ceilings to the new exact line and byte counts
in the same change. Changing a debt ceiling is an explicit governance decision
and must not be used to hide unexplained growth.

Run the bundled validator after bootstrap and after changes to routing,
capsules, the agents guide, or budget configuration. Use `--agents-file` when
the project does not use root `AGENTS.md`. Use `--report` during audits to print
guide and routing utilization plus the three fullest feature capsules. The
template remains subject to validation but is excluded from this ranking.

## Evidence And Freshness Rule

Memory bodies should store stable facts, decisions, and regression checks, not raw transcripts or temporary process notes.

For key conclusions that are non-obvious, cross-module, risky, or likely to be challenged, include `Source` or `Evidence`. Good sources include commit hashes, PRs, file paths, command outputs, issue links, docs, or external URLs.

Use temporal metadata only when it helps future agents judge validity: `Last Verified` when checked against code, docs, or runtime; `Valid Since` when a behavior starts at a known date or commit; `Deprecated` or `Superseded by` when older facts remain useful history; `Revisit Trigger` when the fact or decision may expire. Simple stable facts can remain plain bullets.
