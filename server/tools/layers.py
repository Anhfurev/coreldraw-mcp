"""图层管理工具 — 创建/锁/显隐图层，形状图层分配"""

from core.connection import get_connection
from core.models import ToolResult


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


def create_layer(name: str, color: str = "") -> ToolResult:
    """创建新图层。color 用于图层标识（激光机识别），如 'red' / 'blue'。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _create():
        page = conn.app.ActiveDocument.ActivePage
        layer = page.CreateLayer(name)
        # Ensure layer is visible and printable (X6 defaults can vary)
        for attr in ("Visible", "Printable", "Editable"):
            try:
                setattr(layer, attr, True)
            except Exception:
                pass
        if color:
            try:
                layer.Color = color
            except Exception:
                pass
        return {"name": name, "color": color, "visible": True, "editable": True}

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"图层已创建: {name}", **result["result"])
    return ToolResult.fail(result.get("error", "创建图层失败"))


def get_layers() -> ToolResult:
    """获取当前页面的所有图层信息。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _list():
        page = conn.app.ActiveDocument.ActivePage
        layers_list = []
        try:
            for layer in page.Layers:
                layer_info = {"name": layer.Name}
                try:
                    layer_info["visible"] = layer.Visible
                except Exception:
                    layer_info["visible"] = True
                try:
                    layer_info["editable"] = layer.Editable
                except Exception:
                    layer_info["editable"] = True
                try:
                    layer_info["locked"] = not layer.Editable
                except Exception:
                    layer_info["locked"] = False
                try:
                    layer_info["color"] = layer.Color
                except Exception:
                    layer_info["color"] = ""
                try:
                    layer_info["shapes_count"] = layer.Shapes.Count
                except Exception:
                    layer_info["shapes_count"] = 0
                layers_list.append(layer_info)
        except Exception:
            pass
        return {"layers": layers_list, "count": len(layers_list)}

    result = conn.safe_call(_list)
    if result["success"]:
        return ToolResult.ok(f"共 {result['result']['count']} 个图层", **result["result"])
    return ToolResult.fail(result.get("error", "获取图层列表失败"))


def assign_to_layer(shape_id: str, layer_name: str) -> ToolResult:
    """将形状移动到指定图层。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _assign():
        shape = _find_shape(shape_id)
        if shape is None:
            raise ValueError(f"未找到形状: {shape_id}")
        page = conn.app.ActiveDocument.ActivePage
        target_layer = None
        try:
            target_layer = page.Layers(layer_name)
        except Exception:
            raise ValueError(f"未找到图层: {layer_name}")
        target_layer.Activate()
        # 将形状移动到目标图层
        try:
            shape.MoveToLayer(target_layer)
        except Exception:
            try:
                shape.Layer = target_layer
            except Exception:
                raise RuntimeError(f"无法移动形状到图层: {layer_name}")
        return {"shape_id": shape_id, "layer": layer_name}

    result = conn.safe_call(_assign)
    if result["success"]:
        return ToolResult.ok(f"形状已移至图层: {layer_name}", **result["result"])
    return ToolResult.fail(result.get("error", "分配图层失败"))


def set_layer_visible(layer_name: str, visible: bool) -> ToolResult:
    """设置图层的可见性。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _set():
        page = conn.app.ActiveDocument.ActivePage
        try:
            layer = page.Layers(layer_name)
        except Exception:
            raise ValueError(f"未找到图层: {layer_name}")
        layer.Visible = visible
        return {"layer": layer_name, "visible": visible}

    result = conn.safe_call(_set)
    if result["success"]:
        status = "可见" if visible else "隐藏"
        return ToolResult.ok(f"图层 {layer_name} 已设为{status}", **result["result"])
    return ToolResult.fail(result.get("error", "设置图层可见性失败"))


def lock_layer(layer_name: str) -> ToolResult:
    """锁定图层，防止意外编辑。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _lock():
        page = conn.app.ActiveDocument.ActivePage
        try:
            layer = page.Layers(layer_name)
        except Exception:
            raise ValueError(f"未找到图层: {layer_name}")
        layer.Editable = False
        return {"layer": layer_name, "locked": True}

    result = conn.safe_call(_lock)
    if result["success"]:
        return ToolResult.ok(f"图层已锁定: {layer_name}", **result["result"])
    return ToolResult.fail(result.get("error", "锁定图层失败"))
