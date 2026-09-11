"""图形操作工具 — 创建/查找/修改形状，布尔运算，导入素材，对齐/分布/层级/旋转/缩放"""

from core.connection import get_connection
from core.models import ToolResult


def _static_id(shape) -> str:
    """Return CorelDRAW StaticID in the string form expected by tools."""
    return str(shape.StaticID)


def _shape_matches(shape, shape_id: str) -> bool:
    target = str(shape_id)
    try:
        if str(shape.StaticID) == target:
            return True
    except Exception:
        pass
    try:
        return shape.Name == target
    except Exception:
        return False


def _create_shape_range(shapes):
    conn = get_connection()
    shape_range = conn.app.CreateShapeRange()
    for shape in shapes:
        shape_range.Add(shape)
    return shape_range


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
            if _shape_matches(s, shape_id):
                return s
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
            info["x"] = round(shape.PositionX, 2)
            info["y"] = round(shape.PositionY, 2)
        except Exception:
            pass
        try:
            info["center_x"] = round(shape.CenterX, 2)
            info["center_y"] = round(shape.CenterY, 2)
        except Exception:
            pass
        try:
            info["rotation"] = round(shape.RotationAngle, 2)
        except Exception:
            pass
        try:
            info["locked"] = shape.Locked
        except Exception:
            pass
        try:
            info["layer"] = shape.Layer.Name
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
        return {"shape_id": _static_id(shape), **_shape_info(shape), "corner_radius": corner_radius}

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
        return {"shape_id": _static_id(shape), **_shape_info(shape), "rx": rx, "ry": ry}

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
        return {"shape_id": _static_id(shape), **_shape_info(shape), "x1": x1, "y1": y1, "x2": x2, "y2": y2}

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
                    return {"path": path, "shape_id": _static_id(last_shape), **_shape_info(last_shape), "x": x, "y": y}
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
                return {"path": path, "shape_id": _static_id(last_shape), **_shape_info(last_shape), "x": x, "y": y}
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
        selection = _create_shape_range(selected)
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
        group = _create_shape_range(selected).Group()
        return {"group_id": _static_id(group), "member_count": len(ids), "member_ids": ids}

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
        return {"found": True, **_shape_info(shape), "shape_id": _static_id(shape)}

    result = conn.safe_call(_find)
    if result["success"]:
        if result["result"]["found"]:
            return ToolResult.ok(f"找到形状: {name}", **result["result"])
        return ToolResult.ok(f"未找到形状: {name}", **result["result"])
    return ToolResult.fail(result.get("error", "查找形状失败"))


# ========== P0 排版必需品 ==========

_ALIGN_DIRECTIONS = {"left", "center", "right", "top", "middle", "bottom"}
_Z_ORDER_ACTIONS = {"front", "back", "forward", "backward"}
_CDR_MILLIMETER = 3


def _get_shape_bounds(shape):
    """获取形状的边界信息（位置 + 尺寸），用于对齐/分布计算。返回 dict 或 None。"""
    try:
        x = shape.PositionX
        y = shape.PositionY
        w = shape.SizeWidth
        h = shape.SizeHeight
        return {
            "x": x, "y": y, "w": w, "h": h,
            "center_x": x + w / 2, "center_y": y + h / 2,
            "right": x + w, "bottom": y + h,
        }
    except Exception:
        return None


def _get_page_size(doc):
    """获取当前页面的宽度和高度（mm）。"""
    try:
        doc.Unit = _CDR_MILLIMETER
        page = doc.ActivePage
        return page.SizeWidth, page.SizeHeight
    except Exception:
        return 0, 0


