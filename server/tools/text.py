"""文字处理工具 — 替换文字内容、样式设置、溢出检查、创建文本框"""

from typing import Optional

from core.connection import get_connection
from core.models import ToolResult

_CDR_TEXT_SHAPE = 3
_CDR_PARAGRAPH_TEXT = 1
_CDR_MILLIMETER = 3
_ALIGNMENT_MAP = {"left": 0, "center": 3, "right": 1, "none": 0}


def _find_text_shape(shape_id: str):
    """查找文字形状，确保是文字类型"""
    conn = get_connection()
    doc = conn.app.ActiveDocument
    if doc is None:
        return None
    target = str(shape_id)
    try:
        shapes = doc.ActivePage.Shapes
        try:
            shape = shapes(shape_id)
        except Exception:
            for s in shapes:
                try:
                    if str(s.StaticID) == target or s.Name == target:
                        shape = s
                        break
                except Exception:
                    continue
            else:
                return None
        try:
            if shape.Type == _CDR_TEXT_SHAPE:
                return shape
        except Exception:
            pass
        try:
            _ = shape.Text
        except Exception:
            return None
        return shape
    except Exception:
        return None


def _get_text_content(text) -> str:
    for getter in (
        lambda: text.Contents,
        lambda: text.GetContents(),
        lambda: text.Story.Text,
        lambda: text.Story,
    ):
        try:
            value = getter()
            if isinstance(value, str):
                return value
        except Exception:
            continue
    return ""


def _set_text_content(text, content: str) -> None:
    for setter in (
        lambda: setattr(text, "Contents", content),
        lambda: text.SetContents(2, content),
        lambda: setattr(text, "Story", content),
    ):
        try:
            setter()
            return
        except Exception:
            continue
    raise RuntimeError("当前 CorelDRAW 版本不支持已知的文字内容写入 API")


def _set_text_font(text, font: str) -> None:
    for setter in (
        lambda: setattr(text.Story, "Font", font),
        lambda: setattr(text.FontProperties, "Name", font),
    ):
        try:
            setter()
            return
        except Exception:
            continue


def _set_text_size(text, size: float) -> None:
    for setter in (
        lambda: setattr(text.Story, "Size", size),
        lambda: setattr(text.FontProperties, "Size", size),
    ):
        try:
            setter()
            return
        except Exception:
            continue


def _set_text_bold(text, bold: bool) -> None:
    for setter in (
        lambda: setattr(text.Story, "Bold", bold),
        lambda: setattr(text.FontProperties, "Bold", bold),
    ):
        try:
            setter()
            return
        except Exception:
            continue


def _set_text_underline(text, underline: bool) -> None:
    for setter in (
        lambda: setattr(text.Story, "Underline", 1 if underline else 0),
        lambda: setattr(text.FontProperties, "Underline", underline),
    ):
        try:
            setter()
            return
        except Exception:
            continue


def _set_text_spacing(text, attr: str, value: float) -> bool:
    """设置行距/字间距（百分比）。不同 CorelDRAW 版本路径不同，逐一尝试。"""
    for setter in (
        lambda: setattr(text.Story.Paragraph.Spacing, attr, value),
        lambda: setattr(text.Paragraph.Spacing, attr, value),
        lambda: setattr(text.Story, attr, value),
    ):
        try:
            setter()
            return True
        except Exception:
            continue
    return False


def _apply_default_text_style(shape, frame_height: float) -> None:
    text = shape.Text
    size = max(8.0, min(18.0, frame_height * 0.55))
    _set_text_size(text, size)
    try:
        shape.Fill.UniformColor.CMYKAssign(0, 0, 0, 100)
    except Exception:
        pass


