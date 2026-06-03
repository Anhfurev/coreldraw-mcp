# Harness 初始化协议

> 这个文件只运行一次。完成后可以删除或归档到 `.harness/registry/decisions/init.md`。
>
> **使用方法**：在项目根目录执行
> ```
> claude "请读取 HARNESS_SETUP.md 并按步骤初始化这个项目的 harness"
> ```

---

## 你的角色

你是这个项目的 **Harness 初始化 Agent**。你的任务是理解这个项目，然后搭建一套帮助未来 Agent 高效工作的状态管理框架。

---

## Step 1：自主扫描项目（不要问我，自己做）

按顺序读取以下文件（存在则读，不存在则跳过）：

```
package.json / Cargo.toml / go.mod / pyproject.toml / pom.xml / build.gradle
README.md / README.zh.md
src/ 或 lib/ 的前两层目录结构
.github/workflows/（如果有）
```

从以上文件中自主提取：
- 项目名称和定位
- 技术栈、语言版本、主要依赖
- 构建/测试/启动命令
- 已有的目录分层结构

把提取结果记在心里，**不要输出**，直接进入 Step 2。

---

## Step 2：只问我以下问题

**规则**：逐条问，一次只问一个问题，等我回答后再问下一个。不要合并提问。不要问任何你自己能从代码里推断出来的事情。

**问题清单（按顺序）**：

**Q0**：这个产品是为谁解决什么问题？用一句话描述：「为 [谁]，解决 [什么问题]，让他们能 [做到什么]」。

**Q0.5**：成功长什么样？用户用了之后，你怎么知道这个产品成功了？（可以是具体行为、感受或指标）

**Q0.75**：明确不做什么？有哪些诱人但应该拒绝的方向？

**Q1**：这个项目最终要做到什么？用一两句话描述你期望的最终状态。

**Q2**：有没有架构约束是看代码看不出来的？比如：
- 哪些模块不能互相依赖
- 哪些第三方库是禁止引入的
- 哪些设计决策已经确定、不允许 Agent 自行推翻

**Q3**：有没有容易踩的坑？上手这个项目最容易犯的错误是什么？

**Q4**：第一阶段（接下来 1-2 周）要完成哪些功能？请逐条列出，我来记录到 features.json。每条格式：`功能名称 — 简短描述 | 验收标准（怎么判断这条做完了？）`

**Q5**（可选，如果 Q4 的功能涉及多人或多 Agent）：这些功能有依赖顺序吗？哪个要先做？

---

## Step 3：生成文件

收集完以上信息后，**按顺序**创建以下文件：

### 3.0 .harness/product/backlog.md（优先生成）

把 Q0 / Q0.5 / Q0.75 的答案填入"产品方向"区，把 Q2 / Q3 的答案填入"已知约束与坑"区。
模板已有章节，填入内容后删除占位符即可。

### 3.1 AGENTS.md（项目根目录）

规则：
- **只写** Step 2 中收集到的"人工确认的信息"
- **不要**复述 README 或文档里已有的内容
- **不要**写 Agent 自己能通过读代码发现的信息
- **控制在 60 行以内**
- 如果某项信息 Agent 自己能发现，就不写

模板结构（按实际情况填写，空的章节直接删掉）：

```markdown
# [项目名] — Agent 工作规范

## 不可推翻的约束
（只写 Q2 的答案，每条一行，要具体）

## 容易踩的坑
（只写 Q3 的答案，每条一行）

## 常用命令
（只写 Q1 扫描到但 README 里没有的命令）

## 文件索引
- `.harness/SESSION_START.md` — 每次开始前必读
- `.harness/SESSION_END.md` — 每次结束前必做
- `.harness/state/current-sprint.md` — 当前阶段目标
- `.harness/state/features.json` — 功能完成合约
- `.harness/registry/_index.md` — 决策索引
```

### 3.2 CLAUDE.md 和 .cursorrules

内容与 AGENTS.md 完全相同，直接复制。

### 3.3 .harness/state/features.json

把 Q4 的功能清单填入，格式：

```json
{
  "_readme": "只允许把 passes 从 false 改成 true。禁止删除条目或修改描述。",
  "_project": "项目名",
  "_sprint": "第一阶段",
  "features": [
    {
      "id": "feat-001",
      "description": "功能名称 — 具体描述",
      "acceptance": "验收标准：用一句话描述如何判断这个功能已完成",
      "depends_on": [],
      "passes": false
    }
  ]
}
```

### 3.4 .harness/state/current-sprint.md

```markdown
# 当前阶段目标

**阶段**：第一阶段
**目标**：（Q1 的答案，一句话）
**完成标准**：features.json 中本阶段所有条目 passes = true
**默认 Session 阶段**：BUILD
**当前版本**：（发布后填入）

---

## 阶段历史

| 阶段 | 完成时间 | 主要产出 |
|------|----------|----------|
| （暂无） | | |
```

### 3.5 .harness/registry/_index.md

```markdown
# 决策索引

> Agent 每次 Session 开始时读取最近 3 条。Session 结束时在最前面追加新条目。

格式：`[日期 时间] [类型] 一句话摘要 → 详情文件`

> 类型：`DONE`完成 · `WIP`进行中 · `BLOCKED`阻塞 · `FIX`计划外修复 · `DECISION`决策 · `CONSTRAINT`约束 · `DISCOVER`需求探索 · `VERIFY`验证 · `RELEASE`发布 · `RETRO`复盘

---

[初始化日期] DECISION 项目 harness 初始化完成 → .harness/registry/decisions/init.md
```

### 3.7 .harness/registry/decisions/init.md

```markdown
# 初始化记录

**日期**：[今天日期]
**执行**：Harness 初始化 Agent

## 项目概况
（把 Step 1 扫描到的技术栈、结构简要写这里）

## 确认的约束
（Q2 的完整答案）

## 已知风险
（Q3 的完整答案）

## 第一阶段范围
（Q4 的完整答案）
```

---

## Step 4：完成后告诉我

列出：
1. 创建了哪些文件
2. AGENTS.md 写了哪些内容（为什么这些值得写）
3. features.json 里有几个功能条目
4. 你在扫描中发现了什么需要人工确认的疑问（如果有）

---

## 不要做的事

- ❌ 不要生成模板变量未填写的文件（`__PROJECT_NAME__` 这类占位符）
- ❌ 不要复述 README 或现有文档的内容写进 AGENTS.md
- ❌ 不要问我任何你自己能从代码推断的问题
- ❌ 不要一次性抛出所有问题
- ❌ 不要在 AGENTS.md 里写超过 60 行
