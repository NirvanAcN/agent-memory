<div align="center">

# 🧠 Agent Memory

**A scoped, self-maintaining memory system for coding agents.**

Give your agent a long-term memory it can read selectively and update surgically
without re-reading the entire codebase on every task.

**English** · [简体中文](README.zh-CN.md)

[Why](#why) · [How it works](#how-it-works) · [Install](#install) · [Usage](#usage) · [Memory model](#memory-model) · [Rules](#the-rules) · [Development](#development)

</div>

---

## Why

Agents are great at solving tasks and terrible at remembering them. Each session
starts cold: the agent re-reads files, re-derives architecture, and re-learns
decisions it already made yesterday. That is slow, expensive, and inconsistent.

`agent-memory` is an [Agent Skill](https://www.anthropic.com/news/skills) that
bootstraps a **project-local memory system** (default `.codex/memory`) with two
strict guarantees:

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

## Install

`agent-memory` is a standard [Agent Skill](https://www.anthropic.com/news/skills)
(a `SKILL.md` plus bundled scripts), so it works with any agent that supports the
skills format. Clone it into your agent's skills directory:

```bash
git clone https://github.com/NirvanAcN/agent-memory.git \
  <skills-dir>/agent-memory
```

| Agent | Skills directory |
| --- | --- |
| Codex | `~/.codex/skills/agent-memory` |
| Claude Code | `~/.claude/skills/agent-memory` |
| Other / project-scoped | `./.skills/agent-memory` or your tool's skills path |

## Usage

You don't run anything by hand. Once installed, ask your agent in natural
language; it loads the skill and runs the bundled scripts for you.

> Use **agent-memory** to bootstrap a memory system for this project, with
> features Search and Billing, and add the workflow to AGENTS.md.

The agent scaffolds the memory tree, registers the features, wires up the agents
file, and from then on reads and updates memory according to the
[contract](references/memory-file-contract.md).

### Default location

Memory is created under `.codex/memory` by default. If your agent uses another
convention, ask it to use a different directory (for example `.agent/memory`);
both bundled scripts accept `--memory-dir`.

### Manual / advanced invocation

The bundled scripts are an implementation detail the agent calls, but you can run
them directly to debug or to script CI. Preview without writing:

```bash
python3 scripts/bootstrap_memory.py --project-root . --feature "Search" --dry-run
```

Apply, validate, and optionally use a custom location:

```bash
python3 scripts/bootstrap_memory.py --project-root . --feature "Search" --feature "Billing" --agents
python3 scripts/validate_memory.py --project-root .
python3 scripts/bootstrap_memory.py --project-root . --memory-dir .agent/memory --feature "Search"
```

| Flag | Description |
| --- | --- |
| `--project-root` | Target project root. Defaults to the current directory. |
| `--feature` | Feature capsule to create and register. Repeatable. |
| `--memory-dir` | Memory directory relative to the project root. Defaults to `.codex/memory`. |
| `--agents` | Create or refresh the `Project Memory Workflow` section in the agents file. |
| `--agents-file` | Agents instructions file. Defaults to `AGENTS.md`. |
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
