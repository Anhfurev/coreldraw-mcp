# 第二阶段规划 — Agent 本地化 + LLM 代理 + 多智能体预留

**日期**：2026-04-27  
**背景**：第一阶段 MVP 已完成（单机验证通过）。架构经过多轮讨论后确定最终方案。

---

## 当前活跃架构（Agent 本地化 + LLM 代理）

**核心决策**：Agent 在设计师 PC 本地运行，LLM 调用通过公司服务器 LiteLLM Proxy 统一管控。

```
设计师 PC（每台独立运行）
├── app.py / Claude / OpenCode   ← 任意 UI 触发
├── runner.py (Local Agent)      ← LangGraph，本地推理
├── server.py (MCP Server :8765) ← HTTP 模式，feat-005 已完成
├── CorelDRAW
└── 模板 / 设计文件

        ↕ LLM API 调用（OpenAI 兼容接口）

公司服务器
└── LiteLLM Proxy (feat-011)
    ├── API Key 统一管理
    ├── 用量监控 / 限速
    └── 路由 → Claude / DeepSeek / Qwen
```

**设计原则**：
- 文件和工具全部本地，无网络延迟和传输开销
- 只有 LLM API 调用走服务器，管控成本和 Key 安全
- 设计师可用 Claude/OpenCode 直连 `.mcp.json`，无需公司 Agent 也能工作

---

## 活跃功能列表

| feat | 名称 | 状态 |
|------|------|------|
| feat-005 | MCP Server HTTP 模式 | ✅ 已完成 |
| feat-011 | LiteLLM Proxy 部署 | 待实现 |
| feat-010 | Agent 迁移至 LangGraph + RAG | 待实现，依赖 feat-011 |

---

## 预留架构：公司派单多智能体模式

> **状态**：设计已确定，暂不实现（feat-006/007/008/009）。待业务需要时按此方案启动。

### 架构图

```
公司服务器：Supervisor Agent（LangGraph）
  ├── 任务分析 Node        ← 理解需求、拆分子任务
  ├── 设计师路由 Node       ← 查注册中心，选可用工作站
  ├── 任务派单 Node         ← 通过 SSE 长连接推送任务
  ├── 进度监控 Node
  └── 结果聚合 Node

  注册中心（feat-008）
  ├── 工作站表：id / hostname / last_heartbeat / status
  ├── 心跳：本地 Agent 每 30 秒上报
  └── 认证：工作站 ID + 密钥，任务携带 JWT

每台设计师 PC：Local Agent SubGraph（LangGraph）
  ├── 任务监听 Node         ← SSE 长连接，接收 Supervisor 推送
  ├── LLM 推理 Node         ← via LiteLLM Proxy
  ├── MCP 工具调用 Node     ← 本地 CorelDRAW 操作
  └── 结果上报 Node         ← 回传 Supervisor
```

### 通信方式：SSE 长连接（推荐）

- 本地 Agent 启动时向公司服务器发起 HTTP 长连接（SSE），主动连出，无需开放本地端口，天然穿透 NAT
- 公司 Supervisor 通过 SSE 通道推送任务
- 同步版本优先（HTTP 阻塞等结果）→ 验证后升级为异步队列

### 认证安全方案

- 本地 Agent 启动：工作站 ID + 预共享密钥 → 换取 JWT Token
- Supervisor 派单：任务 Payload 附带签名 JWT，本地 Agent 验签后执行
- 敏感操作（覆盖模板、批量删除）需额外 permission scope

### LLM 成本优化

- Supervisor：用便宜模型（DeepSeek/Qwen）做路由和拆分，不需要视觉能力
- Local Agent：复杂推理和视觉检查时调用 Claude，批量简单任务走规则不调 LLM

### 实现顺序（待启动时）

1. feat-006：SSE 通信层 + 基础任务队列
2. feat-007：Local Agent 升级为 LangGraph SubGraph，支持 `--mode worker` 队列触发
3. feat-008：注册中心 + 心跳 + JWT 认证
4. feat-009：并发锁（本地 Agent 与 Worker 模式共享锁协议）

---

## 架构演进历史

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-04-27 | 初定任务队列 + 哑 Worker 方案 | MVP 阶段最简单 |
| 2026-04-27 | Worker 合并进 Agent（--mode 参数） | Worker 和 Agent 职责重叠，无需两个进程 |
| 2026-04-27 | Agent 移至本地，服务器只做 LLM Proxy | Agent 需要访问本地文件和 CorelDRAW |
| 2026-04-27 | 派单模式升级为多智能体（Supervisor + SubGraph） | 比哑 Worker 更灵活，与 LangGraph 天然契合 |
