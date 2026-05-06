# Session 开始协议

> 每次开始新 Session 时，Agent 必须先执行本清单，再开始任何工作。
> 耗时目标：3 分钟以内。

---

## 第一步：读取状态（按顺序，不要跳过）

```
读 .harness/product/backlog.md      → 扫产品方向 + "待评估"区 + "已知约束"区
读 .harness/registry/_index.md      → 只看最近 5 条
读 .harness/state/current-sprint.md → 确认本阶段目标和默认 Session 阶段
读 .harness/state/features.json     → 找出所有 passes=false 的条目（唯一功能状态权威）
```

**不要**读 sessions/ 目录的完整历史，只通过 _index.md 的摘要了解近况。

---

## 第二步：输出"第一屏"（用户说话前）

读完状态后，立即输出简短摘要，**等待用户说明意图**，不要跳过这一步直接进入工作：

```
## Session 开始

当前阶段：[current-sprint.md 的 默认Session阶段 字段值]（[简短说明，如"feat-xxx、feat-yyy 待完成"]）
上次：[_index.md 最新一条，一句话]

今天要做什么？（或用 :指令 明确阶段，输入 :help 查看可用指令）
```

---

## 第三步：判断本次 Session 阶段（用户回复后执行）

用户回复后，按以下优先级判断阶段，然后**明确告知用户**判断结果：

### 优先级顺序

**优先级 1 — 明确指令**（用户消息包含 `:xxx`）

| 指令 | 进入阶段 |
|------|----------|
| `:discover` | DISCOVER |
| `:design` | DESIGN |
| `:plan` | PLAN |
| `:build` | BUILD |
| `:fix` | BUILD/FIX 子模式 |
| `:verify` | VERIFY |
| `:release` | RELEASE |
| `:retro` | RETRO |
| `:status` | 输出当前状态摘要，不进入任何阶段 |
| `:help` | 输出指令列表，不进入任何阶段 |
| `:phase X` | 将 current-sprint.md 的默认 Session 阶段更新为 X |

**优先级 2 — 关键词推断**

| 关键词（中英混合） | 推断阶段 |
|---------|----------|
| 需求、用户故事、用户说、requirement、user story | DISCOVER |
| 架构、设计、方案、UI、交互、选型、architecture、design | DESIGN |
| 规划、Sprint、任务拆解、优先级、plan、roadmap | PLAN |
| 测试、验证、回归、bug 排查、test、verify | VERIFY |
| 发布、上线、部署、release、deploy、tag | RELEASE |
| 复盘、总结、retrospective、retro、回顾 | RETRO |
| 顺手、临时、快速修、发现个问题、小改 | BUILD/FIX 子模式 |
| 实现、开发、写代码、feat、fix（非小改语境） | BUILD |

**优先级 3 — 回退默认**

读 `current-sprint.md` 的 `默认 Session 阶段` 字段，使用其值。

### 告知用户

判断完成后，在开始工作前说明：

```
检测到：[阶段名]（原因：[一句话，如"你提到了'架构'"或"默认 BUILD 阶段"]）
如果不对，用 :build / :design / :fix 等指令切换。
```

如果判断结果是 PLAN 且 features.json 中有 passes=false 条目未完成，额外提示：
```
注意：当前还有未完成功能（feat-xxx），确认要规划新阶段而非继续开发吗？
```

---

## 第四步：执行对应阶段的 Session 开始报告

### DISCOVER — 需求探索

```
## Session 开始 — DISCOVER 阶段

当前需求池：[backlog.md "待评估"区条目数，如有则列出]
上次需求讨论：[最近一条 DISCOVER 类型的 _index 条目，无则写"暂无"]

今天要探索/梳理什么需求？
```

工作产出放 `docs/requirements/YYYY-MM-DD-[主题].md`，同步记录到 backlog.md。

---

### DESIGN — 产品/技术设计

```
## Session 开始 — DESIGN 阶段

相关需求：[从 backlog 提取相关条目，无则写"暂无"]
已有设计文档：[列出 docs/design/ 下文件名，无则写"暂无"]

今天要设计/决策什么？
```

工作产出：
- 产品设计 → `docs/design/[模块名].md`
- 架构/技术选型 → `registry/decisions/YYYY-MM-DD.md`（ADR 格式）