def align_shapes(shape_ids: str, alignment: str, reference: str = "selection") -> ToolResult:
    """将多个形状对齐。alignment: left/center/right/top/middle/bottom。
    reference='selection' 在形状间对齐，reference='page' 对齐到页面边缘。
    shape_ids 为逗号分隔的形状 ID 或名称列表。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    alignment = alignment.lower()
    if alignment not in _ALIGN_DIRECTIONS:
        return ToolResult.fail(f"不支持的对齐方式: {alignment}，可选: {', '.join(sorted(_ALIGN_DIRECTIONS))}")

    def _align():
        ids = [s.strip() for s in shape_ids.split(",") if s.strip()]
        if not ids:
            raise ValueError("请提供至少一个形状 ID")

        shapes = []
        bounds = []
        for sid in ids:
            shape = _find_shape(sid)
            if shape is None:
                raise ValueError(f"未找到形状: {sid}")
            b = _get_shape_bounds(shape)
            if b is None:
                raise ValueError(f"无法读取形状 {sid} 的位置信息")
            shapes.append(shape)
            bounds.append(b)

        if reference == "page":
            page_w, page_h = _get_page_size(conn.app.ActiveDocument)
            for shape, b in zip(shapes, bounds):
                if alignment == "left":
                    shape.SetPosition(0, b["y"])
                elif alignment == "center":
                    new_x = (page_w - b["w"]) / 2
                    shape.SetPosition(new_x, b["y"])
                elif alignment == "right":
                    shape.SetPosition(page_w - b["w"], b["y"])
                elif alignment == "top":
                    shape.SetPosition(b["x"], 0)
                elif alignment == "middle":
                    new_y = (page_h - b["h"]) / 2
                    shape.SetPosition(b["x"], new_y)
                elif alignment == "bottom":
                    shape.SetPosition(b["x"], page_h - b["h"])
        else:
            # selection 模式：以第一个形状为基准对齐其他形状
            if len(shapes) < 2:
                raise ValueError("selection 模式至少需要两个形状（或使用 reference='page'）")
            ref_bounds = bounds[0]
            for shape, b in zip(shapes[1:], bounds[1:]):
                if alignment == "left":
                    shape.SetPosition(ref_bounds["x"], b["y"])
                elif alignment == "center":
                    new_x = ref_bounds["center_x"] - b["w"] / 2
                    shape.SetPosition(new_x, b["y"])
                elif alignment == "right":
                    shape.SetPosition(ref_bounds["right"] - b["w"], b["y"])
                elif alignment == "top":
                    shape.SetPosition(b["x"], ref_bounds["y"])
                elif alignment == "middle":
                    new_y = ref_bounds["center_y"] - b["h"] / 2
                    shape.SetPosition(b["x"], new_y)
                elif alignment == "bottom":
                    shape.SetPosition(b["x"], ref_bounds["bottom"] - b["h"])

        return {"shape_count": len(shapes), "alignment": alignment, "reference": reference}

    result = conn.safe_call(_align)
    if result["success"]:
        return ToolResult.ok(f"对齐完成: {alignment} ({reference})", **result["result"])
    return ToolResult.fail(result.get("error", "对齐失败"))


def distribute_shapes(shape_ids: str, direction: str = "horizontal", spacing: float = 0) -> ToolResult:
    """将多个形状等距分布。direction: horizontal/vertical。spacing>0 时使用固定间距，
    否则在最小和最大边界之间均匀分布。shape_ids 为逗号分隔。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    direction = direction.lower()
    if direction not in ("horizontal", "vertical"):
        return ToolResult.fail("direction 仅支持 'horizontal' 或 'vertical'")

    def _distribute():
        ids = [s.strip() for s in shape_ids.split(",") if s.strip()]
        if len(ids) < 3:
            raise ValueError("分布至少需要三个形状")

        shapes = []
        bounds = []
        for sid in ids:
            shape = _find_shape(sid)
            if shape is None:
                raise ValueError(f"未找到形状: {sid}")
            b = _get_shape_bounds(shape)
            if b is None:
                raise ValueError(f"无法读取形状 {sid} 的位置信息")
            shapes.append(shape)
            bounds.append(b)

        if direction == "horizontal":
            # 按 X 排序
            pairs = sorted(zip(shapes, bounds), key=lambda p: p[1]["x"])
            if spacing > 0:
                # 固定间距，以第一个为起点
                ref_x = pairs[0][1]["x"]
                for i, (shape, b) in enumerate(pairs):
                    new_x = ref_x + i * spacing
                    shape.SetPosition(new_x, b["y"])
            else:
                # 均匀分布：总跨度 / (n-1)
                min_x = pairs[0][1]["x"]
                max_x = pairs[-1][1]["x"] + pairs[-1][1]["w"]
                total_span = max_x - min_x
                if len(pairs) > 1:
                    step = total_span / (len(pairs) - 1)
                else:
                    step = 0
                for i, (shape, b) in enumerate(pairs[1:-1]):
                    target_center_x = min_x + (i + 1) * step - b["w"] / 2
                    shape.SetPosition(target_center_x, b["y"])
        else:
            # 按 Y 排序
            pairs = sorted(zip(shapes, bounds), key=lambda p: p[1]["y"])
            if spacing > 0:
                ref_y = pairs[0][1]["y"]
                for i, (shape, b) in enumerate(pairs):
                    new_y = ref_y + i * spacing
                    shape.SetPosition(b["x"], new_y)
            else:
                min_y = pairs[0][1]["y"]
                max_y = pairs[-1][1]["y"] + pairs[-1][1]["h"]
                total_span = max_y - min_y
                if len(pairs) > 1:
                    step = total_span / (len(pairs) - 1)
                else:
                    step = 0
                for i, (shape, b) in enumerate(pairs[1:-1]):
                    target_center_y = min_y + (i + 1) * step - b["h"] / 2
                    shape.SetPosition(b["x"], target_center_y)

        return {"shape_count": len(shapes), "direction": direction, "spacing": spacing}

    result = conn.safe_call(_distribute)
    if result["success"]:
        return ToolResult.ok(f"分布完成: {direction} ({result['result']['shape_count']}个形状)", **result["result"])
    return ToolResult.fail(result.get("error", "分布失败"))


