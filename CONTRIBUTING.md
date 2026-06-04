# Contributing to CorelDRAW Signage MCP

## 平台限制说明

本项目核心功能依赖 **Windows + CorelDRAW COM API**，开发环境要求：

- Windows 10/11
- CorelDRAW X6 或更高版本（需已安装激活）
- Python 3.11+，**必须是 64-bit**（与 CorelDRAW 位数一致）

在非 Windows 环境下，只能做语法检查（`ruff check`），无法运行端到端测试。

---

## 快速开始

```bash
git clone https://github.com/<your-fork>/coreldraw-signage-mcp
cd coreldraw-signage-mcp

python -m venv .venv
.venv\Scripts\activate

pip install -e ".[dev]"

cp .env.example .env
# 填入至少一个 LLM API Key
```

---

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：

| 前缀 | 用途 |
|------|------|
| `feat:` | 新增工具或功能 |
| `fix:` | Bug 修复 |
| `docs:` | 文档变更 |
| `refactor:` | 不影响功能的代码重构 |
| `chore:` | 构建/工具链变更 |

## 代码规范

提交前运行 lint：

```bash
ruff check server/
```

配置见 `pyproject.toml`：`line-length=120`，`target-version=py311`，`select=E,F,I,N,W`。

---

## 新增 MCP 工具

新增工具必须同时完成以下三件事，缺一不可：

1. **实现函数**：放在 `server/tools/` 对应模块，返回 `ToolResult`，参见 [CLAUDE.md](CLAUDE.md) 中的统一模式
2. **注册工具**：在 `server/server.py` 的 `register_tools()` 中调用 `mcp.add_tool()`
3. **写 docstring**：函数 docstring 会直接暴露给 Agent，描述清楚参数含义

COM 常量用硬编码整数（`cdrPNG=776` 等），不从 `win32com.client.constants` 导入。

---

## Pull Request 流程

1. Fork → 新建分支（`feat/your-feature` 或 `fix/your-bug`）
2. 实现 + `ruff check` 通过
3. 在 PR 描述中说明：改了哪些工具、在哪个版本 CorelDRAW 测试过
4. 如果无法在本地测试（非 Windows），请在 PR 中注明

---

## 问题反馈

- Bug 报告：使用 GitHub Issues，附上 CorelDRAW 版本、Python 版本和错误日志
- 功能建议：先开 Issue 讨论，避免重复劳动
