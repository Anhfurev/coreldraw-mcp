"""颜色与填充工具 — CMYK/RGB/Pantone 填充、描边、颜色检查"""

from core.connection import get_connection
from core.models import ToolResult

_CDR_TEXT_SHAPE = 6
_FILL_MAP = {"cmyk": 0, "rgb": 1, "pantone": 2}


def _find_shape(shape_id: str):
    """按名称或 StaticID 查找形状"""
    conn = get_connection()
    doc = conn.app.ActiveDocument
    if not doc:
        return None
    try:
        shapes = doc.ActivePage.Shapes
        try:
            return shapes(shape_id)
        except Exception:
            for s in shapes:
                try:
                    if s.Name == shape_id:
                        return s
                except Exception:
                    continue
        return None
    except Exception:
        return None


def set_fill_cmyk(c: float, m: float, y: float, k: float, shape_id: str = "") -> ToolResult:
    """设置形状的 CMYK 填充色。shape_id 为空时作用于选中形状。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _fill():
        if shape_id:
            shape = _find_shape(shape_id)
            if shape is None:
                raise ValueError(f"未找到形状: {shape_id}")
            shape.Fill.UniformColor.CMYKAssign(c, m, y, k)
        else:
            sel = conn.app.ActiveDocument.Selection
            if not sel or sel.Shapes.Count == 0:
                raise RuntimeError("没有选中的形状，请指定 shape_id 或先选中形状")
            for s in sel.Shapes:
                try:
                    s.Fill.UniformColor.CMYKAssign(c, m, y, k)
                except Exception:
                    pass
        return {"shape_id": shape_id or "selection", "cmyk": [c, m, y, k]}

    result = conn.safe_call(_fill)
    if result["success"]:
        return ToolResult.ok(f"CMYK 填充: C{c} M{m} Y{y} K{k}", **result["result"])
    return ToolResult.fail(result.get("error", "设置 CMYK 填充失败"))


def set_fill_rgb(r: int, g: int, b: int, shape_id: str = "") -> ToolResult:
    """设置形状的 RGB 填充色。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _fill():
        if shape_id:
            shape = _find_shape(shape_id)
            if shape is None:
                raise ValueError(f"未找到形状: {shape_id}")
            shape.Fill.UniformColor.RGBAssign(r, g, b)
        else:
            sel = conn.app.ActiveDocument.Selection
            if not sel or sel.Shapes.Count == 0:
                raise RuntimeError("没有选中的形状")
            for s in sel.Shapes:
                try:
                    s.Fill.UniformColor.RGBAssign(r, g, b)
                except Exception:
                    pass
        return {"shape_id": shape_id or "selection", "rgb": [r, g, b]}

    result = conn.safe_call(_fill)
    if result["success"]:
        return ToolResult.ok(f"RGB 填充: ({r}, {g}, {b})", **result["result"])
    return ToolResult.fail(result.get("error", "设置 RGB 填充失败"))


def set_fill_pantone(shape_id: str, pantone_code: str) -> ToolResult:
    """设置形状的 Pantone 专色填充。pantone_code 如 '485 C'。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _fill():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        # Pantone 填充需要通过 Color 对象的 FindPantone 或类似方法
        # 尝试用 NamedColor 或通过 Application 的 Pantone 查找
        try:
            pantone_color = conn.app.CreateRGBColor(0, 0, 0)
            pantone_color.FindPantone(pantone_code)
            shape.Fill.ApplyUniformFill(pantone_color)
        except Exception:
            try:
                color = conn.app.CreateCMYKColor(0, 0, 0, 0)
                color.FindPantone(pantone_code)
                shape.Fill.ApplyUniformFill(color)
            except Exception:
                raise RuntimeError(f"无法应用 Pantone 色: {pantone_code}")
        return {"shape_id": shape_id, "pantone": pantone_code}

    result = conn.safe_call(_fill)
    if result["success"]:
        return ToolResult.ok(f"Pantone 填充: {pantone_code}", **result["result"])
    return ToolResult.fail(result.get("error", "设置 Pantone 填充失败"))


def set_outline(shape_id: str, width: float, color: str = "", color_mode: str = "CMYK") -> ToolResult:
    """设置形状的描边宽度和颜色。color 格式: CMYK 如 '0,100,100,0'，RGB 如 '255,0,0'。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _outline():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        shape.Outline.Width = width
        if color:
            parts = [float(x.strip()) for x in color.split(",")]
            if color_mode.upper() == "CMYK" or len(parts) == 4:
                c, m, y, k = parts
                shape.Outline.Color.CMYKAssign(c, m, y, k)
            elif color_mode.upper() == "RGB" or len(parts) == 3:
                r, g, b = [int(x) for x in parts]
                shape.Outline.Color.RGBAssign(r, g, b)
        return {"shape_id": shape_id, "width": width, "color": color, "color_mode": color_mode}

    result = conn.safe_call(_outline)
    if result["success"]:
        return ToolResult.ok(f"描边: {width}mm, color={color or '保持原色'}", **result["result"])
    return ToolResult.fail(result.get("error", "设置描边失败"))


