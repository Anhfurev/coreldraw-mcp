# CorelDRAW MCP 自动化设计系统（原始设计文档）
## 需求与设计文档 v0.1

---

## 一、项目背景与目标

### 1.1 背景

CorelDRAW 设计工作流中存在大量高度重复的手工操作：
- 同一客户的多套规格标牌（尺寸不同、房间号/部门名不同）
- 同一设计的多种材质/工艺版本（印刷稿、激光切割稿、雕刻稿）
- 大型项目的批量交付（一个写字楼动辄数百块标识）
- 设计改稿反复（甲方换字、换色、换 logo）

目前这些工作大量依赖设计师手工操作 CorelDRAW，效率低、出错率高、难以标准化。

### 1.2 项目目标

构建一套 **AI Agent + MCP Server + CorelDRAW COM API** 的自动化设计系统，使 AI Agent 能够：

1. 理解自然语言或结构化需求（Excel、JSON）
2. 调用 MCP 工具操控 CorelDRAW，自动生成符合印刷/生产规范的矢量设计文件
3. 支持批量并行生成多规格变体
4. 输出可直接送生产的文件（印刷 PDF、激光 DXF、雕刻文件等）

### 1.3 目标场景

| 场景 | 说明 |
|---|---|
| 批量门牌/房号牌 | 从 Excel 读取房间信息，套模板批量生成 |
| 导向标识系列 | 同一设计语言，多尺寸多指向变体 |
| 品牌物料变体 | Logo + 品牌色 + 文案组合，多规格输出 |
| 展板/展架 | 结构固定、内容替换型设计 |
| 工厂铭牌/设备标签 | 序列号、规格参数批量嵌入，配合条码/QR |

---

## 二、系统架构

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                      输入层                              │
│  Excel规格表 / 需求文字 / 品牌手册 / JSON参数 / 图片资产  │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  AI Agent 层（Claude）                   │
│  • 需求解析与任务规划                                     │
│  • 多步推理 & 工具调用编排                                │
│  • 异常处理与设计规范校验                                 │
│  • 视觉反馈确认（PNG预览 → 图像识别）                     │
└─────────────────────┬───────────────────────────────────┘
                      │  MCP 协议（stdio JSON-RPC）
                      ▼
┌─────────────────────────────────────────────────────────┐
│               MCP Server 层（Python）                    │
│  • 工具注册与参数校验                                     │
│  • COM 调用封装与错误处理                                 │
│  • 进程状态监控与重试                                     │
│  • 文件系统与项目管理                                     │
└─────────────────────┬───────────────────────────────────┘
                      │  win32com / COM 自动化
                      ▼
