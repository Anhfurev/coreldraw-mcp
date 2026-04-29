"""导出工具 — PDF/DXF/AI/SVG/PNG 导出，预览 PNG 及批量导出"""

import os

from core.connection import get_connection
from core.models import ToolResult

# 导出滤镜常量（CorelDRAW COM 滤镜编号）
_CDR_DXF = 86
_CDR_AI = 772
_CDR_SVG = 2200
_CDR_PNG = 776
_CDR_JPEG = 774

_DXF_VERSION = {"R12": 0, "R14": 1, "R2000": 3, "R2004": 4}


def _ensure_dir(path: str) -> None:
    """确保输出目录存在"""
    dirpath = os.path.dirname(path)
    if dirpath and not os.path.isdir(dirpath):
        os.makedirs(dirpath, exist_ok=True)


def _page_size_mm(doc):
    """获取页面尺寸（mm）"""
    try:
        doc.Unit = 2  # cdrMillimeter
        page = doc.ActivePage
        return page.SizeWidth, page.SizeHeight
    except Exception:
        return 0, 0


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
        try:
            doc.PDFSettings.ColorMode = 1  # cdrPDFCMYK
            doc.PDFSettings.BleedingLimit = bleed
            doc.PDFSettings.PrintCropMarks = crop_marks
            doc.PDFSettings.MultiPage = multi_page
        except Exception:
            pass
        doc.PublishToPDF(path)
        return {"path": path, "color_profile": color_profile, "bleed": bleed, "crop_marks": crop_marks}

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
        # X6 doesn't have CreateStructExportOptions(); call ExportEx directly
        expflt = doc.ExportEx(path, _CDR_DXF, 0)
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
        expflt.Finish()
        return {"path": path, "version": version, "text_as_curves": True}

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
        doc.Export(path, _CDR_AI, 0)
        return {"path": path, "format": "ai"}

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
        doc.Export(path, _CDR_SVG, 0)
        return {"path": path, "format": "svg"}

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
        page_w_mm, page_h_mm = _page_size_mm(doc)
        if width > 0 and page_w_mm > 0:
            export_dpi = int(width / (page_w_mm / 25.4))
        else:
            export_dpi = dpi
        export_dpi = max(72, export_dpi)

        exported = False
        try:
            rect = conn.app.CreateRect()
            rect.Height = page_h_mm if page_h_mm > 0 else 100
            rect.Width = page_w_mm if page_w_mm > 0 else 100
            palette_opts = conn.app.CreateStructPaletteOptions()
            doc.ExportBitmap(path, _CDR_PNG, export_dpi, export_dpi, 5, 1000, 1000, 1,
                             not background_transparent, False, False, False, 8, palette_opts, rect)
            exported = True
        except Exception:
            pass

        if not exported:
            # X6 fallback: ExportEx returns a filter object; set DPI then Finish()
            expflt = doc.ExportEx(path, _CDR_PNG, 0)
            for attr, val in [("ResolutionX", export_dpi), ("ResolutionY", export_dpi),
                               ("AntiAlias", True), ("TransparentBackground", background_transparent)]:
                try:
                    setattr(expflt, attr, val)
                except Exception:
                    pass
            expflt.Finish()

        return {"path": path, "dpi": export_dpi, "format": "png"}

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
        page_w_mm, page_h_mm = _page_size_mm(doc)
        if page_w_mm > 0:
            export_dpi = int(width / (page_w_mm / 25.4))
        else:
            export_dpi = 72
        export_dpi = max(72, min(export_dpi, 300))

        exported = False
        try:
            rect = conn.app.CreateRect()
            rect.Height = page_h_mm if page_h_mm > 0 else 100
            rect.Width = page_w_mm if page_w_mm > 0 else 100
            palette_opts = conn.app.CreateStructPaletteOptions()
            doc.ExportBitmap(path, _CDR_PNG, export_dpi, export_dpi, 5, 1000, 1000, 1,
                             True, False, False, False, 8, palette_opts, rect)
            exported = True
        except Exception:
            pass

        if not exported:
            # X6 fallback: ExportEx + Finish
            expflt = doc.ExportEx(path, _CDR_PNG, 0)
            for attr, val in [("ResolutionX", export_dpi), ("ResolutionY", export_dpi),
                               ("AntiAlias", True)]:
                try:
                    setattr(expflt, attr, val)
                except Exception:
                    pass
            expflt.Finish()

        try:
            file_size = os.path.getsize(path)
        except Exception:
            file_size = 0
        return {"path": path, "width_px": width, "dpi": export_dpi, "file_size": file_size}

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
                if format == "pdf":
                    doc.PublishToPDF(out_path)
                elif format == "dxf":
                    expopt = conn.app.CreateStructExportOptions()
                    expflt = doc.ExportEx(out_path, _CDR_DXF, 0, expopt)
                    expflt.BitmapType = 0
                    expflt.TextAsCurves = True
                    expflt.Version = 1
                    expflt.Units = 3
                    expflt.Finish()
                elif format == "png":
                    doc.Export(out_path, _CDR_PNG, 0)
                elif format == "svg":
                    doc.Export(out_path, _CDR_SVG, 0)
                else:
                    raise ValueError(f"不支持的导出格式: {format}")
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
