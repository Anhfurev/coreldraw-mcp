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
| MCP tools | `server/server.py` + `server/tools/` | 81 CorelDRAW tools, HTTP or stdio transport |
| CorelDRAW | `server/core/connection.py` | Drives local CorelDRAW via pywin32 COM API |

**Tool modules**

| Module | Tools | Functionality |
|--------|-------|---------------|
| `document` | 7 | Open template, create, save, close, page management |
| `shapes` | 17 | Rectangle / ellipse / line drawing, SVG / image import, boolean ops, align/distribute/rotate/scale/group, **rename, duplicate (single/batch/multi-shape), lock, flip** |
| `text` | 6 | Text replacement, **read full content**, style (font/size/bold/italic/**underline/line-spacing/char-spacing**), overflow detection, convert to curves |
| `colors` | 8 | CMYK / RGB / Pantone fill & stroke, RGB compliance check |
| `layers` | 5 | Create, query, assign, show/hide, lock layers |
| `export` | 7 | PDF / DXF / AI / SVG / PNG export, visual preview, batch export |
| `preflight` | 4 | Size check, text overflow, missing fonts, color report |
| `data_merge` | 3 | Excel data read, barcode / QR code generation |
| `vision` | 1 | **`view_canvas`** — return a live screenshot of the canvas as an actual image the agent can see |

**Shape editing tools (rename / resize / duplicate / lock / flip)**

| Tool | Purpose |
|------|---------|
| `set_shape_size` | Set a shape's exact width × height (mm) |
| `set_shape_position` | Move a shape to an exact x, y |
| `rename_shape` | Rename a shape (e.g. `box_1` → `room_301`) |
| `duplicate_shape` | Copy one shape, offset by x/y, optional new name |
| `duplicate_shape_batch` | Copy one shape N times in one call, with `{name}`/`{n}` name-pattern numbering — e.g. stamp out a row of boxes named `box_1`…`box_20` |
| `duplicate_shapes` | Copy a whole set of shapes together, keeping their relative layout |
| `set_shape_locked` | Lock/unlock a shape against accidental edits |
| `flip_shape` | Mirror a shape horizontally or vertically |
| `save_document` | Save (or Save As) the current document |

These cover the "resize a box, name it, duplicate it N times, save" workflow end to end.

**Vision — can the agent see the canvas?**

Two different kinds of "seeing" are available:

- **Structured (no vision needed)**: `select_shapes()`, `find_shape_by_name()`, and
  `get_document_info()` return every shape's name, id, exact position/size, rotation,
  lock state and layer as plain data — an agent can inspect and reason about the whole
  canvas without ever looking at a picture.
- **Actual vision**: `view_canvas(width=1000)` takes a live screenshot of the current
  page and returns it as a real image in the tool result (via FastMCP's `Image` type,
  MCP `ImageContent`) — not a file path. A vision-capable client (Claude Desktop/Code)
  sees it directly, the same as a pasted screenshot, useful for a final visual sanity
  check after a batch of edits. This is the one tool in the project that doesn't return
  `ToolResult` — see the note in `CLAUDE.md`/`AGENTS.md`.

---

## Requirements

- **OS**: Windows 10 / 11 (CorelDRAW COM API is Windows-only). Note: CorelDRAW's modern
  native Mac app (2024+) has no scripting/automation interface at all (no AppleScript
  dictionary, no equivalent of COM) — verified by inspecting the app bundle for a `.sdef`
  file and `Info.plist` scripting keys, both absent. There is currently no way for this
  project, or any external tool, to drive CorelDRAW running on macOS.
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

### Option 2 — Claude Code / OpenCode via project `.mcp.json` (HTTP)

The repo ships a `.mcp.json` that Claude Code and OpenCode auto-discover as a
project-level MCP config (this is a different mechanism from the literal Claude
Desktop *app* — see Option 2b if that's what you're using):

```bash
# Start MCP Server in HTTP mode
cd server
MCP_TRANSPORT=streamable-http python server.py
```

### Option 2b — Claude Desktop app (recommended for a single Windows machine)

The Claude Desktop app does **not** read this repo's `.mcp.json` — it has its own,
separate global config file, and it launches/manages the server process itself over
stdio rather than you starting `server.py` by hand. No LLM API key is needed for this
path (Claude Desktop uses your own Claude subscription; the `.env` API key is only
used by the standalone Streamlit chat UI in Option 1).

1. Edit (create if missing) `%APPDATA%\Claude\claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "coreldraw": {
         "command": "C:\\path\\to\\coreldraw-mcp\\.venv\\Scripts\\python.exe",
         "args": ["C:\\path\\to\\coreldraw-mcp\\server\\server.py"]
       }
     }
   }
   ```
   Use the **full path** to the `python.exe` inside this project's virtualenv (not a
   bare `python`), so it runs with the right dependencies installed.
2. Make sure CorelDRAW is already running.
3. Fully quit and reopen Claude Desktop. It starts/stops `server.py` automatically —
   you should never need to run it manually in this mode.
4. In a new chat, ask Claude Desktop to do something with CorelDRAW (e.g. "list all
   shapes on the current page") — it should show the tool call.

### Option 3 — stdio mode (for MCP client integration)

```bash
cd server
MCP_TRANSPORT=stdio python server.py
```

### Option 4 — Windows runs the server, another machine (e.g. a Mac) runs the client

CorelDRAW's automation API is COM, which only exists on Windows — there is no Mac/Linux
equivalent, so the server process itself must run on the Windows box that has CorelDRAW
installed. A client on another machine (a MacBook running Claude Desktop/Claude Code, for
example) can still drive it, over the network, using the same HTTP transport as Option 2:

1. On the **Windows** machine (with CorelDRAW running):
   ```bash
   cd server
   set MCP_HOST=0.0.0.0
   set MCP_TRANSPORT=streamable-http
   python server.py
   ```
   `0.0.0.0` binds to all network interfaces instead of just localhost. Find this
   machine's LAN IP with `ipconfig` (look for the `IPv4 Address`, e.g. `192.168.1.50`).
   Allow inbound TCP on `MCP_PORT` (default `8765`) through Windows Firewall.

2. On the **client** machine, point its MCP config at the Windows box's LAN IP instead of
   `127.0.0.1`. For Claude Desktop/Code, edit `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "coreldraw": {
         "type": "http",
         "url": "http://192.168.1.50:8765/mcp"
       }
     }
   }
   ```

Security note: this exposes the CorelDRAW automation endpoint to your LAN with no
authentication. Only do this on a trusted local network (e.g. behind your home/office
router), never expose the port directly to the internet.

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
#   c o r e l d r a w - m c p  
 