┌─────────────────────────────────────────────────────────┐
│            CorelDRAW COM API 层（Windows）               │
│  文档 · 图形 · 文字 · 颜色 · 图层 · 导出 · 印前          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                     生产输出层                            │
│  印刷PDF · 激光切割DXF · 雕刻文件 · 数字打印RIP · 客户确认稿 │
└─────────────────────────────────────────────────────────┘
```

### 2.2 关键设计决策

**为什么选 CorelDRAW COM 而非 Inkscape？**
- CorelDRAW 是平面/印刷/标识行业的主流工具，CDR 格式是主要交换格式
- COM API 功能完整，专色/Pantone 支持成熟，印前工具链健全
- 已有激光切割、VDP 等工业落地案例

**为什么加视觉反馈环？**
- COM API 只能操作对象，无法感知最终渲染效果
- 部分排版问题（文字溢出、视觉比例失调）需要"看"才能发现
- Agent 可调用 `export_preview_png` → 将 PNG 送回 Claude 做视觉检查 → 决定是否需要调整

---

## 三、MCP Server 设计

### 3.1 工具清单

#### 文档管理类
```
open_template(path)                    # 打开 CDR 模板文件
create_document(width, height, unit)   # 新建指定尺寸文档
save_document(path, format)            # 保存/另存为（CDR/PDF/DXF等）
close_document()                       # 关闭当前文档
add_page()                             # 添加新页面
set_page_size(width, height)           # 修改页面尺寸
get_document_info()                    # 获取当前文档状态（供Agent决策）
```

#### 图形操作类
```
create_rectangle(x, y, w, h, corner_radius)   # 创建矩形
create_ellipse(cx, cy, rx, ry)                # 创建椭圆
create_line(x1, y1, x2, y2)                  # 创建直线
import_svg(path, x, y)                       # 导入 SVG（Logo、图标）
import_image(path, x, y, w, h)              # 导入位图
set_shape_size(shape_id, w, h)              # 精确设置尺寸
set_shape_position(shape_id, x, y)          # 精确定位
boolean_operation(ids, op)                  # 布尔运算（合并/裁减/相交）
convert_to_curves(shape_id)                 # 转曲（印前必须）
optimize_nodes(shape_id, threshold)         # 节点精简（激光优化）
group_shapes(ids)                           # 组合对象
find_shape_by_name(name)                    # 按名称查找对象（模板中的占位符）
```

#### 文字处理类
```
set_text_content(shape_id, text)            # 替换文字内容
set_text_style(shape_id, font, size, ...)   # 设置字体/字号/字距/行距
fit_text_to_frame(shape_id)                 # 文字适配框
check_text_overflow(shape_id)               # 检查是否溢出 → 返回布尔
convert_text_to_curves(shape_id)            # 文字转曲线
create_text_frame(x, y, w, h, text)        # 创建文本框
```

#### 颜色与填充类
```
set_fill_cmyk(shape_id, c, m, y, k)        # CMYK 填充
set_fill_pantone(shape_id, pantone_code)    # 专色（Pantone）填充
set_fill_rgb(shape_id, r, g, b)            # RGB 填充
set_outline(shape_id, width, color_mode, ...) # 描边
set_no_fill(shape_id)                      # 无填充（镂空）
set_no_outline(shape_id)                   # 无描边
check_rgb_colors()                          # 检测文档中的 RGB 色（印前检查）
```

#### 图层管理类
```
create_layer(name, color)                   # 新建图层（color用于激光机识别）
get_layers()                                # 获取所有图层列表
assign_to_layer(shape_id, layer_name)       # 对象移入指定图层
set_layer_visible(layer_name, visible)      # 图层显隐
lock_layer(layer_name)                      # 锁定图层
```

#### 导出类
```
export_pdf(path, color_profile, bleed, crop_marks)  # 印刷级 PDF
export_dxf(path, version, layer_filter)             # 激光/雕刻 DXF
export_ai(path)                                     # Adobe Illustrator 格式
export_svg(path)                                    # SVG 矢量
export_png(path, dpi, color_mode)                   # 确认稿/预览
export_preview_png(path, width)                     # 小图预览（供 Agent 视觉检查）
batch_export(pages, format, output_dir)             # 批量多页导出
```

#### 质检类
```
check_dimensions(expected_w, expected_h, tolerance) # 尺寸校验
check_text_overflow_all()                           # 全文档文字溢出检查
check_rgb_colors()                                  # RGB 色检查
check_missing_fonts()                               # 缺失字体检查
check_node_count(shape_id)                          # 节点数检查（路径复杂度）
get_color_report()                                  # 全文档色彩报告
```

#### 数据合并类
```
read_excel_data(path, sheet)                # 读取 Excel/CSV 数据源
merge_record(template_path, data_row, output_path)  # 单条记录合并
batch_merge(template_path, data_path, output_dir)   # 批量数据合并
generate_barcode(type, data, x, y, w, h)   # 生成条码（Code128/EAN等）
generate_qrcode(data, x, y, size)          # 生成 QR Code
```

### 3.2 MCP Server 核心代码结构

```python
# server.py 骨架
import win32com.client
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.types as types

