# Agent Memory

Codex skill for bootstrapping and maintaining project-local `.codex/memory` workflows.

## Contents

- `SKILL.md`: skill metadata and workflow instructions.
- `scripts/bootstrap_memory.py`: idempotent memory scaffold generator.
- `references/memory-file-contract.md`: required memory files, sections, and update rules.
- `agents/openai.yaml`: Codex UI metadata.

## Validate

```bash
python3 /Users/mahaomeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```