def set_text_content(shape_id: str, content: str) -> ToolResult:
    """替换文字形状的文本内容。shape_id 为形状名称或 ID。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _set():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到文字形状: {shape_id}")
        old_content = _get_text_content(shape.Text)
        _set_text_content(shape.Text, content)
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
    bold: Optional[bool] = None,
    italic: Optional[bool] = None,
    underline: Optional[bool] = None,
    alignment: str = "",
    line_spacing: Optional[float] = None,
    char_spacing: Optional[float] = None,
) -> ToolResult:
    """设置文字形状的样式：字体、字号、粗体、斜体、下划线、对齐、行距、字间距。
    bold/italic/underline 留空(None)则不改动该项，显式传 True 或 False 可开启或关闭
    （区别于旧版本，现在可以显式取消粗体/斜体，而不仅仅是开启）。
    line_spacing/char_spacing 对应 CorelDRAW 的 CharSpacing/LineSpacing 属性，
    0 表示正常间距（无额外加宽），正数表示在正常间距基础上增加的百分比（不是"正常值的倍数"）；
    需要收紧字符间距时传负数（如 -30）。留空(None)则不改动该项——显式传 0 会把间距重置为正常。"""
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
            _set_text_font(text, font)
            changes["font"] = font
        if size > 0:
            _set_text_size(text, size)
            changes["size"] = size
        if bold is not None:
            _set_text_bold(text, bold)
            changes["bold"] = bold
        if italic is not None:
            try:
                text.FontProperties.Italic = italic
                changes["italic"] = italic
            except Exception:
                pass
        if underline is not None:
            _set_text_underline(text, underline)
            changes["underline"] = underline
        if alignment and alignment in _ALIGNMENT_MAP:
            try:
                text.Alignment = _ALIGNMENT_MAP[alignment]
                changes["alignment"] = alignment
            except Exception:
                pass
        if line_spacing is not None and _set_text_spacing(text, "LineSpacing", line_spacing):
            changes["line_spacing"] = line_spacing
        if char_spacing is not None and _set_text_spacing(text, "CharSpacing", char_spacing):
            changes["char_spacing"] = char_spacing
        if not changes:
            raise ValueError("未指定任何样式变更，或指定的样式在当前 CorelDRAW 版本不受支持")
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
        content_length = len(_get_text_content(shape.Text))
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


def get_text_content(shape_id: str) -> ToolResult:
    """读取文字形状的完整内容（不截断，区别于 list_all_text_shapes 的预览截断）。
    返回 content、text_type（artistic/paragraph）、length。shape_id 为名称或 StaticID。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _get():
        shape = _find_text_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到文字形状: {shape_id}")
        text = shape.Text
        content = _get_text_content(text)
        try:
            text_type = "paragraph" if text.Type == _CDR_PARAGRAPH_TEXT else "artistic"
        except Exception:
            text_type = "unknown"
        return {"shape_id": shape_id, "content": content, "text_type": text_type, "length": len(content)}

    result = conn.safe_call(_get)
    if result["success"]:
        r = result["result"]
        preview = r["content"][:50] + "…" if len(r["content"]) > 50 else r["content"]
        return ToolResult.ok(f"内容: '{preview}'", **r)
    return ToolResult.fail(result.get("error", "读取文字内容失败"))


def create_artistic_text(x: float, y: float, text: str, font: str = "", size: float = 12) -> ToolResult:
    """创建美术字（单行文字，非段落文本框）。形状的宽高即实际字形包围盒，
    适合需要精确测量/缩放的场景（如按目标高度缩放文字）。返回形状 ID 与实际尺寸。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _create():
        doc = conn.app.ActiveDocument
        doc.Unit = _CDR_MILLIMETER
        layer = doc.ActivePage.ActiveLayer
        shape = None
        for attempt in (
            lambda: layer.CreateArtisticText(x, y, text, 0, 0, 0, font, size, False, False, False),
            lambda: layer.CreateArtisticText(x, y, text),
        ):
            try:
                shape = attempt()
                break
            except Exception:
                continue
        if shape is None:
            raise RuntimeError("创建美术字失败，当前 CorelDRAW 版本不支持已知的 CreateArtisticText 签名")
        if font and not shape.Text.Story.Font == font:
            try:
                shape.Text.Story.Font = font
            except Exception:
                pass
        try:
            shape.Text.Story.Size = size
        except Exception:
            pass
        shape.Name = f"text_{shape.StaticID}"
        return {
            "shape_id": str(shape.StaticID),
            "name": shape.Name,
            "width": round(shape.SizeWidth, 2),
            "height": round(shape.SizeHeight, 2),
            "x": round(shape.PositionX, 2),
            "y": round(shape.PositionY, 2),
            "content": text,
        }

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"美术字创建成功: '{text}'", **result["result"])
    return ToolResult.fail(result.get("error", "创建美术字失败"))


def create_text_frame(x: float, y: float, width: float, height: float, text: str) -> ToolResult:
    """创建段落文本框。返回形状 ID。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _create():
        doc = conn.app.ActiveDocument
        doc.Unit = _CDR_MILLIMETER
        layer = doc.ActivePage.ActiveLayer
        left, top = x, y
        right, bottom = x + width, y + height
        shape = layer.CreateParagraphText(left, top, right, bottom, text)
        _apply_default_text_style(shape, height)
        shape.Name = f"text_{shape.StaticID}"
        return {
            "shape_id": str(shape.StaticID),
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
