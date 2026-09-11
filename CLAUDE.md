# CorelDRAW Signage Agent — Agent 工作规范

> 非自推信息。harness 流程由 Hook 强制执行，本文不重复。

## 平台核心约束

- **所有 COM 调用仅 Windows 有效**。macOS 只能做语法检查（AST parse + import 不含 COM 的模块）
- **Python 必须是 64-bit**（`pywin32` 与 CorelDRAW 位数必须一致，32-bit Python 会导致 COM 调用静默失败）
- **CorelDRAW 必须预先启动**，MCP Server 连接失败不会自动拉起

## 入口与运行方式

| 入口 | 命令 | 用途 |
|------|------|------|
| MCP Server | `cd server && python server.py` | 工具提供方，供 Claude/OpenCode 连接 |
| Streamlit UI | `cd server && streamlit run app.py` | 设计师调试用的 Chat 界面 |
| Agent 脚本 | `from agent.runner import SignageAgent` | 编程方式调用 |

MCP Server 默认 `stdio` 传输，设 `MCP_TRANSPORT=streamable-http` 启动 HTTP 模式（端口 8765），`.mcp.json` 已配好连接地址。

## 工具层架构约定（添加/修改工具时必须遵守）

1. **工具是裸函数**，不用 `@mcp.tool()` 装饰器。由 `server/server.py` 的 `register_tools()` 统一 `mcp.add_tool()`。
2. **所有工具返回 `ToolResult`**（`from core.models import ToolResult`），用 `ToolResult.ok()` / `ToolResult.fail()` 构建。
3. **统一模式**：
   ```python
   def tool_name(param: type) -> ToolResult:
       conn = get_connection()
       if not conn.status.connected:
           return ToolResult.fail("CorelDRAW 未连接")
       result = conn.safe_call(lambda: actual_com_work())
       if result["success"]: return ToolResult.ok(...)
       return ToolResult.fail(result.get("error", "失败"))
   ```
4. **所有工具注册在 `server.py`**，新增工具必须同时在该文件加 `mcp.add_tool()`。
5. **函数 docstring 即 MCP 工具描述**，会被 Agent 看到，写清楚参数含义。
6. **COM 常量是硬编码整数**（`cdrDXF=86`, `cdrPNG=776`, `cdrMillimeter=2`, `cdrTextShape=3` 等）。这些常量来自 CorelDRAW 类型库，只有 Windows 上运行 `makepy` 才能生成类型存根，不要试图从 `win32com.client.constants` 导入。

## 已知的代码重复与特殊处理

- `_find_shape()` 在 `shapes.py`、`colors.py`、`layers.py` 三处重复（各有细微差异，尚未统一）
- `check_rgb_colors` 在两个文件存在：`colors.py` 用于交互式检查，`preflight.py` 用于批量质检。Agent runner 里做了去重。
- PNG 导出有两套 API：`ExportBitmap`（主方案）和 `Export`（fallback），因不同 CorelDRAW 版本行为不一
- Pantone 填充的 `FindPantone` 方法在不同 CorelDRAW 版本路径不同，用了 try/except 双方案
- **`tools/vision.py` 的 `view_canvas` 是全项目唯一不返回 `ToolResult` 的工具**：MCP 图片内容必须
  通过 `fastmcp.utilities.types.Image` 类型返回才会被自动转换为图片内容块（而不是被序列化成一段
  JSON 文本）。成功时返回 `Image(data=..., format="png")`，失败时返回一段说明文字（str）。
  新增其他"视觉/图片返回"类工具时应遵循同样的例外模式，其余所有工具仍必须遵守 `ToolResult` 约定。

## Agent (runner.py) 关键约定

- `SignageAgent(provider="anthropic"|"openai", model=..., api_key=..., base_url=...)`
- API Key 环境变量：`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `DASHSCOPE_API_KEY` / `DEEPSEEK_API_KEY`
- `run_single()` — 同步阻塞，返回 dict
- `run_single_stream()` — 生成器，逐事件 yield（供 Streamlit 消费）。事件类型：`thinking`, `text`, `tool_call`, `tool_result`, `preview`, `final`, `error`
- Provider 为 `openai` 时，DeepSeek 用 `base_url="https://api.deepseek.com"`，千问用 `base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"`
- 工具定义通过 `inspect.signature` 自动从函数签名生成

## 校验命令

```
ruff check server/      # lint（line-length=120, py311, E/F/I/N/W）
python test_e2e.py      # 端到端测试（需 Windows + CorelDRAW 运行中）
```

无 pytest 单元测试（dev 依赖已声明但未编写测试文件）。

## 环境配置

```bash
cp .env.example .env   # 填一个 LLM API Key 即可
```

`.env` 最小内容：任意一个 `*_API_KEY` + `MCP_TRANSPORT`（默认 stdio）。其他均有默认值。

## 当前阶段

Phase 1 MVP 全部完成（feat-001～004 passes=true）。Phase 2 批量生产待开始。详见 `.harness/product/backlog.md`。