def set_z_order(shape_id: str, action: str) -> ToolResult:
    """控制形状的层级顺序。action: front(置顶)/back(置底)/forward(上移一层)/backward(下移一层)。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    action = action.lower()
    if action not in _Z_ORDER_ACTIONS:
        return ToolResult.fail(f"不支持的层级操作: {action}，可选: {', '.join(sorted(_Z_ORDER_ACTIONS))}")

    def _order():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        if action == "front":
            shape.OrderToFront()
        elif action == "back":
            shape.OrderToBack()
        elif action == "forward":
            shape.OrderForwardOne()
        elif action == "backward":
            shape.OrderBackOne()
        return {"shape_id": shape_id, "action": action}

    result = conn.safe_call(_order)
    if result["success"]:
        action_names = {"front": "置顶", "back": "置底", "forward": "上移一层", "backward": "下移一层"}
        return ToolResult.ok(f"层级调整: {shape_id} → {action_names.get(action, action)}", **result["result"])
    return ToolResult.fail(result.get("error", "层级操作失败"))


def delete_shape(shape_id: str) -> ToolResult:
    """删除指定的形状。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _delete():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        name = shape.Name or shape_id
        shape.Delete()
        return {"shape_id": shape_id, "name": name, "deleted": True}

    result = conn.safe_call(_delete)
    if result["success"]:
        return ToolResult.ok(f"已删除: {result['result']['name']}", **result["result"])
    return ToolResult.fail(result.get("error", "删除形状失败"))


def rotate_shape(shape_id: str, angle: float, center_x: float = 0, center_y: float = 0) -> ToolResult:
    """旋转形状。angle 为旋转角度（度，正值逆时针），center_x/center_y 为旋转中心（0=形状自身中心）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _rotate():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        old_angle = 0.0
        try:
            old_angle = shape.RotationAngle
        except Exception:
            pass
        if center_x != 0 or center_y != 0:
            try:
                # 尝试设置旋转中心（CorelDRAW X6+ 支持）
                shape.RotationCenterX = center_x
                shape.RotationCenterY = center_y
            except Exception:
                pass
        shape.RotationAngle = angle
        return {"shape_id": shape_id, "angle": angle, "old_angle": round(old_angle, 2)}

    result = conn.safe_call(_rotate)
    if result["success"]:
        return ToolResult.ok(f"形状已旋转: {shape_id} → {angle}°", **result["result"])
    return ToolResult.fail(result.get("error", "旋转失败"))


def ungroup_shapes(shape_id: str, recursive: bool = False) -> ToolResult:
    """取消群组。shape_id 为群组形状的 ID；recursive=True 时递归取消全部子群组。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _ungroup():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        # 检查是否为群组
        try:
            is_group = shape.Type == 7  # cdrGroupShape
        except Exception:
            is_group = False
        if not is_group:
            # duck-type：尝试读取子形状
            try:
                _ = shape.Shapes
                is_group = True
            except Exception:
                pass
        if not is_group:
            raise ValueError(f"形状 {shape_id} 不是一个群组")

        if recursive:
            try:
                shape.UngroupAll()
            except Exception:
                shape.Ungroup()
        else:
            shape.Ungroup()
        return {"shape_id": shape_id, "recursive": recursive, "ungrouped": True}

    result = conn.safe_call(_ungroup)
    if result["success"]:
        detail = "递归取消群组" if recursive else "取消群组"
        return ToolResult.ok(f"{detail}: {shape_id}", **result["result"])
    return ToolResult.fail(result.get("error", "取消群组失败"))