def set_no_fill(shape_id: str = "") -> ToolResult:
    """移除形状的填充（设为镂空）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _no_fill():
        if shape_id:
            shape = _find_shape(shape_id)
            if shape is None:
                raise ValueError(f"未找到形状: {shape_id}")
            shape.Fill.ApplyNoFill()
        else:
            sel = conn.app.ActiveDocument.Selection
            if not sel or sel.Shapes.Count == 0:
                raise RuntimeError("没有选中的形状")
            for s in sel.Shapes:
                try:
                    s.Fill.ApplyNoFill()
                except Exception:
                    pass
        return {"shape_id": shape_id or "selection"}

    result = conn.safe_call(_no_fill)
    if result["success"]:
        return ToolResult.ok("已移除填充", **result["result"])
    return ToolResult.fail(result.get("error", "移除填充失败"))


def set_no_outline(shape_id: str = "") -> ToolResult:
    """移除形状的描边。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _no_outline():
        if shape_id:
            shape = _find_shape(shape_id)
            if shape is None:
                raise ValueError(f"未找到形状: {shape_id}")
            shape.Outline.SetNoOutline()
        else:
            sel = conn.app.ActiveDocument.Selection
            if not sel or sel.Shapes.Count == 0:
                raise RuntimeError("没有选中的形状")
            for s in sel.Shapes:
                try:
                    s.Outline.SetNoOutline()
                except Exception:
                    pass
        return {"shape_id": shape_id or "selection"}

    result = conn.safe_call(_no_outline)
    if result["success"]:
        return ToolResult.ok("已移除描边", **result["result"])
    return ToolResult.fail(result.get("error", "移除描边失败"))


def check_rgb_colors() -> ToolResult:
    """检测文档中的 RGB 颜色（印前检查用，印刷需转 CMYK）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _check():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        page = doc.ActivePage
        rgb_items = []
        try:
            for s in page.Shapes:
                try:
                    fill_type = s.Fill.Type
                    if fill_type == 1:  # cdrUniformFill
                        try:
                            color = s.Fill.UniformColor
                            if color.Type == 1:  # RGB
                                rgb_items.append({
                                    "name": s.Name,
                                    "type": "fill",
                                    "color": f"R{color.RGBAssign}",
                                })
                        except Exception:
                            pass
                    if s.Outline.Type == 1:
                        try:
                            color = s.Outline.Color
                            if color.Type == 1:
                                rgb_items.append({
                                    "name": s.Name,
                                    "type": "outline",
                                    "color": f"R{color.RGBRed} G{color.RGBGreen} B{color.RGBBlue}",
                                })
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            pass
        return {"found": len(rgb_items), "items": rgb_items, "passed": len(rgb_items) == 0}

    result = conn.safe_call(_check)
    if result["success"]:
        r = result["result"]
        if r["passed"]:
            return ToolResult.ok("未发现 RGB 颜色，可安全印刷", **r)
        return ToolResult.ok(f"发现 {r['found']} 处 RGB 颜色，建议转为 CMYK", **r)
    return ToolResult.fail(result.get("error", "RGB 检查失败"))
