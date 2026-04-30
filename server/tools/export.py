"""导出工具 — PDF/DXF/AI/SVG/PNG 导出，预览 PNG 及批量导出"""

import os

from core.connection import get_connection
from core.models import ToolResult

# 导出滤镜常量（CorelDRAW X6/16.1 COM 滤镜编号）
_CDR_DXF = 1296
_CDR_AI = 1305
_CDR_SVG = 1345
_CDR_PNG = 802
_CDR_JPEG = 774

_CDR_ALL_PAGES = 0
_CDR_CURRENT_PAGE = 1
_PDF_CURRENT_PAGE = 1
_CDR_RGB_COLOR_IMAGE = 4
_CDR_NORMAL_ANTIALIASING = 1
_CDR_COMPRESSION_NONE = 0
_CDR_MILLIMETER = 3

_DXF_VERSION = {"R12": 0, "R14": 1, "R2000": 3, "R2004": 4}


def _ensure_dir(path: str) -> None:
    """确保输出目录存在"""
    dirpath = os.path.dirname(path)
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)


def _page_size_mm(doc):
    """获取页面尺寸（mm）"""
    try:
        doc.Unit = _CDR_MILLIMETER
        page = doc.ActivePage
        return page.SizeWidth, page.SizeHeight
    except Exception:
        return 0, 0


def _prepare_current_page_export(doc) -> int:
    """Make export state explicit so CorelDRAW does not reuse stale UI settings."""
    doc.Unit = _CDR_MILLIMETER
    page = doc.ActivePage
    shapes_count = 0
    try:
        shapes_count = page.Shapes.Count
    except Exception:
        pass
    try:
        doc.ClearSelection()
    except Exception:
        pass
    try:
        page.Activate()
    except Exception:
        pass
    try:
        for layer in page.Layers:
            for attr in ("Visible", "Printable"):
                try:
                    setattr(layer, attr, True)
                except Exception:
                    pass
    except Exception:
        pass
    return shapes_count


def _finish_export_filter(export_filter) -> None:
    if export_filter is not None:
        export_filter.Finish()


def _file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


def _verify_exported(path: str) -> int:
    size = _file_size(path)
    if size <= 0:
        raise RuntimeError(f"导出失败，文件未生成或为空: {path}")
    return size


def _page_export_area(app, doc):
    page_w_mm, page_h_mm = _page_size_mm(doc)
    if page_w_mm <= 0 or page_h_mm <= 0:
        return None
    try:
        return app.CreateRect(0, 0, page_w_mm, page_h_mm)
    except Exception:
        return None


def export_pdf(
    path: str,
    color_profile: str = "ISO_Coated_v2",
    bleed: float = 3.0,
    crop_marks: bool = True,
    multi_page: bool = False,
) -> ToolResult:
    """导出印刷级 PDF。支持色彩配置、出血、裁切线和多页导出。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _export():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        _ensure_dir(path)
        shapes_count = _prepare_current_page_export(doc)
        try:
            doc.PDFSettings.ColorMode = 1  # cdrPDFCMYK
            doc.PDFSettings.BleedingLimit = bleed
            doc.PDFSettings.PrintCropMarks = crop_marks
            doc.PDFSettings.MultiPage = multi_page
            doc.PDFSettings.PublishRange = _CDR_ALL_PAGES if multi_page else _PDF_CURRENT_PAGE
            doc.PDFSettings.PageRange = "" if multi_page else str(doc.ActivePage.Index)
            doc.PDFSettings.TextAsCurves = True
        except Exception:
            pass
        # 尝试加载 ICC Profile（CorelDRAW 版本间 API 名称不同，逐一尝试）
        if color_profile:
            for attr in ("ColorProfileName", "ColorProfile", "OutputColorProfile", "ICCProfileName"):
                try:
                    setattr(doc.PDFSettings, attr, color_profile)
                    break
                except Exception:
                    continue
        doc.PublishToPDF(path)
        file_size = _verify_exported(path)
        return {
            "path": path,
            "color_profile": color_profile,
            "bleed": bleed,
            "crop_marks": crop_marks,
            "shapes_count": shapes_count,
            "file_size": file_size,
        }

    result = conn.safe_call(_export)
    if result["success"]:
        return ToolResult.ok(f"PDF 已导出: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "导出 PDF 失败"))


def export_dxf(path: str, version: str = "R14", layer_filter: str = "", export_hidden: bool = False) -> ToolResult:
    """导出 DXF 文件（用于激光雕刻/切割）。支持版本选择和图层过滤。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    dxf_ver = _DXF_VERSION.get(version, 1)

    def _export():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        _ensure_dir(path)
        shapes_count = _prepare_current_page_export(doc)
        # Try ExportEx (newer CorelDRAW). X6 often rejects this with COM object error;
        # fall back to basic Export which works silently in automation mode.
        try:
            expflt = doc.ExportEx(path, _CDR_DXF, _CDR_CURRENT_PAGE, None, None)
            for attr, val in [("BitmapType", 0), ("TextAsCurves", True),
                              ("Version", dxf_ver), ("Units", 3), ("FillUnmapped", True)]:
                try:
                    setattr(expflt, attr, val)
                except Exception:
                    pass
            if layer_filter:
                filter_layers = [l.strip() for l in layer_filter.split(",") if l.strip()]
                if filter_layers:
                    try:
                        expflt.LayerFilter = ",".join(filter_layers)
                    except Exception:
                        pass
            _finish_export_filter(expflt)
        except Exception:
            doc.Export(path, _CDR_DXF, _CDR_CURRENT_PAGE, None, None)
        file_size = _verify_exported(path)
        return {
            "path": path,
            "version": version,
            "text_as_curves": True,
            "shapes_count": shapes_count,
            "file_size": file_size,
        }

    result = conn.safe_call(_export)
    if result["success"]:
        return ToolResult.ok(f"DXF 已导出: {path} (v{version})", **result["result"])
    return ToolResult.fail(result.get("error", "导出 DXF 失败"))


