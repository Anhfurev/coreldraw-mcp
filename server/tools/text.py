"""文字处理工具 — 替换文字内容、样式设置、溢出检查、创建文本框"""

from core.connection import get_connection
from core.models import ToolResult

_CDR_PARAGRAPH_TEXT = 4
_ALIGNMENT_MAP = {"left": 0, "center": 3, "right": 1, "none": 0}


def _find_text_shape(shape_id: str):
    """查找文字形状，确保是文字类型"""
    conn = get_connection()
    doc = conn.app.ActiveDocument
    if not doc:
        return None
    try:
        shapes = doc.ActivePage.Shapes
        try:
            shape = shapes(shape_id)
        except Exception:
            for s in shapes:
                try:
                    if s.Name == shape_id:
                        shape = s
                        break
                except Exception:
                    continue
            else:
                return None
        try:
            _ = shape.Text
        except Exception:
            return None
        return shape
    except Exception:
        return None


def set_text_content(shape_id: str, content: str) -> ToolResult:
    """替换文字形状的文本内容。shape_id 为形状名称或 ID。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _set():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到文字形状: {shape_id}")
        old_content = ""
        try:
            old_content = shape.Text.Story
        except Exception:
            pass
        shape.Text.Story = content
        text_type = "段落文字" if shape.Text.Type == _CDR_PARAGRAPH_TEXT else "美术字"
        return {"shape_id": shape_id, "old_content": old_content, "new_content": content, "text_type": text_type}

    result = conn.safe_call(_set)
    if result["success"]:
        return ToolResult.ok(f"文字已替换: '{result['result']['old_content']}' → '{content}'", **result["result"])
    return ToolResult.fail(result.get("error", "替换文字失败"))


def set_text_style(
    shape_id: str,
    font: str = "",
    size: float = 0,
    bold: bool = False,
    italic: bool = False,
    alignment: str = "",
) -> ToolResult:
    """设置文字形状的样式：字体、字号、粗体、斜体、对齐。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _style():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到文字形状: {shape_id}")
        changes = {}
        text = shape.Text
        if font:
            try:
                text.FontProperties.Name = font
                changes["font"] = font
            except Exception:
                pass
        if size > 0:
            try:
                text.FontProperties.Size = size
                changes["size"] = size
            except Exception:
                pass
        if bold:
            try:
                text.FontProperties.Bold = True
                changes["bold"] = True
            except Exception:
                pass
        if italic:
            try:
                text.FontProperties.Italic = True
                changes["italic"] = True
            except Exception:
                pass
        if alignment and alignment in _ALIGNMENT_MAP:
            try:
                text.Alignment = _ALIGNMENT_MAP[alignment]
                changes["alignment"] = alignment
            except Exception:
                pass
        if not changes:
            raise ValueError("未指定任何样式变更")
        return {"shape_id": shape_id, "changes": changes}

    result = conn.safe_call(_style)
    if result["success"]:
        changes = result["result"]["changes"]
        return ToolResult.ok(f"文字样式已更新: {changes}", **result["result"])
    return ToolResult.fail(result.get("error", "设置文字样式失败"))


def fit_text_to_frame(shape_id: str) -> ToolResult:
    """将段文字自适应到文本框大小（仅对段落文字有效）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _fit():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到文字形状: {shape_id}")
        if shape.Text.Type != _CDR_PARAGRAPH_TEXT:
            raise ValueError(f"只能对段落文字使用自适应，当前类型: {shape.Text.Type}")
        shape.Text.FitTextToFrame = True
        return {"shape_id": shape_id, "fitted": True}

    result = conn.safe_call(_fit)
    if result["success"]:
        return ToolResult.ok(f"文字已自适应到文本框", **result["result"])
    return ToolResult.fail(result.get("error", "文字自适应失败"))


def check_text_overflow(shape_id: str) -> ToolResult:
    """检查文字是否超出文本框（溢出）。返回溢出状态。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _check():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到文字形状: {shape_id}")
        text_type = shape.Text.Type
        overflowing = False
        if text_type == _CDR_PARAGRAPH_TEXT:
            try:
                overflowing = shape.Text.Overflows
            except Exception:
                try:
                    overflowing = shape.Text.IsOverflowing
                except Exception:
                    pass
        content_length = 0
        try:
            raw = shape.Text.Story
            # X6 returns a TextRange COM object; newer versions return a str
            if isinstance(raw, str):
                content_length = len(raw)
            else:
                try:
                    content_length = len(raw.Text)
                except Exception:
                    pass
        except Exception:
            pass
        return {
            "shape_id": shape_id,
            "overflowing": overflowing,
            "text_type": "paragraph" if text_type == _CDR_PARAGRAPH_TEXT else "artistic",
            "content_length": content_length,
        }

    result = conn.safe_call(_check)
    if result["success"]:
        status = "溢出" if result["result"]["overflowing"] else "正常"
        return ToolResult.ok(f"文字状态: {status}", **result["result"])
    return ToolResult.fail(result.get("error", "检查文字溢出失败"))


def convert_text_to_curves(shape_id: str) -> ToolResult:
    """将文字转换为曲线（印前必须操作，防止字体依赖）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _convert():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到文字形状: {shape_id}")
        shape.ConvertToCurves()
        return {"shape_id": shape_id, "converted": True}

    result = conn.safe_call(_convert)
    if result["success"]:
        return ToolResult.ok(f"文字已转曲: {shape_id}", **result["result"])
    return ToolResult.fail(result.get("error", "文字转曲失败"))


def create_text_frame(x: float, y: float, width: float, height: float, text: str) -> ToolResult:
    """创建段落文本框。返回形状 ID。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _create():
        layer = conn.app.ActiveDocument.ActivePage.ActiveLayer
        left, top = x, y
        right, bottom = x + width, y + height
        shape = layer.CreateParagraphText(left, top, right, bottom, text)
        shape.Name = f"text_{shape.StaticID}"
        return {
            "shape_id": shape.StaticID,
            "name": shape.Name,
            "width": width,
            "height": height,
            "x": x,
            "y": y,
            "content": text,
        }

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"文本框创建成功: {width}×{height}", **result["result"])
    return ToolResult.fail(result.get("error", "创建文本框失败"))
