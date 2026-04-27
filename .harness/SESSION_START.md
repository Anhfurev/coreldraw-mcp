# Session 开始协议

> 每次开始新 Session 时，Agent 必须先执行本清单，再开始任何工作。
> 耗时目标：3 分钟以内。

---

## 第一步：读取状态（按顺序，不要跳过）

```
读 .harness/product/vision.md       → 确认产品方向，所有决策对照此文件
读 .harness/product/backlog.md      → 扫"待评估"区，看有无积压需求
读 .harness/registry/_index.md      → 只看最近 5 条
读 .harness/state/current-sprint.md → 确认本阶段目标
读 .harness/state/features.json     → 找出所有 passes=false 的条目
读 .harness/state/constraints.md    → 扫一遍已知约束，避免重蹈覆辙
```

**不要**读 sessions/ 目录的完整历史，只通过 _index.md 的摘要了解近况。

---

## 第二步：判断本次 Session 类型

读完状态后，先判断属于哪种场景，再决定后续流程：

**场景 A — 正常功能开发**：features.json 中有 passes=false 的条目
→ 执行第三步（汇报 + 确认 + 开发）

**场景 B — Sprint 切换**：features.json 中所有条目 passes 均为 true，
或用户明确说"第 N 阶段完成了，规划下一阶段"
→ 跳过第三步，直接执行【Sprint 切换流程】

---

## 第三步：场景 A — 汇报现状并确认

用以下固定格式输出：

```
## Session 开始报告

**上次完成了**：[从 _index.md 最新条目提取，一句话]

**当前未完成功能**：
- feat-xxx: [描述]（超过 5 个只列前 5 个）

**已知约束提醒**：[本次任务最相关的 1-2 条]

**建议本次做**：[基于优先级和依赖关系，建议 1-2 个功能]

---
请确认：本次 Session 做什么？
```


用户回复后，明确复述目标，然后开始工作：

```
明白，本次 Session 目标：[具体目标]
预计需要：[估算步骤数]
开始。
```

---

## Sprint 切换流程（场景 B）

**Step 1**：读 vision.md 确认方向，读 backlog.md 的"待评估"区，读 PRD 或用户指定文档，草拟新阶段功能清单

**Step 2**：检查 backlog 中的待评估需求，判断是否有高优先级条目需要纳入新阶段

**Step 3**：列表呈现给用户确认：

```
## 第 N+1 阶段规划草案

- feat-xxx: [功能名] — [一句话描述]（依赖：无 或 feat-yyy）
- feat-xxx: ...

请确认：是否按此规划？可以增删或调整。
```

**Step 4**：用户确认后，**立即**依次更新以下文件（不能推迟到 SESSION_END）：

1. `.harness/state/features.json`
   → 在现有条目后面追加新功能，**不删除旧条目**

2. `.harness/state/current-sprint.md`
   → 更新阶段名称、目标、功能列表
   → 把上一阶段信息移入文件底部的"阶段历史"表格

3. `.harness/registry/decisions/sprint-N+1-plan.md`（新建）
   → 记录本次规划的完整功能列表、依赖关系、优先级排序

4. `.harness/registry/_index.md`
   → 在**最前面**追加一行：
   `[日期 时间] DECISION 第N+1阶段规划完成，新增 feat-xxx～feat-yyy → decisions/sprint-N+1-plan.md`

5. git commit：
   ```bash
   git add .harness/
   git commit -m "chore: 第N+1阶段规划完成，新增 X 个功能"
   ```

**Step 4**：全部更新完成后告诉用户：

```
## Sprint 切换完成

新增功能：X 个（feat-xxx ～ feat-yyy）
建议先做：[无依赖且优先级最高的功能]
状态文件已更新，下次 Session 自动加载新阶段。
```

> ⚠️ Sprint 切换的文件更新是规划任务本身的一部分，必须在本次 Session 内完成，不能留到 SESSION_END。


---

## 工作中的规则

- 每完成一个功能 → 立即 git commit（`feat: 描述`）
- 发现新约束 → 立即追加到 `.harness/state/constraints.md`
- 上下文窗口超过 70% → 主动告知用户，建议结束当前 Session
- 不确定某个决定 → 停下来问，不要自己猜

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
- ❌ 自行宣布上次"任务已完成"（要从记录里找，不要猜）
- ❌ 同时开始多个功能
- ❌ Sprint 切换完成后不更新 harness 文件就结束 Session
- ❌ 用 lint-disable / noqa / SuppressWarnings 绕过检查规则
