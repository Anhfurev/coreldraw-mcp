# 已知约束

> 每次 Session 发现新约束时，追加到本文件。不要删除历史条目。

## 架构约束

- Agent 部署在设计师本地 PC，LLM API 调用通过公司服务器 LiteLLM Proxy 统一管控（不直连 AI 厂商）
  原因：API Key 安全、用量监控、多模型路由统一管理
- CorelDRAW COM API 仅 Windows 环境可用，需 CorelDRAW X6+ 已安装并激活
  原因：pywin32 COM 调用依赖 Windows 注册表和本地 CorelDRAW 进程

## 已知坑

（初始化时无人工确认的已知坑）

## 发现时间

- [2026-04-23] 初始化时记录
