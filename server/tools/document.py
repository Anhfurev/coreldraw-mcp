"""文档管理工具 — 打开模板、创建/保存/关闭文档、页面管理"""

from core.connection import get_connection
from core.models import ToolResult

_UNIT_MAP = {"mm": 2, "cm": 3, "inch": 1, "pt": 4, "px": 5}


def _get_page_size(doc):
    """读取当前页面尺寸（mm）"""
    try:
        doc.Unit = 2  # cdrMillimeter
        page = doc.ActivePage
        return page.SizeWidth, page.SizeHeight
    except Exception:
        return 0.0, 0.0


def open_template(path: str) -> ToolResult:
    """打开 CDR 模板文件。path 为模板文件的绝对路径。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _open():
        import os
        if not os.path.isfile(path):
            raise FileNotFoundError(f"模板文件不存在: {path}")
        doc = conn.app.OpenDocument(path)
        doc.Unit = 2  # cdrMillimeter
        width, height = _get_page_size(doc)
        return {"path": path, "pages": doc.Pages.Count, "width": width, "height": height}

    result = conn.safe_call(_open)
    if result["success"]:
        return ToolResult.ok(f"模板已打开: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "打开模板失败"))


def create_document(width: float, height: float, unit: str = "mm") -> ToolResult:
    """新建指定尺寸的 CorelDRAW 文档。width/height 为文档尺寸，unit 支持 mm/cm/inch/pt/px。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _create():
        doc = conn.app.CreateDocument()
        cdr_unit = _UNIT_MAP.get(unit.lower(), 2)
        doc.Unit = cdr_unit
        page = doc.ActivePage
        page.SetSize(width, height)
        return {"width": width, "height": height, "unit": unit, "pages": 1}

    result = conn.safe_call(_create)
    if result["success"]:
        return ToolResult.ok(f"新建文档: {width}×{height} {unit}", **result["result"])
    return ToolResult.fail(result.get("error", "创建文档失败"))


def save_document(path: str = "") -> ToolResult:
    """保存当前文档。path 为空时保存到原路径，否则另存为指定路径。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _save():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        if path:
            doc.SaveAs(path)
            saved_path = path
        else:
            doc.Save()
            saved_path = doc.FilePath + doc.FileName if doc.FilePath else "未命名.cdr"
        return {"path": saved_path}

    result = conn.safe_call(_save)
    if result["success"]:
        return ToolResult.ok(f"文档已保存: {result['result']['path']}")
    return ToolResult.fail(result.get("error", "保存文档失败"))


def close_document() -> ToolResult:
    """关闭当前文档。如有未保存修改会提示。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _close():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        name = doc.FileName or "未命名"
        modified = doc.Modified if hasattr(doc, "Modified") else False
        doc.Close()
        return {"name": name, "had_unsaved_changes": modified}

    result = conn.safe_call(_close)
    if result["success"]:
        info = result["result"]
        msg = f"已关闭: {info['name']}"
        if info.get("had_unsaved_changes"):
            msg += "（如有未保存修改）"
        return ToolResult.ok(msg, **info)
    return ToolResult.fail(result.get("error", "关闭文档失败"))


def add_page() -> ToolResult:
    """在当前文档末尾添加一个新页面，并激活它。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _add():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        doc.AddPages(1)
        page = doc.Pages.Last
        page.Activate()
        width, height = _get_page_size(doc)
        return {"page_index": page.Index, "total_pages": doc.Pages.Count, "width": width, "height": height}

    result = conn.safe_call(_add)
    if result["success"]:
        return ToolResult.ok("已添加新页面", **result["result"])
    return ToolResult.fail(result.get("error", "添加页面失败"))


def set_page_size(width: float, height: float) -> ToolResult:
    """修改当前页面尺寸（mm）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _set():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        doc.Unit = 2  # cdrMillimeter
        page = doc.ActivePage
        page.SetSize(width, height)
        return {"width": width, "height": height, "unit": "mm"}

    result = conn.safe_call(_set)
    if result["success"]:
        return ToolResult.ok(f"页面尺寸已设为: {width}×{height} mm", **result["result"])
    return ToolResult.fail(result.get("error", "设置页面尺寸失败"))


def get_document_info() -> ToolResult:
    """获取当前文档的状态信息：路径、页数、尺寸、形状数等。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _info():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        doc.Unit = 2
        page = doc.ActivePage
        width, height = _get_page_size(doc)

        shapes_count = 0
        text_shapes = 0
        try:
            shapes = page.Shapes
            shapes_count = shapes.Count
            for s in shapes:
                if s.Type == 3:  # cdrTextShape
                    text_shapes += 1
        except Exception:
            pass

        layers_info = []
        try:
            for layer in page.Layers:
                layers_info.append({
                    "name": layer.Name,
                    "visible": layer.Visible if hasattr(layer, "Visible") else True,
                    "editable": layer.Editable if hasattr(layer, "Editable") else True,
                })
        except Exception:
            pass

        return {
            "name": doc.FileName or "未命名",
            "path": doc.FilePath or "",
            "pages": doc.Pages.Count,
            "current_page": page.Index,
            "width": round(width, 2),
            "height": round(height, 2),
            "unit": "mm",
            "shapes_count": shapes_count,
            "text_shapes_count": text_shapes,
            "layers": layers_info,
        }

    result = conn.safe_call(_info)
    if result["success"]:
        return ToolResult.ok("文档信息获取成功", **result["result"])
    return ToolResult.fail(result.get("error", "获取文档信息失败"))
