---
name: agent-memory
description: Create and maintain project-local agent memory systems. Use when a user asks to bootstrap `.codex/memory` (or a custom memory directory), create a sustainable agent memory architecture, enforce minimum-read/scoped-write-back rules, add Project Memory Workflow guidance to AGENTS.md, or update project memory files after a task.
---

# Agent Memory

## Core Workflow

Use this skill to create or maintain a project-local memory system (default `.codex/memory`, configurable via the bundled script's `--memory-dir`) that agents can update over time without reading the whole codebase.

Before bootstrapping memory:

1. Read existing `agents.md`, `AGENTS.md`, or `.codex/agents.md` if present.
2. Do not read engineering source files unless the user explicitly allows it.
3. Prefer facts already provided by the user, existing memory files, and high-level repo metadata.
4. If the user asks for strict minimum-read behavior, treat code inspection as out of scope.

For normal task work in a repo that already has this memory system:

1. Read `.codex/memory/index.md` first.
2. Read `.codex/memory/feature-registry.md` to locate the relevant capsule(s).
3. Read only the target `.codex/memory/features/<Feature>.md` capsule(s).
4. Read `project-memory.md` and `decision-log.md` only for cross-module routing, dependency strategy, persistence strategy, or global behavior contracts.
5. After the task, update the smallest applicable memory scope.
6. Refresh `Last Updated: YYYY-MM-DD` in every memory file touched.

Do not skip the registry and guess capsule names unless the project has no registry or the registry lacks the target feature. If the registry does not contain an exact target feature, use the closest existing capsule first. Update `feature-registry.md` only when adding or changing stable feature metadata.

If memory conflicts with code, code is the source of truth. Fix the memory in the same task when the user has allowed code inspection or the conflict is already proven.

## Bootstrap

Use the bundled script for deterministic skeleton creation:

```bash
python3 scripts/bootstrap_memory.py --project-root <path> --feature <name> [--feature <name> ...] [--agents]
```

Defaults:

- `--project-root` defaults to the current working directory.
- No `--feature` arguments creates only shared memory files plus `features/_template.md`.
- `--agents` creates or refreshes the `Project Memory Workflow` section in `AGENTS.md`.

The script is idempotent. It creates missing files, refreshes freshness markers, ensures required table headers/sections exist, and avoids overwriting existing human-authored memory content.

## Write-Back Rules

Use the smallest write scope that captures stable facts and decisions:

- Feature-only change: update only `.codex/memory/features/<Feature>.md`; update `feature-registry.md` only when feature metadata changes.
- Global change: update `project-memory.md`, `decision-log.md`, and `index.md` in the same change set.
- Registry change: keep `feature-registry.md` aligned when adding, renaming, splitting, merging, or retiring features.
- Capsule splitting: when a capsule grows beyond about 100 lines or mixes responsibilities enough that agents must read large unrelated sections, split it into narrower capsules by function or role such as selection, layout, SDK routing, assets, or persistence. Keep the original capsule as the high-level responsibility and routing summary. Move only stable facts, refresh every touched `Last Updated`, and update `feature-registry.md`.
- Evidence and freshness: keep memory body focused on stable facts, decisions, and regression checks. Add `Source` or `Evidence` for key conclusions that are non-obvious, cross-module, risky, or likely to be challenged. Use `Last Verified`, `Valid Since`, `Deprecated`, `Superseded by`, and `Revisit Trigger` when time validity matters; simple stable facts do not need metadata on every bullet.
- Do not store temporary execution steps, transient errors, or chat narration in memory.

For exact file contracts, required headings, and table headers, read `references/memory-file-contract.md`.
