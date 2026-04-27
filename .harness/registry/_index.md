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

[2026-04-27] DECISION 新增 feat-010：Agent 层迁移至 LangGraph，支持 RAG + 记忆 + 公司级多业务域，在 feat-006 完成后启动 → decisions/sprint-2-plan.md

[2026-04-27] DECISION 第二阶段规划完成，新增 feat-005～feat-010（多工作站分布式架构 + LangGraph 迁移） → decisions/sprint-2-plan.md

[2026-04-27] DONE feat-005 MCP Server HTTP 模式完成 — server.py 支持 MCP_TRANSPORT env，新增 .mcp.json，uvicorn 依赖已补 → decisions/sprint-2-plan.md

[2026-04-27] DONE 第一阶段MVP完成 — feat-002/003/004 全部 passes=true，Agent编排层+端到端测试就绪 → sessions/2026-04-27-session.md

[2026-04-27] DONE feat-002核心工具实现完成，53个MCP工具函数上线，feat-002→passes=true → sessions/2026-04-27-session.md

[2026-04-23] DECISION 项目 harness 初始化完成 → .harness/registry/decisions/init.md

[2026-04-23 13:49] FIX 修复 install.sh 中 Codex/OpenCode 源文件名错误（致命 bug），更新 README 目录结构和初始化说明 → sessions/2026-04-23-1349.md

[初始化日期] DECISION 项目 harness 初始化，建立 Session 协议框架 → decisions/init.md