class CorelDrawMCPServer:
    def __init__(self):
        self.corel = None
        self.app = None
        
    def connect(self):
        """连接或启动 CorelDRAW"""
        try:
            self.app = win32com.client.GetActiveObject("CorelDRAW.Application")
        except:
            self.app = win32com.client.Dispatch("CorelDRAW.Application")
        self.app.Visible = True
        
    def safe_call(self, func, *args, **kwargs):
        """统一错误处理和重试"""
        max_retries = 3
        for i in range(max_retries):
            try:
                return {"success": True, "result": func(*args, **kwargs)}
            except Exception as e:
                if i == max_retries - 1:
                    return {"success": False, "error": str(e)}
                self._reconnect_if_needed()
```

---

## 四、核心工作流设计

### 4.1 批量模板填充工作流

```
输入: Excel文件(房间号, 部门名, 楼层) + 门牌模板.CDR

Agent 执行步骤:
1. read_excel_data("项目数据.xlsx")
   → 返回50条记录
2. for each 记录:
   a. open_template("门牌200x80.cdr")
   b. find_shape_by_name("placeholder_room")  
      → 返回 shape_id
   c. set_text_content(shape_id, record.room)
   d. set_text_content("placeholder_dept", record.dept)
   e. check_text_overflow("placeholder_dept")
      → if True: fit_text_to_frame() or reduce font size
   f. export_preview_png("temp_preview.png", 400)
      → 将 PNG 送回 Claude 做视觉检查
      → if 版式有问题: 调整后重新预览
   g. convert_text_to_curves("all")
   h. check_rgb_colors() → if RGB存在: 转换为CMYK
   i. export_pdf(f"print/{record.room}.pdf", 
                 color_profile="ISO_Coated_v2",
                 bleed=3, crop_marks=True)
   j. assign_to_layer("背景", "laser_red")
      assign_to_layer("文字", "laser_white")
   k. export_dxf(f"laser/{record.room}.dxf")
3. 汇报处理结果（成功数、异常数、调整项）
```

### 4.2 模板创建工作流（前置必须）

```
人工操作（一次性）:
1. 设计师在 CorelDRAW 中制作标准模板
2. 所有需要动态替换的元素用统一命名规范命名
   如: "placeholder_room", "placeholder_dept", "placeholder_logo"
3. 颜色使用规范色值（Pantone 专色或标准 CMYK）
4. 图层按生产工序命名: "laser_cut", "engrave_deep", "print_layer"
5. 保存为 CDR 模板文件

Agent 只负责:
- 打开模板
- 替换占位内容
- 调整需要动态变化的参数
- 验证并导出
```

### 4.3 视觉反馈验证环

```
export_preview_png() 
    → Claude 收到 PNG 图像
    → Claude 检查:
        ✓ 文字是否完整显示（无截断）
        ✓ 整体视觉比例是否合理
        ✓ 关键信息是否清晰可读
        ✓ 色块边界是否正确
    → if 发现问题: 调用修正工具 → 重新预览
    → if 确认OK: 执行正式导出