def export_ai(path: str) -> ToolResult:
    """导出 Adobe Illustrator AI 格式。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _export():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        _ensure_dir(path)
        shapes_count = _prepare_current_page_export(doc)
        doc.Export(path, _CDR_AI, _CDR_CURRENT_PAGE, None, None)
        file_size = _verify_exported(path)
        return {"path": path, "format": "ai", "shapes_count": shapes_count, "file_size": file_size}

    result = conn.safe_call(_export)
    if result["success"]:
        return ToolResult.ok(f"AI 已导出: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "导出 AI 失败"))


def export_svg(path: str) -> ToolResult:
    """导出 SVG 矢量格式。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _export():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        _ensure_dir(path)
        shapes_count = _prepare_current_page_export(doc)
        doc.Export(path, _CDR_SVG, _CDR_CURRENT_PAGE, None, None)
        file_size = _verify_exported(path)
        return {"path": path, "format": "svg", "shapes_count": shapes_count, "file_size": file_size}

    result = conn.safe_call(_export)
    if result["success"]:
        return ToolResult.ok(f"SVG 已导出: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "导出 SVG 失败"))


def export_png(path: str, dpi: int = 300, width: int = 0, background_transparent: bool = False) -> ToolResult:
    """导出 PNG 位图。可指定 DPI、宽度和透明背景。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _export():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        _ensure_dir(path)
        shapes_count = _prepare_current_page_export(doc)
        page_w_mm, page_h_mm = _page_size_mm(doc)
        if width > 0 and page_w_mm > 0:
            export_dpi = int(width / (page_w_mm / 25.4))
        else:
            export_dpi = dpi
        export_dpi = max(72, export_dpi)
        if page_w_mm > 0 and page_h_mm > 0:
            pixel_w = max(1, int(page_w_mm / 25.4 * export_dpi))
            pixel_h = max(1, int(page_h_mm / 25.4 * export_dpi))
        else:
            pixel_w = 0
            pixel_h = 0

        exported = False
        try:
            export_area = _page_export_area(conn.app, doc)
            expflt = doc.ExportBitmap(
                path,
                _CDR_PNG,
                _CDR_CURRENT_PAGE,
                _CDR_RGB_COLOR_IMAGE,
                pixel_w,
                pixel_h,
                export_dpi,
                export_dpi,
                _CDR_NORMAL_ANTIALIASING,
                False,
                background_transparent,
                True,
                False,
                _CDR_COMPRESSION_NONE,
                None,
                export_area,
            )
            _finish_export_filter(expflt)
            exported = True
        except Exception:
            pass

        if not exported:
            doc.Export(path, _CDR_PNG, _CDR_CURRENT_PAGE, None, None)

        file_size = _verify_exported(path)
        return {
            "path": path,
            "dpi": export_dpi,
            "width_px": pixel_w,
            "height_px": pixel_h,
            "format": "png",
            "shapes_count": shapes_count,
            "file_size": file_size,
        }

    result = conn.safe_call(_export)
    if result["success"]:
        return ToolResult.ok(f"PNG 已导出: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "导出 PNG 失败"))


def export_preview_png(path: str, width: int = 800) -> ToolResult:
    """导出低分辨率 PNG 预览图，供 AI Agent 进行视觉检查。width 为像素宽度。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _export():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        _ensure_dir(path)
        shapes_count = _prepare_current_page_export(doc)
        page_w_mm, page_h_mm = _page_size_mm(doc)
        if page_w_mm > 0:
            export_dpi = int(width / (page_w_mm / 25.4))
        else:
            export_dpi = 72
        export_dpi = max(72, min(export_dpi, 300))
        if page_w_mm > 0 and page_h_mm > 0:
            pixel_w = max(1, int(page_w_mm / 25.4 * export_dpi))
            pixel_h = max(1, int(page_h_mm / 25.4 * export_dpi))
        else:
            pixel_w = width
            pixel_h = 0

        exported = False
        try:
            export_area = _page_export_area(conn.app, doc)
            expflt = doc.ExportBitmap(
                path,
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
            _finish_export_filter(expflt)
            exported = True
        except Exception:
            pass

        if not exported:
            doc.Export(path, _CDR_PNG, _CDR_CURRENT_PAGE, None, None)

        file_size = _verify_exported(path)
        return {
            "path": path,
            "width_px": width,
            "actual_width_px": pixel_w,
            "actual_height_px": pixel_h,
            "dpi": export_dpi,
            "shapes_count": shapes_count,
            "file_size": file_size,
        }

    result = conn.safe_call(_export)
    if result["success"]:
        return ToolResult.ok(f"预览图已导出: {path}", **result["result"])
    return ToolResult.fail(result.get("error", "导出预览图失败"))


def batch_export(pages: str, format: str, output_dir: str) -> ToolResult:
    """批量导出指定页面。pages 为 "1,2,3" 或 "1-5" 或 "all"，format 支持 pdf/dxf/png。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    format = format.lower()

    def _batch():
        doc = conn.app.ActiveDocument
        if not doc:
            raise RuntimeError("没有打开的文档")
        _ensure_dir(os.path.join(output_dir, "dummy.txt"))

        all_pages = list(doc.Pages)
        if pages.strip().lower() == "all":
            selected_pages = all_pages
        elif "-" in pages:
            start, end = [int(p.strip()) for p in pages.split("-")]
            selected_pages = [p for p in all_pages if start <= p.Index <= end]
        else:
            indices = [int(p.strip()) for p in pages.split(",") if p.strip()]
            selected_pages = []
            for p in all_pages:
                if p.Index in indices:
                    selected_pages.append(p)

        results = []
        doc_name = doc.FileName or "未命名"
        base = os.path.splitext(doc_name)[0] if doc_name else "output"

        for page in selected_pages:
            page.Activate()
            ext = format if format != "ai" else "ai"
            out_path = os.path.join(output_dir, f"{base}_p{page.Index}.{ext}")
            try:
                _prepare_current_page_export(doc)
                if format == "pdf":
                    try:
                        doc.PDFSettings.PublishRange = _PDF_CURRENT_PAGE
                        doc.PDFSettings.PageRange = str(page.Index)
                    except Exception:
                        pass
                    doc.PublishToPDF(out_path)
                elif format == "dxf":
                    try:
                        expflt = doc.ExportEx(out_path, _CDR_DXF, _CDR_CURRENT_PAGE, None, None)
                        expflt.BitmapType = 0
                        expflt.TextAsCurves = True
                        expflt.Version = 1
                        expflt.Units = 3
                        _finish_export_filter(expflt)
                    except Exception:
                        doc.Export(out_path, _CDR_DXF, _CDR_CURRENT_PAGE, None, None)
                elif format == "png":
                    page_w_mm, page_h_mm = _page_size_mm(doc)
                    if page_w_mm > 0 and page_h_mm > 0:
                        pixel_w = max(1, int(page_w_mm / 25.4 * 150))
                        pixel_h = max(1, int(page_h_mm / 25.4 * 150))
                    else:
                        pixel_w = 0
                        pixel_h = 0
                    export_area = _page_export_area(conn.app, doc)
                    expflt = doc.ExportBitmap(
                        out_path,
                        _CDR_PNG,
                        _CDR_CURRENT_PAGE,
                        _CDR_RGB_COLOR_IMAGE,
                        pixel_w,
                        pixel_h,
                        150,
                        150,
                        _CDR_NORMAL_ANTIALIASING,
                        False,
                        False,
                        True,
                        False,
                        _CDR_COMPRESSION_NONE,
                        None,
                        export_area,
                    )
                    _finish_export_filter(expflt)
                elif format == "svg":
                    doc.Export(out_path, _CDR_SVG, _CDR_CURRENT_PAGE, None, None)
                else:
                    raise ValueError(f"不支持的导出格式: {format}")
                _verify_exported(out_path)
                results.append({"page": page.Index, "path": out_path, "status": "success"})
            except Exception as e:
                results.append({"page": page.Index, "path": out_path, "status": "failed", "error": str(e)})

        return {"format": format, "total": len(results), "results": results}

    result = conn.safe_call(_batch)
    if result["success"]:
        r = result["result"]
        succeeded = sum(1 for x in r["results"] if x["status"] == "success")
        return ToolResult.ok(f"批量导出完成: {succeeded}/{r['total']} 成功", **r)
    return ToolResult.fail(result.get("error", "批量导出失败"))
