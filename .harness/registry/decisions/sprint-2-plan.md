# 第二阶段规划 — 多工作站分布式设计架构

**日期**：2026-04-27  
**背景**：第一阶段 MVP 已完成（单机验证通过）。用户确认采用任务队列架构支持多工作站场景。

---

## 架构决策

**核心方案**：任务队列 + 本地 Worker（方案 B）

```
中心服务器
├── app.py (Streamlit UI)
├── runner.py (Agent，dispatch 到队列)
└── SQLite 任务队列

每台设计师 PC
├── server/server.py  (MCP Server，HTTP 模式，127.0.0.1:8765)
├── worker/polling_worker.py  (轮询队列，调本地 MCP 执行)
└── CorelDRAW
```

**本地 Agent 直连**（无需中心调度）：
- 设计师可用 Claude/OpenCode 直接连本地 MCP Server（HTTP 模式）
- .mcp.json 指向 `http://127.0.0.1:8765/mcp`
- 与中心 Agent 走队列互不干扰

**并发保护**：本地 Worker 拿任务前先请求操作锁，避免与本地 Agent 冲突。

---

## 功能列表

| feat | 名称 | 依赖 | 优先级 |
|------|------|------|--------|
| feat-005 | MCP Server HTTP 模式 | feat-001 | P0，本次已完成 |
| feat-006 | 任务队列基础层 | feat-005 | P1 |
| feat-007 | 设计师本地 Worker | feat-006 | P1 |
| feat-008 | 工作站注册与在线管理 | feat-007 | P2 |
| feat-009 | 操作并发锁机制 | feat-007 | P2 |

---

## 功能描述

**feat-005**（已完成）：MCP Server 切换至 streamable-http transport，env 可配置（MCP_TRANSPORT / MCP_HOST / MCP_PORT），默认向后兼容 stdio。新增 `.mcp.json` 供 Claude/OpenCode 本地连接。

**feat-006**：基于 SQLite 实现中心任务队列。Task 含 id、workstation_id、tool_name、arguments、status（pending/running/done/failed）、result、created_at、updated_at。提供 enqueue / dequeue / complete / fail 接口。

**feat-007**：`worker/polling_worker.py`，约 100 行。启动时向中心注册工作站 ID，轮询队列获取分配给本工作站的任务，通过 HTTP 调用本地 MCP Server 执行，将结果写回队列。

**feat-008**：工作站注册表（SQLite），记录 workstation_id、hostname、last_heartbeat、status。Worker 每 30 秒心跳，中心 Agent 按在线工作站分配任务。

**feat-009**：本地 `lock.json` 文件锁。Worker 拿任务前 acquire，完成后 release。Claude/OpenCode 直连时也通过 MCP tool `acquire_lock` / `release_lock` 参与锁协议，防止并发写同一 CorelDRAW 文档。

**feat-010**：将 `runner.py` 的自定义 API 调用循环迁移至 LangGraph StateGraph。
- CorelDRAW 工具集作为子图节点保留，现有工具函数无需改动
- 通过 LangGraph Checkpointer 实现对话历史与用户偏好持久化（SQLite 或 Redis）
- 接入 RAG 管道：向量数据库（Chroma）+ 公司知识库嵌入（设计规范、产品目录等）
- 其他业务域（CRM、文件管理等）作为独立节点接入同一图，支持跨域协作
- LangGraph 原生支持 MCP 工具，现有 MCP Server 无需改动
- 迁移成本预估：约 2 天，现有逻辑可完整复用

**选型依据**（对比 LangChain / AutoGen）：LangGraph 的有状态图模型天然契合"多步骤设计任务 + 持久记忆 + 多业务域协作"场景；LangChain 抽象层过重调试困难；AutoGen 偏研究向生产稳定性不足。
