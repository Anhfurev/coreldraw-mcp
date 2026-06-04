# CorelDRAW MCP 自动化设计

> 通过 MCP 协议让 AI 直接操控 CorelDRAW，实现设计文件的自动化生成与处理

## 项目简介

本项目为 CorelDRAW 提供 MCP（Model Context Protocol）工具服务，让 AI Agent 能够通过 COM API 直接操作 CorelDRAW，完成文档创建、文字替换、图形操作、批量导出等设计任务。

**核心价值**

- AI Agent 通过自然语言指令直接驱动 CorelDRAW 完成设计操作，无需手动重复执行
- 支持模板填充、批量导出 PDF/DXF/PNG 等生产文件格式
- 提供 Streamlit Chat UI 供设计师本地调试，也可通过 MCP 协议接入 Claude Desktop 等客户端

---

## 架构概览

```
┌─────────────────────────────────────────────────┐
│              设计师本地机器（Windows）             │
│                                                 │
│  ┌──────────────┐      ┌────────────────────┐  │
│  │  AI Agent    │─MCP─▶│   MCP Server       │  │
│  │ (runner.py)  │◀─────│ (FastMCP / HTTP)   │  │
│  │              │      │                    │  │
│  │  Streamlit   │      │  CorelDRAW COM API │  │
│  │  Chat UI     │      │  (pywin32)         │  │
│  └──────────────┘      └────────┬───────────┘  │
│                                 │               │
│                         ┌───────▼──────┐        │
│                         │  CorelDRAW   │        │
│                         │  (本地进程)  │        │
│                         └──────────────┘        │
└─────────────────────────────────────────────────┘
         │ LLM API 调用
         ▼
  公司 LiteLLM Proxy（规划中）
  或 Anthropic / DeepSeek / Qwen 直连
```

**三层结构**

| 层 | 组件 | 说明 |
|----|------|------|
| Agent 层 | `server/agent/runner.py` | LLM 工具调用主循环，支持 Claude / DeepSeek / Qwen |
| MCP 工具层 | `server/server.py` + `server/tools/` | 30+ 个 CorelDRAW 操作工具，HTTP 或 stdio 传输 |
| CorelDRAW 层 | `server/core/connection.py` | 通过 pywin32 COM API 驱动本地 CorelDRAW |

**MCP 工具分类**

| 模块 | 工具 | 功能 |
|------|------|------|
| `document` | 7 个 | 模板打开、新建、保存、关闭、页面管理 |
| `shapes` | 11 个 | 矩形/椭圆/线段绘制、SVG/图片导入、布尔运算 |
| `text` | 5 个 | 文字内容替换、样式设置、溢出检测、转曲 |
| `colors` | 8 个 | CMYK/RGB/Pantone 填色、描边、RGB 合规检测 |
| `layers` | 5 个 | 图层创建、查询、分配、显隐、锁定 |
| `export` | 7 个 | PDF/DXF/AI/SVG/PNG 导出、视觉预览、批量导出 |
| `preflight` | 4 个 | 尺寸检查、文字溢出、缺字体、颜色报告 |
| `data_merge` | 3 个 | Excel 数据读取、条形码/二维码生成 |

---

## 环境要求

- **操作系统**：Windows 10/11（CorelDRAW COM API 仅支持 Windows）
- **Python**：3.11+
- **CorelDRAW**：X6 或更高版本（需已安装并激活；X6 已验证兼容）
- **LLM API Key**：Anthropic Claude、DeepSeek 或阿里云百炼任选其一

---

## 安装

```bash
# 1. 克隆项目
git clone <repo-url>
cd CorelDRAW-mcp

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量（复制示例后填入真实 Key）
copy .env.example .env
```

`.env` 最小配置示例：

```dotenv
# 选择一个 LLM Provider
ANTHROPIC_API_KEY=sk-ant-xxxxx

# MCP Server 传输模式（stdio 或 streamable-http）
MCP_TRANSPORT=streamable-http
MCP_HOST=127.0.0.1
MCP_PORT=8765
```

---

## 运行

### 方式一：Streamlit 对话界面（推荐体验）

```bash
# 确保 CorelDRAW 已启动，然后直接运行：
streamlit run server/app.py
```

浏览器打开 `http://localhost:8501`，在侧边栏填入 API Key，即可用自然语言操控 CorelDRAW。

> **注意**：Streamlit UI 直接通过 COM 连接 CorelDRAW，无需另开 server.py。
> 同时运行 server.py 和 app.py 会建立两个 COM 连接，可能引发冲突。

### 方式二：Claude Desktop / OpenCode 直连（MCP HTTP 模式）

项目根目录已包含 `.mcp.json`，Claude Desktop 或 OpenCode 可直接发现并连接本地 MCP Server：

```bash
# 启动 MCP Server（HTTP 模式）
cd server
MCP_TRANSPORT=streamable-http python server.py
```

### 方式三：stdio 模式（供 MCP 客户端调用）

```bash
cd server
MCP_TRANSPORT=stdio python server.py
```

---

## 典型使用场景

**批量生成门牌**

1. 准备 CDR 模板文件（含文字占位符），放入 `server/templates/`
2. 准备 Excel 数据表（每行一条门牌信息）
3. 在对话框输入：`批量生成门牌，模板用 room_template.cdr，数据用 rooms.xlsx`
4. Agent 自动读取数据、逐条填充模板、印前检查、导出 PDF 和 DXF

**单条快速出稿**

```
生成一块 300×150mm 的门牌，房间号 301，部门名"研发中心"，
背景色 CMYK(0,0,0,80)，导出印刷 PDF 和激光 DXF
```

---

## 目录结构

```
sign-CorelDRAW-mcp-opencode/
├── server/
│   ├── server.py          # MCP Server 入口
│   ├── app.py             # Streamlit Web UI
│   ├── agent/
│   │   ├── runner.py      # Agent 主循环（LLM + 工具调用）
│   │   └── prompts.py     # System prompt
│   ├── tools/             # MCP 工具实现（30+ 个工具）
│   ├── core/              # CorelDRAW COM 连接与公共模型
│   ├── config/            # 配置与模板注册表
│   └── templates/         # CDR 模板文件目录
├── docs/                  # 架构设计文档与示意图
├── requirements.txt
└── pyproject.toml
```

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 代码检查
ruff check server/

# 端到端测试（需本地 CorelDRAW 已启动）
cd server
python test_e2e.py
```

---

## 路线图

| 阶段 | 状态 | 内容 |
|------|------|------|
| 第一阶段 MVP | ✅ 已完成 | MCP Server + 30+ 工具 + Agent 主循环 + HTTP 模式 |
| 第二阶段 | 进行中 | LiteLLM Proxy 统一 LLM 管理、Agent 编排迁移至 LangGraph |
| 预留设计 | 架构已规划 | 公司派单模式：任务队列、多工作站 Worker、并发锁 |

---

## License

MIT