def scale_shape(shape_id: str, scale_x: float, scale_y: float = 0, keep_proportion: bool = False) -> ToolResult:
    """等比/非等比缩放形状。scale_x 为 X 方向缩放因子（1.0=原尺寸，2.0=放大一倍）。
    scale_y 为 Y 方向缩放因子，为 0 时与 scale_x 相同（等比）。
    keep_proportion=True 时忽略 scale_y 强制等比缩放。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    if scale_x <= 0:
        return ToolResult.fail(f"缩放因子必须大于 0，当前 scale_x={scale_x}")

    scale_y = scale_y if scale_y > 0 else scale_x

    def _scale():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        old_w = shape.SizeWidth
        old_h = shape.SizeHeight
        new_w = old_w * scale_x
        new_h = old_h * (scale_x if keep_proportion else scale_y)
        # 保持中心点不变缩放
        cx = shape.PositionX + old_w / 2
        cy = shape.PositionY + old_h / 2
        shape.SetSize(new_w, new_h)
        shape.SetPosition(cx - new_w / 2, cy - new_h / 2)
        return {
            "shape_id": shape_id,
            "scale_x": scale_x,
            "scale_y": scale_x if keep_proportion else scale_y,
            "old_size": {"width": round(old_w, 2), "height": round(old_h, 2)},
            "new_size": {"width": round(new_w, 2), "height": round(new_h, 2)},
        }

    result = conn.safe_call(_scale)
    if result["success"]:
        r = result["result"]
        return ToolResult.ok(
            f"缩放: {r['old_size']['width']}×{r['old_size']['height']} "
            f"→ {r['new_size']['width']}×{r['new_size']['height']}",
            **r,
        )
    return ToolResult.fail(result.get("error", "缩放失败"))


# ========== P1 增强工具 ==========


def select_shapes(by_type: str = "", by_layer: str = "", by_name_pattern: str = "") -> ToolResult:
    """按条件选择形状并返回匹配的形状列表。
    by_type: rectangle/ellipse/curve/text/bitmap/group 等
    by_layer: 图层名称
    by_name_pattern: 名称包含此字符串的形状

    不修改 CorelDRAW 中的实际选中状态，只返回匹配列表供其他工具使用。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    _TYPE_MAP = {
        "rectangle": 1, "ellipse": 2, "curve": 4, "text": 3,
        "bitmap": 6, "group": 7, "line": 1, "polygon": 5,
    }

    def _select():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        page = doc.ActivePage
        matched = []

        for s in page.Shapes:
            # 按图层过滤
            if by_layer:
                try:
                    if s.Layer.Name != by_layer:
                        continue
                except Exception:
                    continue

            # 按类型过滤
            if by_type:
                type_lower = by_type.lower()
                expected = _TYPE_MAP.get(type_lower, -1)
                try:
                    if expected >= 0 and s.Type != expected:
                        continue
                except Exception:
                    continue

            # 按名称模式过滤
            if by_name_pattern:
                try:
                    name = s.Name or ""
                    if by_name_pattern.lower() not in name.lower():
                        continue
                except Exception:
                    continue

            # 提取形状信息
            info = _shape_info(s)
            info["shape_id"] = ""
            try:
                info["shape_id"] = str(s.StaticID)
            except Exception:
                pass
            try:
                info["layer"] = s.Layer.Name
            except Exception:
                info["layer"] = ""
            matched.append(info)

        return {"count": len(matched), "shapes": matched, "criteria": {
            "by_type": by_type, "by_layer": by_layer, "by_name_pattern": by_name_pattern,
        }}

    result = conn.safe_call(_select)
    if result["success"]:
        r = result["result"]
        criteria_parts = []
        if by_type:
            criteria_parts.append(f"类型={by_type}")
        if by_layer:
            criteria_parts.append(f"图层={by_layer}")
        if by_name_pattern:
            criteria_parts.append(f"名称包含'{by_name_pattern}'")
        return ToolResult.ok(f"找到 {r['count']} 个匹配形状 ({', '.join(criteria_parts)})", **r)
    return ToolResult.fail(result.get("error", "选择形状失败"))


