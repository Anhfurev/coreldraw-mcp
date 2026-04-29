"""工程图工具 — 标题栏填充、工程图框架组装"""

import os

from core.connection import get_connection
from core.models import ToolResult

_CDR_TEXT_SHAPE = 3


def populate_title_block(
    template_path: str,
    project_name: str = "",
    order_no: str = "",
    part_no: str = "",
    designer: str = "",
    material: str = "",
    finish: str = "",
    scale: str = "1:1",
    sheet_no: str = "",
    revision: str = "A",
    output_path: str = "",
) -> ToolResult:
    """填充工程图标题栏。打开工程图 CDR 模板，按参数替换标题栏各字段文字形状，
    保存到 output_path（省略则覆盖原文件）。形状名称须与字段名一致（如 title_project_name）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    if not os.path.isfile(template_path):
        return ToolResult.fail(f"模板文件不存在: {template_path}")

    save_path = output_path or template_path

    fields = {
        "title_project_name": project_name,
        "title_order_no": order_no,
        "title_part_no": part_no,
        "title_designer": designer,
        "title_material": material,
        "title_finish": finish,
        "title_scale": scale,
        "title_sheet_no": sheet_no,
        "title_revision": revision,
    }
    # 只写非空字段
    fields = {k: v for k, v in fields.items() if v}

    def _populate():
        doc = conn.app.OpenDocument(template_path)
        page = doc.ActivePage
        replaced = {}
        skipped = []

        for s in page.Shapes:
            try:
                if s.Type == _CDR_TEXT_SHAPE and s.Name in fields:
                    s.Text.Story = str(fields[s.Name])
                    replaced[s.Name] = str(fields[s.Name])
            except Exception:
                skipped.append(s.Name)

        # 遍历所有页（工程图可能多页）
        for pg in doc.Pages:
            if pg.Index == page.Index:
                continue
            try:
                for s in pg.Shapes:
                    if s.Type == _CDR_TEXT_SHAPE and s.Name in fields and s.Name not in replaced:
                        try:
                            s.Text.Story = str(fields[s.Name])
                            replaced[s.Name] = str(fields[s.Name])
                        except Exception:
                            skipped.append(s.Name)
            except Exception:
                pass

        dirpath = os.path.dirname(save_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        doc.SaveAs(save_path)
        doc.Close()
        not_found = [k for k in fields if k not in replaced]
        return {
            "output": save_path,
            "replaced": replaced,
            "not_found": not_found,
            "skipped": skipped,
        }

    result = conn.safe_call(_populate)
    if result["success"]:
        r = result["result"]
        cnt = len(r["replaced"])
        msg = f"标题栏填充完成: {cnt} 个字段 → {save_path}"
        if r["not_found"]:
            msg += f"，{len(r['not_found'])} 个字段未找到形状: {r['not_found']}"
        return ToolResult.ok(msg, **r)
    return ToolResult.fail(result.get("error", "标题栏填充失败"))


def assemble_engineering_drawing(
    design_path: str,
    frame_template_path: str,
    output_path: str,
    title_block_fields: dict = None,
) -> ToolResult:
    """将设计文件嵌入工程图框架模板，生成完整工程图 CDR 文件。
    先填充标题栏，再导入设计文件内容到框架的 design_zone 图层/形状区域。
    title_block_fields 为标题栏字段字典，键名与 populate_title_block 参数一致。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    if not os.path.isfile(design_path):
        return ToolResult.fail(f"设计文件不存在: {design_path}")
    if not os.path.isfile(frame_template_path):
        return ToolResult.fail(f"工程图框架模板不存在: {frame_template_path}")

    fields = title_block_fields or {}

    def _assemble():
        # 打开工程图框架
        doc = conn.app.OpenDocument(frame_template_path)
        page = doc.ActivePage

        # 填充标题栏
        replaced_fields = {}
        field_map = {
            "title_project_name": fields.get("project_name", ""),
            "title_order_no": fields.get("order_no", ""),
            "title_part_no": fields.get("part_no", ""),
            "title_designer": fields.get("designer", ""),
            "title_material": fields.get("material", ""),
            "title_finish": fields.get("finish", ""),
            "title_scale": fields.get("scale", "1:1"),
            "title_sheet_no": fields.get("sheet_no", ""),
            "title_revision": fields.get("revision", "A"),
        }
        for s in page.Shapes:
            try:
                if s.Type == _CDR_TEXT_SHAPE and s.Name in field_map and field_map[s.Name]:
                    s.Text.Story = str(field_map[s.Name])
                    replaced_fields[s.Name] = field_map[s.Name]
            except Exception:
                pass

        # 导入设计文件到框架
        doc.Import(design_path)

        dirpath = os.path.dirname(output_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        doc.SaveAs(output_path)
        doc.Close()
        return {
            "output": output_path,
            "design_imported": design_path,
            "frame_used": frame_template_path,
            "title_block_filled": replaced_fields,
        }

    result = conn.safe_call(_assemble)
    if result["success"]:
        r = result["result"]
        return ToolResult.ok(f"工程图已组装: {output_path}", **r)
    return ToolResult.fail(result.get("error", "工程图组装失败"))
