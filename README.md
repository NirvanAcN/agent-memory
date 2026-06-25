# Agent Memory

Codex skill for bootstrapping and maintaining project-local `.codex/memory` workflows.

## Contents

- `SKILL.md`: skill metadata and workflow instructions.
- `scripts/bootstrap_memory.py`: idempotent memory scaffold generator.
- `scripts/validate_memory.py`: contract validator for an existing `.codex/memory`.
- `scripts/test_memory.py`: pytest suite for the scripts.
- `references/memory-file-contract.md`: required memory files, sections, and update rules.
- `agents/openai.yaml`: Codex UI metadata.

## Bootstrap

Preview without writing:

```bash
python3 scripts/bootstrap_memory.py --project-root <path> --feature <name> --dry-run
```

Apply:

```bash
python3 scripts/bootstrap_memory.py --project-root <path> --feature <name> [--feature <name> ...] [--agents]
```

## Validate

Check an existing memory tree against the contract:

```bash
python3 scripts/validate_memory.py --project-root <path>
```

## Test

```bash
python3 -m pytest scripts/test_memory.py
```
