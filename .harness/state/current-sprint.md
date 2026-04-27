# 当前阶段目标

**阶段**：第一阶段（MVP）
**目标**：构建一套 AI Agent + MCP Server + CorelDRAW COM API 的自动化工业标识设计系统

## 本阶段功能列表

- **feat-001**: MCP Server 基础框架搭建 — 基于 fastmcp 建立 MCP Server 骨架，实现 CorelDRAW COM 连接管理与统一错误处理
- **feat-002**: 核心工具实现 — 实现文档管理、文字替换、PDF/DXF 导出等基础工具，支持模板打开与内容替换
- **feat-003**: 单条记录门牌生成端到端验证 — 完成从打开模板、替换文字、印前检查到导出 PDF/DXF 的完整单条流程
- **feat-004**: 视觉预览反馈基础版 — 实现 export_preview_png 工具，支持 Agent 视觉检查与迭代修正

## 完成标准

本阶段完成 = features.json 中所有条目 passes 为 true
