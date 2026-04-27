# 变更日志

> 记录所有方向调整、需求变更、功能取消。
> Agent 每次 Sprint 规划前必读，避免重复已否决的方向。
> 格式：最新在上。

---

## 变更记录

### [2026-04-27] DIRECTION 多模型支持 — runner.py 增加 OpenAI 兼容 provider

- **原因**：用户需要支持 DeepSeek/Qwen 等国产模型，不能只绑 Claude
- **影响**：SignageAgent 增加 provider 参数，内部拆分为 Anthropic 和 OpenAI 两套调用循环。工具定义自动适配两套格式。视觉反馈路径需在 OpenAI 下改用 image_url 格式。
- **处理**：agent/runner.py 已重构完成，Anthropic 路径向后兼容

### [2026-04-27] MILESTONE Phase 1 MVP 完成

- **原因**：feat-001/002/003/004 全部 passes=true
- **影响**：53 个 MCP 工具就绪、Agent 编排层就绪、端到端测试脚本就绪、视觉反馈闭环就绪。尚未在 Windows 环境实际运行验证。
- **处理**：Phase 2 批量生产阶段准备中

### [2026-04-27] SCOPE Phase 1 MVP 范围确认

- **原因**：从 docs/signage-agent-design.md 实施路线图提取 Phase 1 范围，对齐 .harness/ 产品文件
- **影响**：Phase 1 包含 4 项功能（feat-001 至 feat-004），已全部实现。Phase 2-4 需求录入 backlog。
- **处理**：product/vision.md、product/backlog.md、product/changes.md 从空壳模板更新为实际内容
