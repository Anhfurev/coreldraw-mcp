# CorelDRAW Signage MCP

> Let AI drive CorelDRAW directly via the Model Context Protocol — automated design file generation at scale

[中文文档](README-CN.md)

## Overview

This project exposes CorelDRAW as an MCP (Model Context Protocol) tool server. An AI Agent connects via COM API to create documents, replace text, manipulate shapes, run preflight checks, and batch-export production files — all from natural language instructions.

**Key capabilities**

- Natural language → CorelDRAW operations, no manual repetition
- Template filling and batch export to PDF / DXF / PNG
- Streamlit Chat UI for local debugging, or connect any MCP-compatible client (Claude Desktop, OpenCode, etc.)

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Designer's machine (Windows)        │
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
│                         │ (local proc) │        │
│                         └──────────────┘        │
└─────────────────────────────────────────────────┘
         │ LLM API calls
         ▼
  Company LiteLLM Proxy (planned)
  or Anthropic / DeepSeek / Qwen direct
```

**Three-layer structure**

| Layer | Component | Description |
|-------|-----------|-------------|
| Agent | `server/agent/runner.py` | LLM tool-call loop; supports Claude / DeepSeek / Qwen |
| MCP tools | `server/server.py` + `server/tools/` | 30+ CorelDRAW tools, HTTP or stdio transport |
| CorelDRAW | `server/core/connection.py` | Drives local CorelDRAW via pywin32 COM API |

**Tool modules**

| Module | Tools | Functionality |
|--------|-------|---------------|
| `document` | 7 | Open template, create, save, close, page management |
| `shapes` | 11 | Rectangle / ellipse / line drawing, SVG / image import, boolean ops |
| `text` | 5 | Text replacement, style, overflow detection, convert to curves |
| `colors` | 8 | CMYK / RGB / Pantone fill & stroke, RGB compliance check |
| `layers` | 5 | Create, query, assign, show/hide, lock layers |
| `export` | 7 | PDF / DXF / AI / SVG / PNG export, visual preview, batch export |
| `preflight` | 4 | Size check, text overflow, missing fonts, color report |
| `data_merge` | 3 | Excel data read, barcode / QR code generation |

---

## Requirements

- **OS**: Windows 10 / 11 (CorelDRAW COM API is Windows-only)
- **Python**: 3.11+, **64-bit** (must match CorelDRAW's bitness)
- **CorelDRAW**: X6 or later (must be installed and activated; X6 verified compatible)
- **LLM API Key**: one of Anthropic Claude, DeepSeek, or Alibaba Qwen

---

## Installation

```bash
# 1. Clone the repo
git clone <repo-url>
cd coreldraw-signage-mcp

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env
# then fill in a real LLM API key
```

Minimal `.env`:

```dotenv
# Pick one LLM provider
ANTHROPIC_API_KEY=sk-ant-xxxxx

# MCP Server transport (stdio or streamable-http)
MCP_TRANSPORT=streamable-http
MCP_HOST=127.0.0.1
MCP_PORT=8765
```

---

## Usage

### Option 1 — Streamlit Chat UI (recommended for quick start)

```bash
# Make sure CorelDRAW is running first, then:
streamlit run server/app.py
```

Open `http://localhost:8501`, enter your API key in the sidebar, and control CorelDRAW with natural language.

> **Note**: The Streamlit UI connects to CorelDRAW directly via COM. Do **not** run `server.py` at the same time — two simultaneous COM connections can cause conflicts.

### Option 2 — Claude Desktop / OpenCode via MCP HTTP

The repo ships a `.mcp.json` that Claude Desktop and OpenCode auto-discover:

```bash
# Start MCP Server in HTTP mode
cd server
MCP_TRANSPORT=streamable-http python server.py
```

### Option 3 — stdio mode (for MCP client integration)

```bash
cd server
MCP_TRANSPORT=stdio python server.py
```

---

## Example prompts

**Batch room-number signs**

1. Place a CDR template (with text placeholders) in `server/templates/`
2. Prepare an Excel sheet (one sign per row)
3. Type: `Batch generate room signs, template: room_template.cdr, data: rooms.xlsx`
4. The agent reads the data, fills the template row by row, runs preflight, and exports PDF + DXF

**Single sign, quick output**

```
Create a 300×150 mm room sign, room number 301, department "R&D Center",
background CMYK(0,0,0,80), export print-ready PDF and laser-cut DXF
```

---

## Directory structure

```
coreldraw-signage-mcp/
├── server/
│   ├── server.py          # MCP Server entry point
│   ├── app.py             # Streamlit Web UI
│   ├── agent/
│   │   ├── runner.py      # Agent main loop (LLM + tool calls)
│   │   └── prompts.py     # System prompt
│   ├── tools/             # MCP tool implementations (30+ tools)
│   ├── core/              # CorelDRAW COM connection & shared models
│   ├── config/            # Settings & template registry
│   └── templates/         # CDR template files
├── docs/                  # Architecture docs & diagrams
├── CONTRIBUTING.md
├── LICENSE
├── NOTICE
├── requirements.txt
└── pyproject.toml
```

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Lint
ruff check server/

# End-to-end test (requires CorelDRAW running locally)
cd server
python test_e2e.py
```

---

## Roadmap

| Phase | Status | Scope |
|-------|--------|-------|
| Phase 1 MVP | ✅ Done | MCP Server + 30+ tools + Agent loop + HTTP transport |
| Phase 2 | In progress | LiteLLM Proxy for unified LLM management; migrate agent orchestration to LangGraph |
| Planned | Architecture drafted | Company dispatch mode: task queue, multi-workstation workers, concurrency lock |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Note: the COM API is Windows-only, so end-to-end testing requires a Windows machine with CorelDRAW installed.

---

## License

Apache 2.0 © 2026 深圳市玄熵智能科技有限责任公司 (Xuanshang Intelligent Technology Co., Ltd., Shenzhen)
