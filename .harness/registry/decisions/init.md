# 初始化记录

**日期**：2026-04-23
**执行**：Harness 初始化 Agent

## 项目概况

- **项目名**：CorelDRAW MCP 自动化设计服务
- **定位**：CorelDRAW MCP 通用辅助设计系统
- **技术栈**：Python + fastmcp + pywin32 + CorelDRAW COM API
- **当前状态**：需求与设计文档已完成（docs/signage-agent-design.md），代码尚未开始编写

## 确认的约束

（Q2 答案：无）

## 已知风险

（Q3 答案：无）

## 第一阶段范围（MVP）

1. **MCP Server 基础框架搭建** — 基于 fastmcp 建立 MCP Server 骨架，实现 CorelDRAW COM 连接管理与统一错误处理
2. **核心工具实现** — 实现文档管理、文字替换、PDF/DXF 导出等基础工具，支持模板打开与内容替换
3. **单条记录端到端验证** — 完成从打开模板、替换文字、印前检查到导出 PDF/DXF 的完整单条流程
4. **视觉预览反馈基础版** — 实现 export_preview_png 工具，支持 Agent 视觉检查与迭代修正
