<div align="center">

# 🧠 Agent Memory

**A scoped, self-maintaining memory system for coding agents.**

Give your agent a long-term memory it can read selectively and update surgically
without re-reading the entire codebase on every task.

[Why](#why) · [How it works](#how-it-works) · [Quick start](#quick-start) · [Memory model](#memory-model) · [Rules](#the-rules) · [Development](#development)

</div>

---

## Why

Agents are great at solving tasks and terrible at remembering them. Each session
starts cold: the agent re-reads files, re-derives architecture, and re-learns
decisions it already made yesterday. That is slow, expensive, and inconsistent.

`agent-memory` is a [Codex](https://openai.com/index/introducing-codex/) skill that
bootstraps a **project-local `.codex/memory` system** with two strict guarantees:

- **Minimum read** — locate the relevant capsule through a registry, then read only that capsule.
- **Scoped write-back** — persist stable facts to the smallest applicable scope, never to everything.

The result is durable project knowledge that stays small, stays fresh, and never
turns into an unbounded log nobody trusts.

## How it works

```
  task starts
      │
      ▼
  index.md ──────────▶ read order + write-back policy
      │
      ▼
  feature-registry.md ─▶ locate the right capsule(s)
      │
      ▼
  features/<Feature>.md ─▶ read ONLY the target capsule
      │
      ▼
  do the work, then write back to the SMALLEST scope
```

Global context (`project-memory.md`, `decision-log.md`) is read **only** when a
task touches cross-module routing, dependencies, persistence, or global behavior
contracts. Everything else stays local to a single feature capsule.

## Quick start

Preview the scaffold without writing anything:

```bash
python3 scripts/bootstrap_memory.py --project-root . --feature "Search" --dry-run
```

Create the memory system for real:

```bash
python3 scripts/bootstrap_memory.py \
  --project-root . \
  --feature "Search" \
  --feature "Billing" \
  --agents
```

Validate an existing memory tree against the contract:

```bash
python3 scripts/validate_memory.py --project-root .
```

| Flag | Description |
| --- | --- |
| `--project-root` | Target project root. Defaults to the current directory. |
| `--feature` | Feature capsule to create and register. Repeatable. |
| `--agents` | Create or refresh the `Project Memory Workflow` section in `AGENTS.md`. |
| `--dry-run` | Report what would change without touching the filesystem. |

The bootstrap script is **idempotent**: it creates missing files, refreshes
freshness markers, ensures required headers and sections exist, and never
overwrites human-authored content.

## Memory model

```
.codex/memory/
├── index.md              # routing entrypoint + read/write policy
├── project-memory.md     # stable cross-feature project facts
├── feature-registry.md   # feature list → capsule pointers
├── decision-log.md       # durable project decisions
└── features/
    ├── _template.md      # capsule template
    └── <Feature>.md      # one capsule per feature
```

Every feature capsule carries a fixed shape so agents always know where to look:
`Status`, `Responsibilities`, `Dependencies`, `Persistence`, `Key Decisions`,
and `Regression Checks`. Every file tracks a `Last Updated: YYYY-MM-DD` marker
that is refreshed on every touch.

Full schema, required headers, and update semantics live in
[`references/memory-file-contract.md`](references/memory-file-contract.md).

## The rules

Three principles keep the memory trustworthy over time:

1. **Locate before read.** Always go `index → registry → capsule`. Never guess capsule names.
2. **Scope the write-back.** Feature-only changes touch one capsule; global changes update `project-memory.md`, `decision-log.md`, and `index.md` together.
3. **Code is the source of truth.** When memory and code disagree, fix the memory.

Capsules that grow past ~100 lines or mix unrelated responsibilities are split
by function or role, while the original capsule remains a high-level routing
summary. Non-obvious or risky conclusions carry `Source`/`Evidence`; time-sensitive
facts carry `Last Verified`, `Valid Since`, `Deprecated`, `Superseded by`, or
`Revisit Trigger`. Transient process notes never enter memory.

## Project layout

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Skill metadata and the agent-facing workflow. |
| `scripts/bootstrap_memory.py` | Idempotent memory scaffold generator. |
| `scripts/validate_memory.py` | Contract validator for an existing memory tree. |
| `scripts/test_memory.py` | Test suite for the scripts. |
| `references/memory-file-contract.md` | Authoritative file contract and update rules. |
| `agents/openai.yaml` | Codex UI metadata. |

## Development

Run the test suite:

```bash
python3 -m pytest scripts/test_memory.py
```

Requires **Python 3.9+** (uses standard-library typing generics). The scripts
have no runtime dependencies; `pytest` is needed only for tests.

## License

Released under the [MIT License](LICENSE).
