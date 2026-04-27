"""数据合并工具 — Excel 数据读取、批量数据合并、条码/QR 码生成"""

import os
import tempfile

from core.connection import get_connection
from core.models import ToolResult


def read_excel_data(path: str, sheet: int = 0, has_header: bool = True) -> ToolResult:
    """读取 Excel 数据源，返回行数据列表。sheet 为工作表索引（0-based）。"""
    try:
        import pandas as pd
    except ImportError:
        return ToolResult.fail("pandas 未安装，请执行 pip install pandas openpyxl xlrd")

    if not os.path.isfile(path):
        return ToolResult.fail(f"文件不存在: {path}")

    try:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".xlsx", ".xlsm"):
            df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
        elif ext == ".xls":
            df = pd.read_excel(path, sheet_name=sheet, engine="xlrd")
        elif ext == ".csv":
            df = pd.read_csv(path)
        else:
            return ToolResult.fail(f"不支持的文件格式: {ext}，支持 .xlsx/.xls/.csv")

        if has_header:
            records = df.to_dict(orient="records")
        else:
            df.columns = [f"col_{i}" for i in range(len(df.columns))]
            records = df.to_dict(orient="records")

        # 将 NaN 等转为 None
        clean_records = []
        for r in records:
            clean = {}
            for k, v in r.items():
                if pd.isna(v):
                    clean[k] = ""
                else:
                    clean[k] = str(v) if not isinstance(v, (int, float, bool, str)) else v
            clean_records.append(clean)

        return ToolResult.ok(
            f"读取成功: {len(clean_records)} 条记录",
            path=path,
            sheet=sheet,
            total=len(clean_records),
            records=clean_records,
            columns=list(df.columns),
        )
    except Exception as e:
        return ToolResult.fail(f"读取 Excel 失败: {e}")


def merge_record(template_path: str, data: dict, output_path: str) -> ToolResult:
    """单条数据合并：打开模板，按 data 字典替换占位符，保存到 output_path。data key 对应占位符名称。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _merge():
        doc = conn.app.OpenDocument(template_path)
        page = doc.ActivePage
        replaced = {}
        for key, value in data.items():
            try:
                shapes = page.Shapes
                for s in shapes:
                    try:
                        if s.Type == 3 and s.Name == key:  # cdrTextShape
                            s.Text.Story = str(value)
                            replaced[key] = str(value)[:30]
                            break
                    except Exception:
                        continue
            except Exception:
                pass
        dirpath = os.path.dirname(output_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        doc.SaveAs(output_path)
        return {"template": template_path, "output": output_path, "replaced": replaced}

    result = conn.safe_call(_merge)
    if result["success"]:
        cnt = len(result["result"]["replaced"])
        return ToolResult.ok(f"合并完成: {cnt} 处替换 → {output_path}", **result["result"])
    return ToolResult.fail(result.get("error", "数据合并失败"))


def batch_merge(template_path: str, data_path: str, output_dir: str, naming_pattern: str = "{room}") -> ToolResult:
    """批量数据合并：从 Excel 读取数据，逐条生成文件。naming_pattern 支持 {col_name} 占位符。"""
    from core.connection import get_connection

    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    # 先读取数据
    read_result = read_excel_data(data_path)
    if not read_result.success:
        return ToolResult.fail(read_result.error or "读取数据源失败")

    records = read_result.data["records"]
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for i, record in enumerate(records):
        try:
            filename = naming_pattern
            for key, value in record.items():
                filename = filename.replace("{" + key + "}", str(value))
            filename = filename.format(**record) if "{" in filename else filename
        except Exception:
            filename = f"output_{i:03d}"
        output_path = os.path.join(output_dir, f"{filename}.cdr")

        merge_result = merge_record(template_path, record, output_path)
        results.append({
            "index": i,
            "filename": f"{filename}.cdr",
            "success": merge_result.success,
            "error": merge_result.error if not merge_result.success else "",
        })

    succeeded = sum(1 for r in results if r["success"])
    return ToolResult.ok(
        f"批量合并完成: {succeeded}/{len(results)} 成功",
        output_dir=output_dir,
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
        results=results,
    )


def generate_barcode(barcode_type: str, data: str, x: float, y: float, width: float, height: float) -> ToolResult:
    """生成条码并导入到 CorelDRAW。type 支持 code128/ean13/code39。"""
    try:
        import barcode
        from barcode.writer import SVGWriter
    except ImportError:
        return ToolResult.fail("python-barcode 未安装，请执行 pip install python-barcode")

    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _generate():
        type_map = {"code128": "code128", "ean13": "ean13", "code39": "code39"}
        if barcode_type not in type_map:
            raise ValueError(f"不支持的条码类型: {barcode_type}，可选: {', '.join(type_map.keys())}")

        bc_class = barcode.get_barcode_class(barcode_type)
        bc = bc_class(data, writer=SVGWriter())

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            svg_path = tmp.name
        try:
            bc.save(svg_path.replace(".svg", ""))
            final_svg = svg_path.replace(".svg", "") + ".svg" if os.path.exists(svg_path.replace(".svg", "") + ".svg") else svg_path
            if os.path.exists(final_svg):
                doc = conn.app.ActiveDocument
                doc.Import(final_svg)
                page = doc.ActivePage
                shapes = page.Shapes
                if shapes.Count > 0:
                    last_shape = shapes.Last
                    last_shape.SetPosition(x, y)
                    last_shape.SetSize(width, height)
                    last_shape.Name = f"barcode_{barcode_type}_{data}"
                    return {
                        "shape_id": last_shape.StaticID,
                        "type": barcode_type,
                        "data": data,
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height,
                    }
            raise RuntimeError("条码 SVG 生成失败")
        finally:
            for f in [svg_path, svg_path.replace(".svg", "") + ".svg"]:
                try:
                    os.remove(f)
                except Exception:
                    pass

    result = conn.safe_call(_generate)
    if result["success"]:
        return ToolResult.ok(f"条码已生成: {barcode_type} - {data}", **result["result"])
    return ToolResult.fail(result.get("error", "生成条码失败"))


def generate_qrcode(data: str, x: float, y: float, size: float) -> ToolResult:
    """生成 QR Code 并导入到 CorelDRAW。"""
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return ToolResult.fail("qrcode 未安装，请执行 pip install qrcode[pil]")

    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _generate():
        factory = qrcode.image.svg.SvgImage
        qr = qrcode.QRCode(version=None, box_size=10, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(image_factory=factory)

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            svg_path = tmp.name
        try:
            img.save(svg_path)
            doc = conn.app.ActiveDocument
            doc.Import(svg_path)
            page = doc.ActivePage
            shapes = page.Shapes
            if shapes.Count > 0:
                last_shape = shapes.Last
                last_shape.SetPosition(x, y)
                last_shape.SetSize(size, size)
                last_shape.Name = f"qrcode_{data[:20]}"
                return {
                    "shape_id": last_shape.StaticID,
                    "type": "qr",
                    "data": data,
                    "x": x,
                    "y": y,
                    "size": size,
                }
            raise RuntimeError("QR Code 导入失败")
        finally:
            try:
                os.remove(svg_path)
            except Exception:
                pass

    result = conn.safe_call(_generate)
    if result["success"]:
        return ToolResult.ok(f"QR Code 已生成: {data[:30]}...", **result["result"])
    return ToolResult.fail(result.get("error", "生成 QR Code 失败"))