```

---

## 五、技术约束与对策

### 5.1 硬约束

| 约束 | 影响 | 对策 |
|---|---|---|
| 必须 Windows 环境 | 部署限制 | 专用 Windows 生产服务器或 VM |
| CorelDRAW 进程必须运行 | 无法纯无头执行 | 后台最小化运行，可 RDP 监控 |
| COM 操作串行 | 无法真正并发 | 任务队列 + 多实例（多 VM）扩展 |
| CorelDRAW 版本依赖 | 不同版本 API 有差异 | 锁定 CorelDRAW 2021+ 版本 |
| COM 偶发崩溃 | 任务中断 | 自动重连机制 + 断点续传 |

### 5.2 设计能力边界

| 能力类型 | 可行性 | 说明 |
|---|---|---|
| 模板内容替换 | ★★★★★ | 完全自动化，核心场景 |
| 参数化尺寸变体 | ★★★★☆ | 可自动按比例缩放 |
| 颜色方案替换 | ★★★★☆ | 程序化赋值，准确率高 |
| 印前规范处理 | ★★★★★ | 转曲、CMYK、出血全自动 |
| 从零创意设计 | ★★☆☆☆ | 不适合，Agent 无空间感知 |
| 复杂排版决策 | ★★★☆☆ | 需视觉反馈环辅助 |
| 自由曲线绘制 | ★★☆☆☆ | 有限，规则形状可以，复杂轮廓不可以 |

---

## 六、实施路线图

### Phase 1 — MVP（4周）
- [ ] MCP Server 基础框架搭建
- [ ] 核心工具实现（文档、文字替换、导出 PDF/DXF）
- [ ] 单条记录端到端验证
- [ ] 视觉预览反馈基础版

### Phase 2 — 批量生产（3周）
- [ ] Excel 数据读取与批量合并
- [ ] 质检工具全套实现
- [ ] 错误处理与任务日志
- [ ] 条码/QR 生成集成

### Phase 3 — 稳定化（2周）
- [ ] COM 崩溃重连机制
- [ ] 任务队列管理
- [ ] 多模板管理与版本控制
- [ ] 操作记录与可追溯性

### Phase 4 — 扩展（后续）
- [ ] 多 CorelDRAW 实例并发
- [ ] Web UI / 订单系统对接
- [ ] 自动报价联动（尺寸→材料→工时→报价）

---

## 七、需要特别关注的风险

1. **模板规范化是前提**：若现有模板命名混乱、图层无规范，Agent 将无法准确定位元素，需要先投入人工整理模板库。

2. **中文字体问题**：设计行业常用特殊中文字体（方正、汉仪等），生产机器上的字体安装状态必须与设计机一致，否则 Agent 无法发现静默替换。

3. **视觉质量的主观性**：Agent 通过 PNG 做视觉检查能发现明显问题，但无法替代人类对「设计美感」的判断，建议关键稿件保留人工审批环节。

4. **CorelDRAW 版本锁定**：不同版本的 COM API 有细微差异，需锁定统一版本，避免在不同机器上行为不一致。

5. **色彩管理链路**：从 Pantone 专色到数字打印的色彩转换需要配置正确的 ICC Profile，COM API 本身不管理色彩引擎，需要依赖 CorelDRAW 的色彩设置预先配置正确。

---

## 八、技术选型与依赖清单

### 8.1 运行环境要求

| 环境 | 要求 | 说明 |
|---|---|---|
| 操作系统 | Windows 10/11 64-bit | COM 自动化强依赖 Windows |
| Python | 3.11+ 64-bit | **必须与 CorelDRAW 位数一致**，否则 COM 调用失败 |
| CorelDRAW | Graphics Suite 2021+（建议 2024） | 低版本 COM API 功能不完整 |
| Ghostscript | 10.x | 部分条码格式生成依赖，可选 |

> ⚠️ Python 必须是 64-bit 版本。使用旧版环境时 32-bit Python 的旧习惯会导致 COM 调用失败，是踩坑重灾区。

---

### 8.2 开发语言与各层选型

#### MCP Server 层 — Python

MCP Server 必须用 Python，原因：
- `pywin32` 是 Windows COM 自动化的事实标准，Python 生态最成熟
- Anthropic 官方 MCP SDK 对 Python 支持最完整
- 条码/QR/图像处理相关库 Python 生态最丰富

#### Agent 层 — 两种模式可选

**模式 A：Claude Desktop 直连（开发/原型阶段推荐）**

无需写 Agent 代码，直接在 `claude_desktop_config.json` 中注册 MCP Server：

```json
{
  "mcpServers": {
    "coreldraw": {
      "command": "python",
      "args": ["C:/projects/coreldraw-mcp/server.py"]
    }
  }
}
```

优点：零开发成本，Claude 直接驱动工具，适合快速验证

**模式 B：Python Agent 自定义循环（生产阶段推荐）**

使用 `anthropic` SDK 构建标准 Agent 循环，适合无人值守批量生产：

```python
import anthropic

client = anthropic.Anthropic()

def run_agent(task_description, tools):
    messages = [{"role": "user", "content": task_description}]
    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            tools=tools,
            messages=messages
        )
        if response.stop_reason == "end_turn":
            break
        # 执行工具调用，结果追加回 messages
        ...
