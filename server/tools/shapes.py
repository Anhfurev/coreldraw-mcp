"""图形操作工具 — 创建/查找/修改形状，布尔运算，导入素材"""

from core.connection import get_connection
from core.models import ToolResult


def _find_shape(shape_id: str):
    """按名称或 StaticID 查找形状。返回 Shape 对象或 None。"""
    conn = get_connection()
    doc = conn.app.ActiveDocument
    if not doc:
        return None
    try:
        page = doc.ActivePage
        shapes = page.Shapes
        # 先尝试按名称查找
        try:
            return shapes(shape_id)
        except Exception:
            pass
        # 遍历匹配
        for s in shapes:
            try:
                if s.Name == shape_id:
                    return s
            except Exception:
                continue
        return None
    except Exception:
        return None


def _shape_info(shape) -> dict:
    """提取形状信息"""
    try:
        info = {
            "name": shape.Name if shape.Name else "",
            "type": shape.Type,
            "width": round(shape.SizeWidth, 2),
            "height": round(shape.SizeHeight, 2),
        }
        try:
            info["center_x"] = round(shape.CenterX, 2)
            info["center_y"] = round(shape.CenterY, 2)
        except Exception:
            pass
        return info
    except Exception:
        return {"name": "", "type": -1}


def create_rectangle(x: float, y: float, width: float, height: float, corner_radius: float = 0) -> ToolResult:
    """创建矩形。x,y 为左上角坐标，支持圆角（corner_radius）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _create():
        layer = conn.app.ActiveDocument.ActivePage.ActiveLayer
        r = corner_radius if corner_radius > 0 else 0
        shape = layer.CreateRectangle(x, y, x + width, y + height, r, r, r, r)
        shape.Name = f"rect_{shape.StaticID}"
        return {"shape_id": shape.StaticID, **_shape_info(shape), "corner_radius": corner_radius}

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"矩形创建成功: {width}×{height}", **result["result"])
    return ToolResult.fail(result.get("error", "创建矩形失败"))


def create_ellipse(cx: float, cy: float, rx: float, ry: float) -> ToolResult:
    """创建椭圆。cx,cy 为中心坐标，rx,ry 为 X/Y 半径。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _create():
        layer = conn.app.ActiveDocument.ActivePage.ActiveLayer
        left = cx - rx
        top = cy - ry
        right = cx + rx
        bottom = cy + ry
        shape = layer.CreateEllipse(left, top, right, bottom)
        shape.Name = f"ellipse_{shape.StaticID}"
        return {"shape_id": shape.StaticID, **_shape_info(shape), "rx": rx, "ry": ry}

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"椭圆创建成功: rx={rx}, ry={ry}", **result["result"])
    return ToolResult.fail(result.get("error", "创建椭圆失败"))


