# 决策索引

> **Agent 使用规则**：
> - Session 开始时：只读最近 5 条，了解近况
> - Session 结束时：在最前面追加新条目（不是末尾）
> - 不要读完整历史，用条目里的文件链接按需查阅

格式：`[日期 时间] [类型] 一句话摘要 → 详情文件`

类型说明：
- `DONE` 完成功能 · `WIP` 进行中 · `BLOCKED` 阻塞
- `DECISION` 架构决策 · `CONSTRAINT` 新发现约束 · `FIX` 修复问题

---

<!-- 新条目追加到这里（上方） -->

[2026-04-23] DECISION 项目 harness 初始化完成 → .harness/registry/decisions/init.md

[2026-04-23 13:49] FIX 修复 install.sh 中 Codex/OpenCode 源文件名错误（致命 bug），更新 README 目录结构和初始化说明 → sessions/2026-04-23-1349.md

[初始化日期] DECISION 项目 harness 初始化，建立 Session 协议框架 → decisions/init.md
