"""视觉能力工具 — 将当前画布导出为图片直接返回给 Agent 查看

与 export.py 的区别：export_pdf/export_png/export_preview_png 等工具把结果写入磁盘
文件路径，Agent 需要额外的文件读取/图片查看能力才能"看到"内容。本模块的 view_canvas
直接把图片作为 MCP 图片内容返回，支持视觉的 Agent（如 Claude）可以在工具调用结果里
直接"看到"画布当前排版效果 —— 检查形状位置、文字是否正确、颜色是否符合预期。

注意：这是本项目中唯一不遵循"所有工具返回 ToolResult"约定的工具。MCP 图片内容必须
通过 fastmcp.utilities.types.Image 类型返回才能被自动转换为图片内容块（而不是被
序列化成一段 JSON 文本），因此本工具成功时返回 Image，失败时返回一段说明文字。
"""

import os
import tempfile

from core.connection import get_connection
from fastmcp.utilities.types import Image

_CDR_PNG = 802
_CDR_CURRENT_PAGE = 1
_CDR_RGB_COLOR_IMAGE = 4
_CDR_NORMAL_ANTIALIASING = 1
_CDR_COMPRESSION_NONE = 0
_CDR_MILLIMETER = 3


def view_canvas(width: int = 1000):
    """视觉能力：将 CorelDRAW 当前页面截图为 PNG 并直接返回图片内容（而非文件路径），
    支持视觉的 Agent 可以直接"看到"画布当前效果 —— 用于核查排版、确认文字/颜色是否
    符合预期，或在批量操作后做视觉抽查。width 为导出宽度（像素），默认 1000。
    注：本工具失败时返回一段说明文字而非 ToolResult（见模块顶部说明）。"""
    conn = get_connection()
    if not conn.status.connected:
        return "CorelDRAW 未连接"

    def _capture():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        doc.Unit = _CDR_MILLIMETER
        page = doc.ActivePage
        page_w_mm = page.SizeWidth
        page_h_mm = page.SizeHeight
        if page_w_mm <= 0 or page_h_mm <= 0:
            raise RuntimeError("无法读取页面尺寸")

        export_dpi = max(72, min(int(width / (page_w_mm / 25.4)), 300))
        pixel_w = max(1, int(page_w_mm / 25.4 * export_dpi))
        pixel_h = max(1, int(page_h_mm / 25.4 * export_dpi))

        try:
            doc.ClearSelection()
        except Exception:
            pass
        try:
            export_area = conn.app.CreateRect(0, 0, page_w_mm, page_h_mm)
        except Exception:
            export_area = None

        tmp_path = os.path.join(tempfile.gettempdir(), f"coreldraw_view_{os.getpid()}_{id(doc)}.png")
        exported = False
        try:
            expflt = doc.ExportBitmap(
                tmp_path,
                _CDR_PNG,
                _CDR_CURRENT_PAGE,
                _CDR_RGB_COLOR_IMAGE,
                pixel_w,
                pixel_h,
                export_dpi,
                export_dpi,
                _CDR_NORMAL_ANTIALIASING,
                False,
                False,
                True,
                False,
                _CDR_COMPRESSION_NONE,
                None,
                export_area,
            )
            if expflt is not None:
                expflt.Finish()
            exported = True
        except Exception:
            pass

        if not exported:
            doc.Export(tmp_path, _CDR_PNG, _CDR_CURRENT_PAGE, None, None)

        if not os.path.isfile(tmp_path) or os.path.getsize(tmp_path) == 0:
            raise RuntimeError("截图导出失败，文件为空")

        with open(tmp_path, "rb") as f:
            data = f.read()
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return data

    result = conn.safe_call(_capture)
    if not result["success"]:
        return f"截图失败: {result.get('error', '未知错误')}"
    return Image(data=result["result"], format="png")
