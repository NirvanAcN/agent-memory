<div align="center">

# 🧠 Agent Memory

**为编程智能体打造的按范围、可自我维护的记忆系统。**

让你的智能体拥有可按需读取、精准更新的长期记忆，
无需在每次任务时重新通读整个代码库。

[简体中文](README.zh-CN.md) · [English](README.md)

[为什么](#为什么) · [工作原理](#工作原理) · [安装](#安装) · [使用](#使用) · [记忆模型](#记忆模型) · [核心规则](#核心规则) · [开发](#开发)

</div>

---

## 为什么

智能体擅长解决任务，却不擅长记住它们。每次会话都是“冷启动”：
重新读文件、重新推导架构、重新学习一天前已经做过的决策。
这既慢又贵，还不一致。

`agent-memory` 是一个 [Agent Skill](https://learn.chatgpt.com/docs/build-skills)，
用于在项目本地创建**记忆系统**（默认 `.codex/memory`），并提供严格的读写控制：

- **最小读取**：先通过注册表定位相关胶囊，再只读取该胶囊。
- **按范围回写**：将稳定事实写入最小适用范围，而不是到处都写。
- **验证后回写**：独立验证新结论，并基于目标文件的最新内容合并更新。
- **故障降级与隐私保护**：记忆损坏不阻塞主任务，仓库记忆不保存密钥或原始对话。

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

## 安装

`agent-memory` 是一个标准的 [Agent Skill](https://learn.chatgpt.com/docs/build-skills)
（一份 `SKILL.md` 加随附脚本），适用于任何支持 skills 格式的智能体。
将它 clone 到你的智能体 skills 目录即可：

```bash
git clone https://github.com/NirvanAcN/agent-memory.git \
  <skills-dir>/agent-memory
```

| 智能体 | Skills 目录 |
| --- | --- |
| Codex | `~/.agents/skills/agent-memory` |
| Claude Code | `~/.claude/skills/agent-memory` |
| 其他 / 项目级 | `./.skills/agent-memory` 或你工具的 skills 路径 |

## 使用

你不需要手动跑任何命令。安装后，直接用自然语言告诉智能体，
它会加载该 skill 并代你调用随附脚本：

> 用 **agent-memory** 为这个项目初始化记忆系统，feature 包括 Search 和 Billing，
> 并把工作流加到 AGENTS.md。

智能体会创建记忆树、注册功能、配置 agents 文件，之后按
[契约](references/memory-file-contract.md)读取和更新记忆。

### 默认位置

记忆默认创建在 `.codex/memory` 下。若你的智能体使用其他约定，
可让它指定不同目录（例如 `.agent/memory`）；两个随附脚本都接受 `--memory-dir`。

### 手动 / 进阶调用

随附脚本是智能体调用的实现细节，但你也可以直接运行它们用于调试或 CI。
先预览不写入：

```bash
python3 scripts/bootstrap_memory.py --project-root . --feature "Search" --dry-run
```

正式创建、校验，并可选自定义位置：

```bash
python3 scripts/bootstrap_memory.py --project-root . --feature "Search" --feature "Billing" --agents
python3 scripts/validate_memory.py --project-root .
python3 scripts/bootstrap_memory.py --project-root . --memory-dir .agent/memory --feature "Search"
```

预览并执行旧 policy 升级：

```bash
python3 scripts/bootstrap_memory.py --project-root . --upgrade --dry-run
python3 scripts/bootstrap_memory.py --project-root . --upgrade
```

| 参数 | 说明 |
| --- | --- |
| `--project-root` | 目标项目根目录，默认为当前目录。 |
| `--feature` | 要创建并注册的功能胶囊，可重复传入。 |
| `--memory-dir` | 相对于项目根目录的记忆目录，默认 `.codex/memory`。 |
| `--agents` | 在 agents 文件中创建或刷新 `Project Memory Workflow` 节。 |
| `--agents-file` | agents 指令文件，默认 `AGENTS.md`。 |
| `--upgrade` | 显式迁移旧 managed policy block，并保留项目自定义内容。 |
| `--dry-run` | 只报告将要发生的变更，不触碰文件系统。 |

引导脚本具有**跨日期幂等性**：它创建缺失文件、保守修复必需的表头与章节，
不会仅为推进新鲜度标记而重写未变化的记忆树。任何文件写入前都会先校验
全部输出路径和 feature 名称。新 scaffold 带有版本化 managed policy 和稳定
rule IDs；无版本旧 policy 必须显式使用 `--upgrade`，且不会降级未来版本。

## 记忆模型

```
.codex/memory/
├── index.md              # 路由入口 + 读/写策略
├── project-memory.md     # 稳定的跨功能项目事实
├── feature-registry.md   # 功能列表 → 胶囊指针
├── decision-log.md       # 持久的项目决策
├── context-budget.json   # 机器可读的容量限制；任务期间不读取
└── features/
    ├── _template.md      # 胶囊模板
    └── <Feature>.md      # 每个功能一个胶囊
```

每个功能胶囊都采用固定结构，让智能体始终知道去哪里查：
`Status`、`Responsibilities`、`Dependencies`、`Persistence`、`Key Decisions`
以及 `Regression Checks`。Markdown 文件记录 `Last Updated: YYYY-MM-DD`，
预算配置使用 `last_updated`；各标记只随对应文件的实际变更刷新。

完整的结构定义、必需表头及更新语义请见
[`references/memory-file-contract.md`](references/memory-file-contract.md)。

## 核心规则

五条原则让记忆随时间推移仍值得信任：

1. **先定位再读取。** 始终按 `index → 注册表 → 胶囊` 的顺序，绝不猜测胶囊名。
2. **限定回写范围。** 仅涉及单个功能的变更只动一个胶囊；全局变更需同时更新 `project-memory.md`、`decision-log.md` 和 `index.md`。
3. **验证后再写。** 任务开始时读到的记忆只是上下文，不是证据；每个新增或变更结论都要独立验证。
4. **写前比较，写后确认。** 编辑前只重读将要修改的 memory 文件，发现并发变化时基于最新内容合并，写入后再重读结果。
5. **故障可降级，内容守隐私。** 记忆缺失或无效不能阻塞主任务，但也不能支撑 memory 结论；密钥、凭证、原始对话和敏感个人数据不得进入仓库记忆。

代码、权威文档和运行时证据仍是事实来源；当记忆与它们冲突时，修正记忆。

当胶囊超过约 100 行或混入了不相关的职责时，按功能或角色拆分，
原胶囊保留为高层路由摘要。非显而易见或高风险的结论需附上
`Source`/`Evidence`；时效性事实需附上 `Last Verified`、`Valid Since`、
`Deprecated`、`Superseded by` 或 `Revisit Trigger`。临时的过程记录永远不进入记忆。

随附校验器会强制执行 agent guide、路由文件和胶囊的容量预算。已有的超大胶囊
可在拆分期间登记明确的“只减不增”债务；债务可以缩小，但不能增长。

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
python3 -m unittest scripts/test_memory.py
python3 scripts/validate_memory.py --project-root . --report
```

需要 **Python 3.7+**。脚本与测试只使用标准库，没有运行时依赖；官方 skill
校验器还需要 PyYAML。

## 许可证

基于 [MIT 许可证](LICENSE) 发布。