```

**模式 C：对接 AIAgentDSL / LangChain4j（Java 生态集成）**

若需要将此能力集成到现有 Java Agent 框架，LangChain4j 支持通过 stdio 连接 MCP Server：

```java
McpTransport transport = new StdioMcpTransport.Builder()
    .command(List.of("python", "server.py"))
    .logEvents(true)
    .build();

McpToolProvider toolProvider = McpToolProvider.builder()
    .mcpClients(List.of(McpClient.sync(transport).build()))
    .build();
```

此模式允许 CorelDRAW 工具作为 AIAgentDSL 的一类技能插件接入，与其他业务 Agent 协同。

---

### 8.3 Python 第三方依赖清单

#### 核心依赖

| 包名 | 推荐版本 | 用途 |
|---|---|---|
| `fastmcp` | ≥ 2.0 | MCP Server 框架，比官方 `mcp` SDK 更简洁 |
| `pywin32` | ≥ 306 | CorelDRAW COM 接口（`win32com.client`） |
| `pydantic` | ≥ 2.0 | 工具参数校验与数据模型定义 |
| `anthropic` | ≥ 0.40 | Claude API SDK（生产 Agent 模式使用） |

#### 数据处理

| 包名 | 推荐版本 | 用途 |
|---|---|---|
| `pandas` | ≥ 2.0 | Excel/CSV 数据读取与处理 |
| `openpyxl` | ≥ 3.1 | pandas 读取 .xlsx 的底层依赖 |
| `xlrd` | ≥ 2.0 | 读取老版 .xls 格式（部分客户仍在用） |

#### 条码与图像

| 包名 | 推荐版本 | 用途 |
|---|---|---|
| `qrcode` | ≥ 7.4 | QR Code 生成，支持输出 SVG（可直接导入 CorelDRAW） |
| `python-barcode` | ≥ 0.15 | Code128、EAN-13、Code39 等标准条码 |
| `Pillow` | ≥ 10.0 | 图像处理，预览 PNG 的缩放与格式转换 |

#### 工程支撑

| 包名 | 推荐版本 | 用途 |
|---|---|---|
| `loguru` | ≥ 0.7 | 结构化日志，比标准 logging 更易用 |
| `psutil` | ≥ 5.9 | 监控 CorelDRAW 进程状态（是否存活、内存使用） |
| `python-dotenv` | ≥ 1.0 | 环境变量配置（API Key、路径配置等） |
| `tenacity` | ≥ 8.0 | 重试逻辑封装（COM 调用失败自动重试） |

#### requirements.txt 完整版

```
# MCP & AI
fastmcp>=2.0.0
anthropic>=0.40.0

# Windows COM
pywin32>=306

# Data validation
pydantic>=2.0.0
pydantic-settings>=2.0.0

# Data processing
pandas>=2.0.0
openpyxl>=3.1.0
xlrd>=2.0.0

# Barcode & QR
qrcode[pil]>=7.4.0
python-barcode>=0.15.0

# Image processing
Pillow>=10.0.0

