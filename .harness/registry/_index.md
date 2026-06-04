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

[2026-06-04 FIX] runner.py 缺少 init_connection 导致 Streamlit 路径所有工具返回"CorelDRAW 未连接"

[2026-06-04 FIX] OpenAI 超时 300s + DeepSeek reasoning_content 显示 + 错误终止消息修正

[2026-06-03 STATUS] 查看项目完成情况 — feat-001~005/012~015 全部 passes=true，feat-011/010 延后，feat-006~009 预留

[2026-04-30 DISCOVER] DISCOVER CorelDRAW COM API 工具缺口调研，11 大类未暴露能力写入 backlog → sessions/2026-04-30-discover.md

[2026-06-03 00:00] WIP Session 开始，处理 git 问题 → （进行中）

[2026-06-03 00:10] FIX app.py 页面标题从"标识行业"改为"CorelDRAW 调试"

<!-- 新条目追加到这里（上方） -->

[2026-04-30 13:45] VERIFY test_e2e.py 测试覆盖率审计：21/28 通过，7 失败（3 个 ExportEx），~40+ 工具零测试 → sessions/2026-04-30-1345.md

[2026-04-29 00:01] FIX X6 兼容性多轮修复完成，测试从 13→21/28 通过，PNG/DXF 导出待最终验证 → sessions/2026-04-29-0001.md


[2026-04-27 22:52] WIP 第二阶段架构规划完成，feat-005✅，feat-011/010 待实现，多智能体预留设计固化 → sessions/2026-04-27-session.md
[2026-04-28 20:30] FIX CorelDRAW X6 兼容性修复 — 形状 duck-typing、disconnect 不 Quit、reconnect_on_failure=False、ExportEx 无 struct、测试步骤顺序修正 → sessions/2026-04-28-1921.md

[2026-04-28 19:21] DONE Session Q&A — 提供 CorelDRAW X6 MCP 连通性测试指南，用户待跑 test_e2e.py 验证 → sessions/2026-04-28-1921.md

[2026-04-28 11:30] DONE feat-012/013/014/015 全部完成 — P0批量合并修复、P2代码质量、模板管理增强、工程图标题栏工具 → sessions/2026-04-28-1130.md

[2026-04-28 10:00] DECISION 新增 feat-012/013/014/015 修复批量合并/模板管理/工程图/代码质量问题，feat-011/010 延后 → decisions/sprint-2-plan.md

[2026-04-28 00:38] WIP Session 开始，状态汇报完成，等待确认 feat-011 任务 → sessions/2026-04-28-0038.md


[2026-04-27] DECISION 公司派单升级为多智能体模式：Supervisor + Local Agent SubGraph，SSE 长连接通信，JWT 认证，预留设计已固化 → decisions/sprint-2-plan.md

[2026-04-27] DECISION 架构调整：Agent 移至本地运行，新增 feat-011 LiteLLM Proxy，feat-006/007/008/009 标记为公司派单预留暂不实现 → decisions/sprint-2-plan.md

[2026-04-27] DECISION 新增 feat-010：Agent 层迁移至 LangGraph，支持 RAG + 记忆 + 公司级多业务域，在 feat-006 完成后启动 → decisions/sprint-2-plan.md

[2026-04-27] DECISION 第二阶段规划完成，新增 feat-005～feat-010（多工作站分布式架构 + LangGraph 迁移） → decisions/sprint-2-plan.md

[2026-04-27] DONE feat-005 MCP Server HTTP 模式完成 — server.py 支持 MCP_TRANSPORT env，新增 .mcp.json，uvicorn 依赖已补 → decisions/sprint-2-plan.md

[2026-04-27] DONE 第一阶段MVP完成 — feat-002/003/004 全部 passes=true，Agent编排层+端到端测试就绪 → sessions/2026-04-27-session.md

[2026-04-27] DONE feat-002核心工具实现完成，53个MCP工具函数上线，feat-002→passes=true → sessions/2026-04-27-session.md

[2026-04-23] DECISION 项目 harness 初始化完成 → .harness/registry/decisions/init.md

[2026-04-23 13:49] FIX 修复 install.sh 中 Codex/OpenCode 源文件名错误（致命 bug），更新 README 目录结构和初始化说明 → sessions/2026-04-23-1349.md

[初始化日期] DECISION 项目 harness 初始化，建立 Session 协议框架 → decisions/init.md