---

### PLAN — Sprint 规划

```
## Session 开始 — PLAN 阶段

当前 Sprint：[current-sprint.md 阶段名 + 目标]
backlog 待评估：[backlog.md "待评估"区条目列表，无则写"暂无"]
未完成功能（来自 features.json）：[passes=false 的条目列表]

今天要规划哪个阶段/功能集？
```

用户确认功能列表后，立即更新 `features.json` 和 `current-sprint.md` 元数据字段（不能推迟到 SESSION_END）。
注意：current-sprint.md 不再维护功能状态栏，features.json 是唯一来源。

---

### BUILD — 功能开发（标准模式）

```
## Session 开始 — BUILD 阶段

上次完成了：[_index.md 最新条目，一句话]

当前未完成功能：
- feat-xxx: [描述]（超过 5 个只列前 5 个）

建议本次做：[无依赖且优先级最高的 1-2 个]

请确认：本次 Session 做什么？
```

每完成一个功能 → 立即 git commit → 更新 features.json passes=true。

---

### BUILD/FIX — 快速修复子模式

```
## Session 开始 — 快速修复

跳过规划。描述要修什么？
```

- 不新增 feat 条目，不改 passes
- 改完立即 commit（`fix: 描述`）
- SESSION_END 极简：只在 _index.md 追加一行 `FIX` 条目，不写 session 摘要文件

---

### VERIFY — 验证/测试

```
## Session 开始 — VERIFY 阶段

已完成功能（passes=true）：[列表]
上次验证结果：[最近一条 VERIFY 类型 _index 条目，无则写"暂无"]

今天要验证哪些功能，还是排查哪个 Bug？
```

发现 Bug → 记入 backlog.md（来源：[VERIFY]）或立即进入 FIX 子模式。

---

### RELEASE — 发布

```
## Session 开始 — RELEASE 阶段

待发布功能：[passes=true 且未发布的条目]
上次发布：[最近一条 RELEASE 类型 _index 条目，无则写"暂无"]

今天发布 vX.Y.Z，还是准备发布清单？
```

工作产出放 `docs/releases/vX.Y.Z.md`，完成后打 git tag。

---

### RETRO — 阶段复盘

```
## Session 开始 — RETRO 阶段

本 Sprint 完成：[features.json passes=true 列表]
本 Sprint 未完成：[passes=false 列表]

今天复盘哪个 Sprint？
```

工作产出放 `registry/decisions/retro-N.md`，改进行动项写入 backlog.md（来源：[RETRO]）。

---

## 第五步：复述目标，开始工作

用户确认后输出：

```
明白，本次 Session 目标：[具体目标]
阶段：[阶段名]
开始。
```

---

## 工作中的规则

- 每完成一个功能 → 立即 git commit（`feat: 描述`）
- 发现新约束 → 立即追加到 `.harness/state/constraints.md`
- 上下文窗口超过 70% → 主动告知用户，建议结束当前 Session
- 不确定某个决定 → 停下来问，不要自己猜
- PLAN 阶段用户确认功能列表 → 立即更新 features.json 和 current-sprint.md，不推迟

## 编码前置原则（Karpathy 准则）

**开始实现每个功能前，先做一次简短的"思考前置"：**

1. 说出你对需求的理解；有歧义先问，不要静默假设
2. 列出 1-2 种实现方案，选最简单的那个，说明原因
3. 列清楚要动哪些文件，以及为什么

**编码时：**
- 只改任务要求改的，不"顺手优化"相邻代码或格式
- 不加未被要求的参数、配置项、抽象层
- 你的改动产生的孤儿 import/变量/函数必须清掉
- 如果发现不相关的死代码，提一句——不要动它

---

## 禁止行为

- ❌ 不读状态文件就直接开始工作
- ❌ 跳过第二步（不输出第一屏就直接问"做哪个功能"）
- ❌ 自行宣布上次"任务已完成"（要从记录里找，不要猜）
- ❌ 同时开始多个功能
- ❌ PLAN 阶段确认后不更新 features.json 就结束 Session
- ❌ 修改 SESSION_START.md / SESSION_END.md 后不同步 template/ 副本
- ❌ 用 lint-disable / noqa / SuppressWarnings 绕过检查规则
