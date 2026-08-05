---
name: agent-memory
description: Create, upgrade, audit, and maintain bounded project-local agent memory systems. Use when a user asks to bootstrap `.codex/memory` (or a custom memory directory), migrate legacy policy blocks, govern agent context growth, enforce measurable guide/routing/capsule budgets, migrate oversized memory into no-growth debt, enforce minimum-read/scoped-write-back rules, add Project Memory Workflow guidance to AGENTS.md, or update project memory files after a task.
---

# Agent Memory

## Core Workflow

Use this skill to create or maintain a project-local memory system (`<memory-dir>`,
default `.codex/memory`) that agents can update over time without reading the
whole codebase. Custom memory directories must remain inside the project root.

Before bootstrapping memory:

1. Read existing `agents.md`, `AGENTS.md`, or `.codex/agents.md` if present.
2. Do not read engineering source files unless the user explicitly allows it.
3. Prefer facts already provided by the user, existing memory files, and high-level repo metadata.
4. If the user asks for strict minimum-read behavior, treat code inspection as out of scope.

For normal task work in a repo that already has this memory system, resolve the
configured memory directory from the project's agent guide or the current task;
use `.codex/memory` only when no custom location is configured:

1. Read `<memory-dir>/index.md` first.
2. Read `<memory-dir>/feature-registry.md` to locate the relevant capsule(s).
3. Read only the target `<memory-dir>/features/<Feature>.md` capsule(s).
4. Read `project-memory.md` and `decision-log.md` only for cross-module routing, dependency strategy, persistence strategy, or global behavior contracts.
5. After the task, update the smallest applicable memory scope.
6. Refresh `Last Updated: YYYY-MM-DD` in every memory file touched.

Do not skip the registry and guess capsule names unless the project has no registry or the registry lacks the target feature. If the registry does not contain an exact target feature, use the closest existing capsule first. Update `feature-registry.md` only when adding or changing stable feature metadata.

If memory conflicts with code, code is the source of truth. Fix the memory in the same task when the user has allowed code inspection or the conflict is already proven.

## Bootstrap

Use the bundled script for deterministic skeleton creation:

```bash
python3 <skill-dir>/scripts/bootstrap_memory.py --project-root <path> \
  [--memory-dir <relative-path>] [--feature <name> ...] \
  [--agents] [--agents-file <relative-path>] [--upgrade] [--dry-run]
```

Defaults:

- `--project-root` defaults to the current working directory.
- No `--feature` arguments creates only shared memory files plus `features/_template.md`.
- `--agents` creates the `Project Memory Workflow` section when absent or
  refreshes its current managed policy block while preserving content outside it.
- `--upgrade` explicitly migrates an unversioned or older `index.md` policy and
  any existing `Project Memory Workflow` section to the current managed policy
  version. Preview with `--upgrade --dry-run`; never downgrade a newer policy.
- `--memory-dir` and `--agents-file` must resolve inside the project root. A
  custom memory directory is propagated into the generated agent workflow;
  unsafe Markdown path characters are rejected before use.
- Feature inputs are validated before writes; unusable names, Markdown table
  delimiters, and distinct names that resolve to the same capsule slug fail
  without leaving a partial scaffold.
- New scaffolds include versioned managed policy blocks with stable rule IDs,
  plus `context-budget.json`; the latter is validator configuration, not part of
  the agent's normal read path.
- Bundled scripts require Python 3.7 or newer and use only the standard library
  at runtime.

The script is idempotent across dates. It creates missing files, repairs required
table headers and capsule sections, and avoids overwriting meaningful
human-authored memory content. Existing unversioned policies require explicit
`--upgrade`; migration replaces known generated lines and preserves other text as
project-owned content. It refreshes `Last Updated` only in files with a
substantive scaffold or repair change; an unchanged rerun reports `No changes.`.
When generated policy semantics change, increment `POLICY_VERSION` and update
the stable rule IDs and migration tests in the same change. Do not alter a
released policy contract in place while retaining its version.

## Context Budget