def powerclip(content_shape_id: str, container_shape_id: str) -> ToolResult:
    """将 content 形状放入 container 形状内（PowerClip）。
    类似于 AI 的剪切蒙版，用于将图案/文字限制在特定区域内。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _clip():
        content = _find_shape(content_shape_id)
        if content is None:
            raise ValueError(f"未找到内容形状: {content_shape_id}")
        container = _find_shape(container_shape_id)
        if container is None:
            raise ValueError(f"未找到容器形状: {container_shape_id}")

        placed = False
        for method in (
            lambda: content.AddToPowerClip(container, -2),
            lambda: _create_shape_range([content]).AddToPowerClip(container, -2),
            lambda: content.CreatePowerClip(container),
            lambda: container.PowerClip.Place(content),
            lambda: conn.app.ActiveDocument.CreatePowerClip(content, container),
        ):
            try:
                method()
                placed = True
                break
            except Exception:
                continue

        if not placed:
            raise RuntimeError("当前 CorelDRAW 版本不支持已知的 PowerClip API")

        return {
            "content_id": content_shape_id,
            "container_id": container_shape_id,
            "powerclip_created": True,
        }

    result = conn.safe_call(_clip)
    if result["success"]:
        return ToolResult.ok(
            f"PowerClip: {content_shape_id} → {container_shape_id}",
            **result["result"],
        )
    return ToolResult.fail(result.get("error", "PowerClip 操作失败"))


# ========== P2 重命名/复制/翻转/锁定 ==========

# cdrFlipDirection: cdrFlipHorizontal=0, cdrFlipVertical=1 (硬编码，来自 CorelDRAW 类型库)
_FLIP_DIRECTIONS = {"horizontal": 0, "vertical": 1}


def rename_shape(shape_id: str, new_name: str) -> ToolResult:
    """重命名形状。shape_id 为当前名称或 StaticID，new_name 为新名称。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _rename():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        old_name = shape.Name or ""
        shape.Name = new_name
        return {"shape_id": _static_id(shape), "old_name": old_name, "new_name": new_name}

    result = conn.safe_call(_rename)
    if result["success"]:
        r = result["result"]
        return ToolResult.ok(f"形状已重命名: '{r['old_name']}' → '{r['new_name']}'", **r)
    return ToolResult.fail(result.get("error", "重命名失败"))


