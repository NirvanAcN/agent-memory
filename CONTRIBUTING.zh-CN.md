# 贡献指南

感谢你有兴趣改进 **agent-memory**！本文说明如何提交变更并合入。

> For English, see [CONTRIBUTING.md](CONTRIBUTING.md).

## 基本原则

- 保持尊重。本项目遵循[行为准则](CODE_OF_CONDUCT.md)。
- 保持变更聚焦，每个合并请求只做一件逻辑上独立的事。
- 较大或破坏性变更请先在 issue 中讨论，再提交合并请求。

## 开发环境

脚本**无运行时依赖**，面向 **Python 3.9+**。只有测试工具需要额外依赖。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 提交合并请求之前

运行与 CI 一致的本地检查：

```bash
# 单元测试
python3 -m pytest scripts/test_memory.py

# Lint（如已安装）
ruff check .

# 端到端凒烟测试
python3 scripts/bootstrap_memory.py --project-root /tmp/agent-memory-demo --feature Demo
python3 scripts/validate_memory.py --project-root /tmp/agent-memory-demo
```

`scripts/` 中的所有新行为都必须在 `scripts/test_memory.py` 中附带测试。
引导脚本必须保持**幂等**：在已是最新状态的记忆树上重跑不产生任何变更。

## 修改记忆契约

文件契约是唯一事实源。若你修改了必需文件、表头或胶囊章节，必须**同时**更新以下全部：

1. `references/memory-file-contract.md`
2. `scripts/bootstrap_memory.py`（模板与章节列表）
3. `scripts/validate_memory.py`（校验规则）
4. 若用户可见行为发生变化，同步 `SKILL.md` 与 README

并在 [`CHANGELOG.md`](CHANGELOG.md) 的 `Unreleased` 下添加对应条目。

## 提交与 MR 约定

- 使用清晰的祈使句提交标题（例如 `fix: ...`、`docs: ...`、`chore: ...`）。
- 在 MR 描述中关联相关 issue。
- MR 描述专注于**为什么**和**做了什么**，而非重复 diff。

## 报告缺陷

使用 **Bug** 模板创建 issue，提供复现步骤、预期与实际行为以及你的 Python 版本。
