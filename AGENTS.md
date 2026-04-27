# 标识行业 AI Agent 自动化设计系统 — Agent 工作规范

> 由 HARNESS_SETUP 生成。只包含 AI 自己推断不出来的信息。
> Session 开始/结束的行为由 Hook 系统强制执行，本文件不再重复。

---

## 状态文件位置

| 文件 | 说明 |
|------|------|
| `.harness/state/current-sprint.md` | 当前阶段目标 |
| `.harness/state/features.json` | 功能完成合约，passes 只能 false→true |
| `.harness/state/constraints.md` | 已知约束，发现新的立即追加 |
| `.harness/registry/_index.md` | 决策索引，每次 Session 读最近 5 条 |
