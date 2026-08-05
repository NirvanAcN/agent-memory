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

`agent-memory` is an [Agent Skill](https://learn.chatgpt.com/docs/build-skills) that
bootstraps a **project-local memory system** (default `.codex/memory`) with
strict read and write controls:

- **Minimum read** — locate the relevant capsule through a registry, then read only that capsule.
- **Scoped write-back** — persist stable facts to the smallest applicable scope, never to everything.
- **Verified write-back** — independently verify new conclusions and merge against the latest target file.
- **Fail-open privacy** — broken memory never blocks the task, and repository memory never stores secrets or raw conversations.

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

`agent-memory` is a standard [Agent Skill](https://learn.chatgpt.com/docs/build-skills)
(a `SKILL.md` plus bundled scripts), so it works with any agent that supports the
skills format. Clone it into your agent's skills directory:

```bash
git clone https://github.com/NirvanAcN/agent-memory.git \
  <skills-dir>/agent-memory
```

| Agent | Skills directory |
| --- | --- |
| Codex | `~/.agents/skills/agent-memory` |
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

Preview and apply a legacy policy upgrade:

```bash
python3 scripts/bootstrap_memory.py --project-root . --upgrade --dry-run
python3 scripts/bootstrap_memory.py --project-root . --upgrade
```

| Flag | Description |
| --- | --- |
| `--project-root` | Target project root. Defaults to the current directory. |
| `--feature` | Feature capsule to create and register. Repeatable. |
| `--memory-dir` | Memory directory relative to the project root. Defaults to `.codex/memory`. |
| `--agents` | Create or refresh the `Project Memory Workflow` section in the agents file. |
| `--agents-file` | Agents instructions file. Defaults to `AGENTS.md`. |
| `--upgrade` | Explicitly migrate legacy managed policy blocks while preserving project-owned content. |
| `--dry-run` | Report what would change without touching the filesystem. |

The bootstrap script is **idempotent across dates**: it creates missing files,
repairs required headers and sections conservatively, and never rewrites an
unchanged tree merely to advance freshness markers. All output paths and feature
names are validated before any file is written. New scaffolds carry a versioned
managed policy and stable rule IDs. Existing unversioned policies require
explicit `--upgrade`; newer versions are never downgraded.

## Memory model

```
.codex/memory/
├── index.md              # routing entrypoint + read/write policy
├── project-memory.md     # stable cross-feature project facts
├── feature-registry.md   # feature list → capsule pointers
├── decision-log.md       # durable project decisions
├── context-budget.json   # machine-readable size limits; not read during tasks
└── features/
    ├── _template.md      # capsule template
    └── <Feature>.md      # one capsule per feature
```

Every feature capsule carries a fixed shape so agents always know where to look:
`Status`, `Responsibilities`, `Dependencies`, `Persistence`, `Key Decisions`,
and `Regression Checks`. Markdown files track `Last Updated: YYYY-MM-DD`, while
the budget config uses `last_updated`; each marker changes only with its file.

Full schema, required headers, and update semantics live in
[`references/memory-file-contract.md`](references/memory-file-contract.md).

## The rules

Five principles keep the memory trustworthy over time:

1. **Locate before read.** Always go `index → registry → capsule`. Never guess capsule names.
2. **Scope the write-back.** Feature-only changes touch one capsule; global changes update `project-memory.md`, `decision-log.md`, and `index.md` together.
3. **Verify before write.** Task-start memory is context, not evidence; independently verify every new or changed conclusion.
4. **Compare and confirm writes.** Re-read only the target memory files immediately before editing, merge concurrent changes, then re-read the result.
5. **Fail open and keep it private.** Missing or invalid memory never blocks the primary task, but it cannot support memory claims; secrets, credentials, raw chats, and sensitive personal data never enter repository memory.

Code, authoritative documentation, and runtime evidence remain the sources of
truth. When memory disagrees with them, fix the memory.

Capsules that grow past ~100 lines or mix unrelated responsibilities are split
by function or role, while the original capsule remains a high-level routing
summary. Non-obvious or risky conclusions carry `Source`/`Evidence`; time-sensitive
facts carry `Last Verified`, `Valid Since`, `Deprecated`, `Superseded by`, or
`Revisit Trigger`. Transient process notes never enter memory.

The bundled validator enforces guide, routing, and capsule budgets. Existing
oversized capsules may use explicit no-growth debt while they are split into
narrower capsules; debt can shrink but cannot grow.

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
python3 -m unittest scripts/test_memory.py
python3 scripts/validate_memory.py --project-root . --report
```

Requires **Python 3.7+**. The scripts and tests use only the standard library
and have no runtime dependencies. The official skill validator additionally
requires PyYAML.

## License

Released under the [MIT License](LICENSE).
