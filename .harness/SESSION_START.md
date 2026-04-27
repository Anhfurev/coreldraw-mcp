# Session 开始协议

> 每次开始新 Session 时，Agent 必须先执行本清单，再开始任何工作。
> 耗时目标：3 分钟以内。

---

## 第一步：读取状态（按顺序，不要跳过）

```
读 .harness/registry/_index.md     → 只看最近 5 条
读 .harness/state/current-sprint.md → 确认本阶段目标
读 .harness/state/features.json     → 找出所有 passes=false 的条目
读 .harness/state/constraints.md    → 扫一遍已知约束，避免重蹈覆辙
```

**不要**读 sessions/ 目录的完整历史，只通过 _index.md 的摘要了解近况。

---

## 第二步：向用户汇报现状

用以下固定格式输出，不要自由发挥：

```
## Session 开始报告

**上次完成了**：[从 _index.md 最新条目提取，一句话]

**当前未完成功能**：
- feat-xxx: [描述]（如果超过 5 个，只列前 5 个）

**已知约束提醒**：[本次任务最相关的 1-2 条约束]

**建议本次做**：[基于优先级和依赖关系，建议 1-2 个功能]

---
请确认：本次 Session 做什么？
```

---

## 第三步：等待用户确认

用户回复后，**明确复述**本次 Session 的目标，然后开始工作。

格式：
```
明白，本次 Session 目标：[具体目标]
预计需要：[估算步骤数]
开始。
```

---

## 工作中的规则

- 每完成一个功能 → 立即 git commit（`feat: 描述`）
- 发现新约束 → 立即追加到 `.harness/state/constraints.md`
- 上下文窗口超过 70% → 主动告知用户，建议结束当前 Session
- 不确定某个决定 → 停下来问，不要自己猜

---

## 禁止行为

- ❌ 不读状态文件就直接开始工作
- ❌ 自行宣布上次"任务已完成"（要从记录里找，不要猜）
- ❌ 同时开始多个功能
- ❌ 用 lint-disable / noqa / SuppressWarnings 绕过检查规则
