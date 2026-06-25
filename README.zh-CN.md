<div align="center">

# 🧠 Agent Memory

**为编程智能体打造的分作用、可自我维护的记忆系统。**

让你的智能体拥有可按需读取、精准更新的长期记忆，
无需在每次任务时重新通读整个代码库。

[简体中文](README.zh-CN.md) · [English](README.md)

[为什么](#为什么) · [工作原理](#工作原理) · [快速开始](#快速开始) · [记忆模型](#记忆模型) · [核心规则](#核心规则) · [开发](#开发)

</div>

---

## 为什么

智能体擅长解决任务，却不擅长记住它们。每次会话都是“冷启动”：
重新读文件、重新推导架构、重新学习一天前已经做过的决策。
这既慢又贵，还不一致。

`agent-memory` 是一个 [Codex](https://openai.com/index/introducing-codex/) skill，
用于在项目本地创建 **`.codex/memory` 记忆系统**，并提供两项严格保证：

- **最小读取**：先通过注册表定位相关胶囊，再只读取该胶囊。
- **分作回写**：将稳定事实写入最小适用范围，而不是到处都写。

最终得到的是一份持久的项目知识：体量小、保持新鲜，且不会变成
一份没人信任的无限增长的日志。

## 工作原理

```
  任务开始
      │
      ▼
  index.md ──────────▶ 读取顺序 + 回写策略
      │
      ▼
  feature-registry.md ─▶ 定位正确的胶囊
      │
      ▼
  features/<Feature>.md ─▶ 只读取目标胶囊
      │
      ▼
  完成工作，然后回写到最小范围
```

全局上下文（`project-memory.md`、`decision-log.md`）**仅在**任务涉及
跨模块路由、依赖、持久化或全局行为契约时才读取。
其余情况下一切都局限在单个功能胶囊内。

## 快速开始

在不写入任何文件的情况下预览脚手架：

```bash
python3 scripts/bootstrap_memory.py --project-root . --feature "Search" --dry-run
```

正式创建记忆系统：

```bash
python3 scripts/bootstrap_memory.py \
  --project-root . \
  --feature "Search" \
  --feature "Billing" \
  --agents
```

按契约校验现有记忆树：

```bash
python3 scripts/validate_memory.py --project-root .
```

| 参数 | 说明 |
| --- | --- |
| `--project-root` | 目标项目根目录，默认为当前目录。 |
| `--feature` | 要创建并注册的功能胶囊，可重复传入。 |
| `--agents` | 在 `AGENTS.md` 中创建或刷新 `Project Memory Workflow` 节。 |
| `--dry-run` | 只报告将要发生的变更，不触碰文件系统。 |

引导脚本是**幂等**的：它创建缺失文件、刷新新鲜度标记、确保必需的
表头与章节存在，且绝不覆盖人工撰写的内容。

## 记忆模型

```
.codex/memory/
├── index.md              # 路由入口 + 读/写策略
├── project-memory.md     # 稳定的跨功能项目事实
├── feature-registry.md   # 功能列表 → 胶囊指针
├── decision-log.md       # 持久的项目决策
└── features/
    ├── _template.md      # 胶囊模板
    └── <Feature>.md      # 每个功能一个胶囊
```

每个功能胶囊都采用固定结构，让智能体始终知道去哪里查：
`Status`、`Responsibilities`、`Dependencies`、`Persistence`、`Key Decisions`
以及 `Regression Checks`。每个文件都记录 `Last Updated: YYYY-MM-DD` 标记，
并在每次变更时刷新。

完整的结构定义、必需表头及更新语义请见
[`references/memory-file-contract.md`](references/memory-file-contract.md)。

## 核心规则

三条原则让记忆随时间推移仍值得信任：

1. **先定位再读取。** 始终按 `index → 注册表 → 胶囊` 的顺序，绝不猜测胶囊名。
2. **限定回写范围。** 仅涉及单个功能的变更只动一个胶囊；全局变更需同时更新 `project-memory.md`、`decision-log.md` 和 `index.md`。
3. **代码是唯一事实源。** 当记忆与代码不一致时，修正记忆。

当胶囊超过约 100 行或混入了不相关的职责时，按功能或角色拆分，
原胶囊保留为高层路由摘要。非显而易见或高风险的结论需附上
`Source`/`Evidence`；时效性事实需附上 `Last Verified`、`Valid Since`、
`Deprecated`、`Superseded by` 或 `Revisit Trigger`。临时的过程记录永远不进入记忆。

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `SKILL.md` | Skill 元数据与面向智能体的工作流。 |
| `scripts/bootstrap_memory.py` | 幂等的记忆脚手架生成器。 |
| `scripts/validate_memory.py` | 针对现有记忆树的契约校验器。 |
| `scripts/test_memory.py` | 脚本的测试套件。 |
| `references/memory-file-contract.md` | 权威的文件契约与更新规则。 |
| `agents/openai.yaml` | Codex UI 元数据。 |

## 开发

运行测试套件：

```bash
python3 -m pytest scripts/test_memory.py
```

需要 **Python 3.9+**（使用了标准库类型泛型）。脚本本身无运行时依赖，
`pytest` 仅用于测试。

## 许可证

基于 [MIT 许可证](LICENSE) 发布。