# Engineering
loguru>=0.7.0
psutil>=5.9.0
python-dotenv>=1.0.0
tenacity>=8.0.0
```

---

### 8.4 开发工具推荐

| 工具 | 用途 |
|---|---|
| `uv` | Python 包管理器，比 pip 快 10x，推荐替代 pip+venv |
| `makepy`（pywin32 自带） | 从 CorelDRAW 类型库生成 Python 类型存根，提供 IDE 智能提示 |
| `ruff` | 代码格式化与 lint（速度极快） |
| MCP Inspector | Anthropic 官方 MCP 调试工具，可在不启动 Claude 的情况下测试每个工具 |

#### makepy 生成 CorelDRAW 类型库（强烈推荐）

```bash
# 在开发机上执行一次，生成早绑定（Early Binding）的类型存根
python -m win32com.client.makepy "CorelDRAW Application Type Library"
```

执行后，IDE 可以自动提示 `app.ActiveDocument.Pages` 等所有属性和方法，极大提升开发效率。

---

### 8.5 项目目录结构

```
coreldraw-mcp/
├── server.py                  # MCP Server 入口，工具注册
├── tools/                     # 工具实现（每类一个文件）
│   ├── document.py            # 文档管理
│   ├── shapes.py              # 图形操作
│   ├── text.py                # 文字处理
│   ├── colors.py              # 颜色与填充
│   ├── layers.py              # 图层管理
│   ├── export.py              # 导出（PDF/DXF/PNG）
│   ├── preflight.py           # 印前质检
│   └── data_merge.py          # 数据合并与条码
├── core/
│   ├── connection.py          # CorelDRAW COM 连接管理与重连
│   ├── retry.py               # tenacity 重试策略封装
│   └── models.py              # Pydantic 数据模型（工具参数定义）
├── config/
│   ├── settings.py            # 系统配置（路径、超时、CorelDRAW 版本）
│   ├── color_profiles/        # ICC 色彩配置文件
│   └── template_registry.json # 模板库元数据（模板名→文件路径→占位符清单）
├── agent/                     # 生产 Agent 模式（可选）
│   ├── runner.py              # Agent 主循环
│   └── prompts.py             # 系统提示词
├── logs/                      # 运行日志（loguru 输出）
├── output/                    # 生产输出暂存目录
├── requirements.txt
├── pyproject.toml             # uv 项目配置
└── README.md
```

---

### 8.6 fastmcp 工具注册示例

```python
# server.py
from fastmcp import FastMCP
from tools.document import open_template, save_document, get_document_info
from tools.text import set_text_content, check_text_overflow, convert_text_to_curves
from tools.export import export_pdf, export_dxf, export_preview_png
from tools.preflight import check_missing_fonts, check_rgb_colors
from core.connection import CorelDrawConnection

mcp = FastMCP("coreldraw-mcp")
conn = CorelDrawConnection()

@mcp.tool()
def open_template(path: str) -> dict:
    """打开 CDR 模板文件。path 为模板绝对路径或模板库中的模板名称。"""
    return conn.safe_call(lambda: _open_template_impl(path))

@mcp.tool()
def set_text_content(shape_name: str, text: str) -> dict:
    """按对象名称找到文字框并替换内容。shape_name 为模板中定义的占位符名称。"""
    return conn.safe_call(lambda: _set_text_impl(shape_name, text))

@mcp.tool()
def export_preview_png(output_path: str, width_px: int = 800) -> dict:
    """
    导出当前文档为低分辨率 PNG 预览图，供 AI Agent 进行视觉检查。
    返回图片的 base64 编码，Agent 可直接读取。
    """
    return conn.safe_call(lambda: _export_preview_impl(output_path, width_px))

if __name__ == "__main__":
    mcp.run()
```

---

### 8.7 template_registry.json — 模板元数据示例

模板库的核心配置文件，Agent 通过它了解可用模板及其占位符定义：

```json
{
  "templates": {
    "门牌_200x80_红底": {
      "file": "templates/门牌_200x80_红底白字.cdr",
      "description": "标准门牌，200×80mm，Pantone 485 红底白字",
      "placeholders": {
        "placeholder_room":  { "type": "text", "max_chars": 6,  "desc": "房间号" },
        "placeholder_dept":  { "type": "text", "max_chars": 12, "desc": "部门名称" },
        "placeholder_floor": { "type": "text", "max_chars": 4,  "desc": "楼层" }
      },
      "layers": {
        "print_layer":  "印刷内容层",
        "laser_red":    "激光雕刻-底色层（红色）",
        "laser_white":  "激光雕刻-文字层（白色）"
      },
      "export_profiles": {
        "print_pdf": { "color_profile": "ISO_Coated_v2", "bleed_mm": 3 },
        "laser_dxf": { "version": "R14", "layers": ["laser_red", "laser_white"] }
      }
    }
  }
}
```

Agent 调用 `list_templates()` 工具时返回此配置，从而知道有哪些模板可用、每个模板支持哪些占位符。
