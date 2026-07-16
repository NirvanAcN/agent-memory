# Memory File Contract

This contract defines the default `.codex/memory` scaffold created by the `agent-memory` skill.

## Required Files

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

`context-budget.json` must include `last_updated: YYYY-MM-DD`; refresh it when
the budget configuration changes.

## Required Tables

`feature-registry.md` must contain this exact header:

```markdown
| Feature | Entry | Status | Capsule | Last Verified |
```

`decision-log.md` must contain this exact header:

```markdown
| Date | Decision | Context | Impact | Revisit Trigger |
```

## Feature Capsule Sections

Every feature capsule must include:

- `Status`
- `Responsibilities`
- `Dependencies`
- `Persistence`
- `Key Decisions`
- `Regression Checks`

## Locate-Before-Read Rule

At task start, read `index.md` first, then read `feature-registry.md` to locate target feature capsules. Read only target feature capsules after locating them through the registry.

Do not skip the registry and guess capsule names unless the project has no registry or the registry lacks the target feature. If the registry does not contain an exact target feature, use the closest existing capsule first. Update `feature-registry.md` only when adding or changing stable feature metadata.

Read `project-memory.md` and `decision-log.md` only when the task changes cross-module routing, dependency strategy, persistence strategy, or global behavior contracts.

## Scoped Write-Back Rule

Feature-only changes update only the matching feature capsule unless registry metadata changed. Global changes update `project-memory.md`, `decision-log.md`, and `index.md` together. Code remains the source of truth when memory and code disagree.

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
relative Markdown paths contained by the memory root; absolute paths,
backslashes, and `..` traversal are invalid.

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

The validator fails if debt grows, points at a missing capsule, or remains after
the capsule fits the standard budget. Changing a debt ceiling is an explicit
governance decision and must not be used to hide unexplained growth.

Run the bundled validator after bootstrap and after changes to routing,
capsules, the agents guide, or budget configuration. Use `--agents-file` when
the project does not use root `AGENTS.md`.

## Evidence And Freshness Rule

Memory bodies should store stable facts, decisions, and regression checks, not raw transcripts or temporary process notes.

For key conclusions that are non-obvious, cross-module, risky, or likely to be challenged, include `Source` or `Evidence`. Good sources include commit hashes, PRs, file paths, command outputs, issue links, docs, or external URLs.

Use temporal metadata only when it helps future agents judge validity: `Last Verified` when checked against code, docs, or runtime; `Valid Since` when a behavior starts at a known date or commit; `Deprecated` or `Superseded by` when older facts remain useful history; `Revisit Trigger` when the fact or decision may expire. Simple stable facts can remain plain bullets.