Validate the memory tree after bootstrap and after memory-policy or capsule changes:

```bash
python3 <skill-dir>/scripts/validate_memory.py --project-root <path> [--memory-dir <relative-path>]
python3 <skill-dir>/scripts/validate_memory.py --project-root <path> [--memory-dir <relative-path>] --report
```

Use `--report` during audits to show guide and routing utilization plus the
three fullest feature capsules without loading every capsule into the agent
context. The template remains validated but does not consume a ranking slot.

The generated defaults cap the agents guide and index-plus-registry route at 8
KiB each, and standard capsules at 128 lines and 12 KiB. Projects may change
these values in `context-budget.json` when they have a documented reason.

Validation also requires the current managed policy version and required rule
IDs in `index.md`, and in the agents workflow when that section exists. Use the
explicit upgrade path rather than manually changing version markers.

For an existing tree, create the config by re-running bootstrap, then validate.
Split oversized capsules first. If an oversized capsule cannot be migrated in
one change, add its exact current line and byte counts to the `debt` map. Debt
may shrink but must not grow: whenever the file shrinks, lower both recorded
ceilings to its new measured size. Remove the entry after the capsule fits the
standard budget. Never pad or raise a debt ceiling merely to make unexplained
growth pass validation.

Every Markdown capsule under `features/`, except `_template.md`, must have one
unique row in `feature-registry.md`. Nested capsules are allowed, but they are
subject to the same required sections and context budgets as top-level
capsules.

## Write-Back Rules

Use the smallest write scope that captures stable facts and decisions:

- Feature-only change: update only `<memory-dir>/features/<Feature>.md`; update `feature-registry.md` only when feature metadata changes.
- Global change: update `project-memory.md`, `decision-log.md`, and `index.md` in the same change set.
- Registry change: keep `feature-registry.md` aligned when adding, renaming, splitting, merging, or retiring features.
- Registry integrity: do not leave unregistered Markdown capsules under `features/`; each capsule must be reachable through one unique registry row.
- Capsule splitting: when a capsule grows beyond about 100 lines or mixes responsibilities enough that agents must read large unrelated sections, split it into narrower capsules by function or role such as selection, layout, SDK routing, assets, or persistence. Keep the original capsule as the high-level responsibility and routing summary. Move only stable facts, refresh every touched `Last Updated`, and update `feature-registry.md`.
- Evidence and freshness: keep memory body focused on stable facts, decisions, and regression checks. Add `Source` or `Evidence` for key conclusions that are non-obvious, cross-module, risky, or likely to be challenged. Use `Last Verified`, `Valid Since`, `Deprecated`, `Superseded by`, and `Revisit Trigger` when time validity matters; simple stable facts do not need metadata on every bullet.
- Verification before write: treat memory loaded or injected at task start as context, not as evidence of its own truth. Independently verify every new or changed conclusion against code, documentation, runtime output, an authoritative external source, or, for a decision, an explicit user instruction before writing it back. Never persist recalled memory as though the task newly discovered it.
- Fail open and protect privacy: missing, malformed, unavailable, or invalid memory must not block the primary task. Fail open for task execution but fail closed for memory-derived claims: report that memory was skipped, do not equate unreadable memory with no memory, and do not fabricate fallback facts. Continue from code or authoritative documentation, then repair the relevant memory when practical. Never store secrets, tokens, credentials, raw chat transcripts, or personal or sensitive data unsuitable for the repository; prefer a stable source pointer over copied sensitive content.
- Compare before write: immediately before write-back, narrowly re-read only each memory file that will change. If a target changed since the task's initial read, merge with its current content instead of overwriting it. This task-end check is an explicit exception to the normal no-re-read rule. After writing, re-read each touched memory file to confirm the exact result before claiming success.
- Do not store temporary execution steps, transient errors, or chat narration in memory.
- Run `<skill-dir>/scripts/validate_memory.py` after bootstrap and every memory write-back.

For exact file contracts, budget schema, migration rules, required headings,
and table headers, read `references/memory-file-contract.md`.