def duplicate_shape(shape_id: str, offset_x: float = 0, offset_y: float = 0, new_name: str = "") -> ToolResult:
    """复制单个形状，副本相对原形状偏移 offset_x/offset_y（mm，默认 0 即原地重叠，
    通常配合 set_shape_position 使用）。new_name 留空则自动生成 "<原名>_copy"。
    返回新形状的完整信息（含 shape_id），原形状不受影响。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _duplicate():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        original_name = shape.Name or str(shape.StaticID)
        new_shape = shape.Duplicate(offset_x, offset_y)
        new_shape.Name = new_name if new_name else f"{original_name}_copy_{new_shape.StaticID}"
        return {"source_shape_id": shape_id, "shape_id": _static_id(new_shape), **_shape_info(new_shape)}

    result = conn.safe_call(_duplicate)
    if result["success"]:
        r = result["result"]
        return ToolResult.ok(f"形状已复制: {shape_id} → {r['shape_id']}", **r)
    return ToolResult.fail(result.get("error", "复制形状失败"))


def duplicate_shape_batch(
    shape_id: str,
    count: int,
    offset_x: float = 0,
    offset_y: float = 0,
    name_pattern: str = "",
) -> ToolResult:
    """批量复制同一个形状，一次生成多份副本（"each by each" 场景，如批量生产同款标牌坯）。
    count 为副本数量（不含原始形状，必须 ≥1）。
    第 i 份（i 从 1 开始）相对原形状偏移 (offset_x*i, offset_y*i)，用于自动排成一行/一列。
    name_pattern 支持占位符 {name}（原名称）和 {n}（序号，从 1 开始），留空则用 "{name}_copy{n}"。
    返回每份副本的 shape_id 及完整信息，可直接用于后续逐个 set_shape_size / set_text_content / rename_shape。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    if count < 1:
        return ToolResult.fail("count 必须大于等于 1")

    def _duplicate_batch():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        original_name = shape.Name or str(shape.StaticID)
        pattern = name_pattern or "{name}_copy{n}"
        created = []
        for i in range(1, count + 1):
            new_shape = shape.Duplicate(offset_x * i, offset_y * i)
            new_shape.Name = pattern.replace("{name}", original_name).replace("{n}", str(i))
            created.append({"shape_id": _static_id(new_shape), **_shape_info(new_shape)})
        return {"source_shape_id": shape_id, "count": count, "created": created}

    result = conn.safe_call(_duplicate_batch)
    if result["success"]:
        r = result["result"]
        return ToolResult.ok(f"已批量复制 {r['count']} 份: {shape_id}", **r)
    return ToolResult.fail(result.get("error", "批量复制失败"))


def duplicate_shapes(shape_ids: str, offset_x: float = 0, offset_y: float = 0) -> ToolResult:
    """整体复制多个形状并保持相对位置关系（如复制一整套已排好版的标牌元素）。
    shape_ids 为逗号分隔的 ID 或名称列表，副本整体相对原始位置偏移 offset_x/offset_y（mm）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _duplicate():
        ids = [s.strip() for s in shape_ids.split(",") if s.strip()]
        if not ids:
            raise ValueError("请提供至少一个形状 ID")
        shapes = []
        for sid in ids:
            shape = _find_shape(sid)
            if shape is None:
                raise ValueError(f"未找到形状: {sid}")
            shapes.append(shape)
        shape_range = _create_shape_range(shapes)
        new_range = shape_range.Duplicate(offset_x, offset_y)
        created = [{"shape_id": _static_id(s), **_shape_info(s)} for s in new_range]
        return {"source_ids": ids, "count": len(created), "created": created}

    result = conn.safe_call(_duplicate)
    if result["success"]:
        r = result["result"]
        return ToolResult.ok(f"已整体复制 {r['count']} 个形状", **r)
    return ToolResult.fail(result.get("error", "整体复制失败"))


def set_shape_locked(shape_id: str, locked: bool) -> ToolResult:
    """锁定或解锁形状，锁定后该形状在 CorelDRAW 界面中不可选中/编辑（不影响脚本操作）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _set():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        shape.Locked = locked
        return {"shape_id": shape_id, "locked": locked}

    result = conn.safe_call(_set)
    if result["success"]:
        status = "已锁定" if locked else "已解锁"
        return ToolResult.ok(f"形状{status}: {shape_id}", **result["result"])
    return ToolResult.fail(result.get("error", "设置锁定状态失败"))


def flip_shape(shape_id: str, direction: str) -> ToolResult:
    """水平或垂直翻转（镜像）形状，围绕形状自身中心。direction: horizontal/vertical。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    direction = direction.lower()
    if direction not in _FLIP_DIRECTIONS:
        return ToolResult.fail(f"不支持的翻转方向: {direction}，可选: horizontal/vertical")

    def _flip():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        shape.Flip(_FLIP_DIRECTIONS[direction])
        return {"shape_id": shape_id, "direction": direction}

    result = conn.safe_call(_flip)
    if result["success"]:
        label = "水平" if direction == "horizontal" else "垂直"
        return ToolResult.ok(f"形状已{label}翻转: {shape_id}", **result["result"])
    return ToolResult.fail(result.get("error", "翻转形状失败"))