def create_line(x1: float, y1: float, x2: float, y2: float) -> ToolResult:
    """创建直线段。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _create():
        layer = conn.app.ActiveDocument.ActivePage.ActiveLayer
        shape = layer.CreateLineSegment(x1, y1, x2, y2)
        shape.Name = f"line_{shape.StaticID}"
        return {"shape_id": shape.StaticID, **_shape_info(shape), "x1": x1, "y1": y1, "x2": x2, "y2": y2}

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok("直线创建成功", **result["result"])
    return ToolResult.fail(result.get("error", "创建直线失败"))


def import_svg(path: str, x: float = 0, y: float = 0) -> ToolResult:
    """导入 SVG 文件到当前文档。返回导入的形状信息。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _import():
        import os
        if not os.path.isfile(path):
            raise FileNotFoundError(f"SVG 文件不存在: {path}")
        doc = conn.app.ActiveDocument
        doc.Import(path)
        if x != 0 or y != 0:
            try:
                shapes = doc.ActivePage.Shapes
                if shapes.Count > 0:
                    last_shape = shapes.Last
                    last_shape.SetPosition(x, y)
                    return {"path": path, "shape_id": last_shape.StaticID, **_shape_info(last_shape), "x": x, "y": y}
            except Exception:
                pass
        return {"path": path, "status": "imported"}

    result = conn.safe_call(_import)
    if result["success"]:
        return ToolResult.ok(f"SVG 已导入: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "导入 SVG 失败"))


def import_image(path: str, x: float = 0, y: float = 0, width: float = 0, height: float = 0) -> ToolResult:
    """导入位图到当前文档。可指定位置和尺寸。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _import():
        import os
        if not os.path.isfile(path):
            raise FileNotFoundError(f"图片文件不存在: {path}")
        doc = conn.app.ActiveDocument
        doc.Import(path)
        try:
            shapes = doc.ActivePage.Shapes
            if shapes.Count > 0:
                last_shape = shapes.Last
                if x != 0 or y != 0:
                    last_shape.SetPosition(x, y)
                if width > 0 and height > 0:
                    last_shape.SetSize(width, height)
                return {"path": path, "shape_id": last_shape.StaticID, **_shape_info(last_shape), "x": x, "y": y}
        except Exception:
            pass
        return {"path": path, "status": "imported"}

    result = conn.safe_call(_import)
    if result["success"]:
        return ToolResult.ok(f"图片已导入: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "导入图片失败"))


def set_shape_size(shape_id: str, width: float, height: float) -> ToolResult:
    """设置形状的精确尺寸（mm）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _set():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        shape.SetSize(width, height)
        return {"shape_id": shape_id, "width": width, "height": height}

    result = conn.safe_call(_set)
    if result["success"]:
        return ToolResult.ok(f"形状尺寸已设为: {width}×{height} mm", **result["result"])
    return ToolResult.fail(result.get("error", "设置尺寸失败"))


def set_shape_position(shape_id: str, x: float, y: float) -> ToolResult:
    """设置形状的位置（mm）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _set():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        shape.SetPosition(x, y)
        return {"shape_id": shape_id, "x": x, "y": y}

    result = conn.safe_call(_set)
    if result["success"]:
        return ToolResult.ok(f"形状移至: ({x}, {y})", **result["result"])
    return ToolResult.fail(result.get("error", "设置位置失败"))


_BOOLEAN_OPS = {"union": "Weld", "intersect": "Intersect", "subtract": "Trim", "exclude": "Simplify"}


def boolean_operation(shape_ids: str, operation: str) -> ToolResult:
    """对指定形状执行布尔运算。shape_ids 为逗号分隔的 ID 列表，operation 支持 union/intersect/subtract/exclude。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    if operation not in _BOOLEAN_OPS:
        return ToolResult.fail(f"不支持的布尔运算: {operation}，可选: {', '.join(_BOOLEAN_OPS.keys())}")

    def _operate():
        ids = [s.strip() for s in shape_ids.split(",") if s.strip()]
        if len(ids) < 2:
            raise ValueError("至少需要两个形状进行布尔运算")
        page = conn.app.ActiveDocument.ActivePage
        selected = []
        for sid in ids:
            shape = _find_shape(sid)
            if shape is None:
                raise ValueError(f"未找到形状: {sid}")
            selected.append(shape)
        selection = conn.app.CreateSelection()
        for s in selected:
            selection.Add(s)
        method = getattr(selection, _BOOLEAN_OPS[operation])
        method()
        return {"operation": operation, "input_ids": ids, "result": "success"}

    result = conn.safe_call(_operate)
    if result["success"]:
        return ToolResult.ok(f"布尔运算完成: {operation}", **result["result"])
    return ToolResult.fail(result.get("error", "布尔运算失败"))


def convert_to_curves(shape_id: str) -> ToolResult:
    """将形状转换为曲线（印前必须操作）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _convert():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        shape.ConvertToCurves()
        return {"shape_id": shape_id, "converted": True}

    result = conn.safe_call(_convert)
    if result["success"]:
        return ToolResult.ok(f"已转曲: {shape_id}", **result["result"])
    return ToolResult.fail(result.get("error", "转曲失败"))


def group_shapes(shape_ids: str) -> ToolResult:
    """将多个形状组合为一个群组。shape_ids 为逗号分隔的 ID 列表。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _group():
        ids = [s.strip() for s in shape_ids.split(",") if s.strip()]
        if len(ids) < 2:
            raise ValueError("至少需要两个形状才能组合")
        page = conn.app.ActiveDocument.ActivePage
        selected = []
        for sid in ids:
            shape = _find_shape(sid)
            if shape is None:
                raise ValueError(f"未找到形状: {sid}")
            selected.append(shape)
        selection = conn.app.CreateSelection()
        for s in selected:
            selection.Add(s)
        group = selection.Group()
        return {"group_id": group.StaticID, "member_count": len(ids), "member_ids": ids}

    result = conn.safe_call(_group)
    if result["success"]:
        return ToolResult.ok(f"已组合 {result['result']['member_count']} 个形状", **result["result"])
    return ToolResult.fail(result.get("error", "组合失败"))


def find_shape_by_name(name: str) -> ToolResult:
    """按名称查找形状。返回形状的 ID、类型、尺寸等。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _find():
        shape = _find_shape(name)
        if shape is None:
            return {"found": False, "name": name}
        return {"found": True, **_shape_info(shape), "shape_id": shape.StaticID}

    result = conn.safe_call(_find)
    if result["success"]:
        if result["result"]["found"]:
            return ToolResult.ok(f"找到形状: {name}", **result["result"])
        return ToolResult.ok(f"未找到形状: {name}", **result["result"])
    return ToolResult.fail(result.get("error", "查找形状失败"))
