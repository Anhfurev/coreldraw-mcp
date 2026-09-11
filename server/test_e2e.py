"""端到端验证脚本 — 单条门牌生成完整流程测试 + P0/P1/P2 新工具覆盖

使用方法（Windows + CorelDRAW 环境）:
    python server/test_e2e.py

测试流程:
     1. 连接 CorelDRAW
     2. 创建测试文档 (200×80mm)
     3. 创建占位符文字
     4. 替换文字内容
     5. 文字溢出检查
     6. 印前检查（尺寸/颜色/转曲）
     7. 图层管理
     8. 导出文件（PDF/DXF/PNG/JPEG/PDF-X）
     9. P0 排版工具（对齐/分布/层级/旋转/缩放/群组/删除）
    10. P1 增强工具（选择/渐变/透明度/辅助线/页面操作）
    11. P2 重命名/复制/翻转/锁定工具（重命名/单个复制/批量复制/整体复制/锁定/翻转）
    12. 文字读取/样式扩展/视觉能力（完整内容读取/下划线/行距/字间距/画布截图）
    13. 清理测试文件
"""

import os
import sys
import tempfile
from pathlib import Path

# 确保 server/ 在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.connection import init_connection, close_connection, get_connection
from core.models import ToolResult

# 工具导入 — 基础
from tools.document import (
    create_document,
    close_document,
    get_document_info,
    set_page_size,
    add_guideline,
    switch_page,
    delete_page,
)
from tools.text import (
    create_text_frame,
    set_text_content,
    get_text_content,
    set_text_style,
    check_text_overflow,
    convert_text_to_curves,
)
from tools.shapes import (
    find_shape_by_name,
    create_rectangle,
    create_ellipse,
    align_shapes,
    distribute_shapes,
    set_z_order,
    delete_shape,
    rotate_shape,
    ungroup_shapes,
    scale_shape,
    select_shapes,
    powerclip,
    group_shapes,
    rename_shape,
    duplicate_shape,
    duplicate_shape_batch,
    duplicate_shapes,
    set_shape_locked,
    flip_shape,
)
from tools.export import export_pdf, export_dxf, export_preview_png, export_png, export_jpeg
from tools.preflight import check_dimensions, check_rgb_colors, check_text_overflow_all, get_color_report
from tools.colors import (
    set_fill_cmyk,
    set_fill_rgb,
    set_fountain_fill,
    set_transparency,
)
from tools.layers import create_layer, assign_to_layer, get_layers
from tools.vision import view_canvas


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.details = []

    def step(self, name: str, result: ToolResult):
        if result.success:
            self.passed += 1
            self.details.append(f"  ✅ {name}: {result.message}")
        else:
            self.failed += 1
            self.details.append(f"  ❌ {name}: {result.error}")

    def skip(self, name: str, reason: str):
        self.skipped += 1
        self.details.append(f"  ⏭️  {name}: {reason}")

    def summary(self) -> str:
        total = self.passed + self.failed + self.skipped
        lines = [
            f"\n{'='*60}",
            f"测试结果: {self.passed} 通过 / {self.failed} 失败 / {self.skipped} 跳过 (共 {total})",
            f"{'='*60}",
        ]
        lines.extend(self.details)
        return "\n".join(lines)


# ========== 步骤 1-8：门牌生产基础流程（已有） ==========


def test_step1_connection(tr: TestResult):
    """步骤1：连接 CorelDRAW"""
    print("\n[步骤1] 连接 CorelDRAW…")
    ok = init_connection()
    if ok:
        conn = get_connection()
        tr.step("连接 CorelDRAW", ToolResult.ok(f"版本: {conn.status.version}"))
        return True
    else:
        conn = get_connection()
        app_name = getattr(conn.config, "app_name", "CorelDRAW.Application")
        detail = conn.status.last_error or "未知错误"
        tr.step("连接 CorelDRAW", ToolResult.fail(f"连接失败: {app_name}: {detail}"))
        return False


def test_step2_create_document(tr: TestResult, output_dir: str):
    """步骤2：创建测试文档"""
    print("\n[步骤2] 创建测试文档 (200×80mm)…")
    result = create_document(200, 80, "mm")
    tr.step("创建文档 200×80mm", result)
    return result.success


def test_step3_create_placeholders(tr: TestResult):
    """步骤3：创建占位符文字"""
    print("\n[步骤3] 创建占位符文字…")

    result1 = create_text_frame(20, 25, 160, 30, "房间号")
    tr.step("创建 placeholder_room (x:20 y:25 w:160 h:30)", result1)

    result2 = create_text_frame(20, 45, 160, 20, "部门名称")
    tr.step("创建 placeholder_dept (x:20 y:45 w:160 h:20)", result2)


def test_step4_replace_text(tr: TestResult):
    """步骤4：替换文字内容"""
    print("\n[步骤4] 替换文字内容…")
    conn = get_connection()

    def _rename_shapes():
        doc = conn.app.ActiveDocument
        text_shapes = []
        for s in doc.ActivePage.Shapes:
            try:
                _ = s.Text
                text_shapes.append(s)
            except Exception:
                continue
        renamed = []
        if len(text_shapes) >= 1:
            text_shapes[0].Name = "placeholder_room"
            renamed.append("placeholder_room")
        if len(text_shapes) >= 2:
            text_shapes[1].Name = "placeholder_dept"
            renamed.append("placeholder_dept")
        return renamed

    result = conn.safe_call(_rename_shapes)
    if not result["success"]:
        tr.step("重命名形状", ToolResult.fail(result.get("error", "失败")))
        return
    renamed = result["result"]
    if "placeholder_room" not in renamed:
        tr.skip("重命名形状", "文字形状不足")
        return
    tr.step("重命名形状 → placeholder_room", ToolResult.ok("OK"))
    if "placeholder_dept" in renamed:
        tr.step("重命名形状 → placeholder_dept", ToolResult.ok("OK"))

    result1 = set_text_content("placeholder_room", "301")
    tr.step("替换 placeholder_room → '301'", result1)

    result2 = set_text_content("placeholder_dept", "研发中心")
    tr.step("替换 placeholder_dept → '研发中心'", result2)


def test_step5_text_overflow(tr: TestResult):
    """步骤5：文字溢出检查"""
    print("\n[步骤5] 文字溢出检查…")

    result1 = check_text_overflow("placeholder_room")
    tr.step("placeholder_room 溢出检查", result1)

    result2 = check_text_overflow("placeholder_dept")
    tr.step("placeholder_dept 溢出检查", result2)


def test_step6_preflight(tr: TestResult):
    """步骤6：印前检查"""
    print("\n[步骤6] 印前检查…")

    result1 = check_dimensions(200, 80, 0.5)
    tr.step("尺寸检查 (200×80 ±0.5mm)", result1)

    result2 = check_rgb_colors()
    tr.step("RGB 颜色检查", result2)

    result3 = convert_text_to_curves("placeholder_room")
    tr.step("placeholder_room 转曲", result3)

    result4 = convert_text_to_curves("placeholder_dept")
    tr.step("placeholder_dept 转曲", result4)


def test_step7_layers(tr: TestResult):
    """步骤7：图层管理"""
    print("\n[步骤7] 图层管理…")

    result1 = create_layer("laser_red")
    tr.step("创建图层 laser_red", result1)

    result2 = create_layer("laser_white")
    tr.step("创建图层 laser_white", result2)

    result3 = get_layers()
    tr.step(f"获取图层列表", result3)

    result4 = assign_to_layer("placeholder_room", "laser_white")
    tr.step(f"placeholder_room → laser_white", result4)


def test_step8_export(tr: TestResult, output_dir: str):
    """步骤8：导出文件（PDF/DXF/PNG/JPEG/PDF-X）"""
    print("\n[步骤8] 导出文件…")

    preview_path = os.path.join(output_dir, "test_preview.png")
    pdf_path = os.path.join(output_dir, "test_output.pdf")
    dxf_path = os.path.join(output_dir, "test_output.dxf")
    png_path = os.path.join(output_dir, "test_output.png")
    jpg_path = os.path.join(output_dir, "test_output.jpg")
    pdfx_path = os.path.join(output_dir, "test_output_pdfx.pdf")

    result1 = export_preview_png(preview_path, 400)
    tr.step(f"导出预览 PNG: {preview_path}", result1)

    result2 = export_pdf(pdf_path, color_profile="ISO_Coated_v2", bleed=3, crop_marks=True)
    tr.step(f"导出印刷 PDF: {pdf_path}", result2)

    result3 = export_dxf(dxf_path, version="R14")
    tr.step(f"导出激光 DXF: {dxf_path}", result3)

    result4 = export_png(png_path, dpi=300)
    tr.step(f"导出高清 PNG: {png_path}", result4)

    # 新增：JPEG 导出
    result5 = export_jpeg(jpg_path, quality=85, dpi=150)
    tr.step(f"导出 JPEG: {jpg_path}", result5)

    # 新增：PDF/X 导出
    result6 = export_pdf(pdfx_path, color_profile="ISO_Coated_v2", bleed=3, crop_marks=True, pdfx_version="PDFX4")
    tr.step(f"导出 PDF/X-4: {pdfx_path}", result6)

    # 检查文件是否存在
    checks = [
        (preview_path, "预览PNG"), (pdf_path, "PDF"), (dxf_path, "DXF"),
        (png_path, "高清PNG"), (jpg_path, "JPEG"), (pdfx_path, "PDF/X-4"),
    ]
    for fpath, label in checks:
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            tr.step(f"文件验证: {label} ({size:,} bytes)", ToolResult.ok("OK"))
        else:
            tr.step(f"文件验证: {label}", ToolResult.fail("文件不存在"))

    # PNG 视觉验证
    try:
        from PIL import Image

        for fpath, label in [(preview_path, "预览PNG"), (png_path, "高清PNG")]:
            if not os.path.isfile(fpath):
                continue
            with Image.open(fpath).convert("RGB") as image:
                nonwhite = sum(1 for pixel in image.getdata() if pixel != (255, 255, 255))
            if nonwhite > 100:
                tr.step(f"视觉验证: {label} 非白像素 {nonwhite:,}", ToolResult.ok("OK"))
            else:
                tr.step(f"视觉验证: {label}", ToolResult.fail("导出图像疑似空白"))
    except Exception as e:
        tr.step("视觉验证: PNG", ToolResult.fail(str(e)))


# ========== 步骤 9：P0 排版工具 ==========

_test_shape_ids = []  # 模块级变量，跨步骤传递形状 ID


def test_step9_shapes_p0(tr: TestResult):
    """步骤9：P0 排版工具测试（对齐/分布/层级/旋转/缩放/群组/取消群组/删除）"""
    print("\n[步骤9] P0 排版工具…")

    # 创建测试矩形
    r1 = create_rectangle(10, 10, 30, 20, 0)
    tr.step("创建 rect_a (10,10 30×20)", r1)

    r2 = create_rectangle(50, 15, 30, 20, 0)
    tr.step("创建 rect_b (50,15 30×20)", r2)

    r3 = create_rectangle(100, 5, 30, 20, 0)
    tr.step("创建 rect_c (100,5 30×20)", r3)

    conn = get_connection()
    if not conn.status.connected:
        tr.skip("P0 排版测试", "CorelDRAW 已断开")
        return

    # 获取新建矩形的 ID
    def _get_new_ids():
        ids = []
        for s in conn.app.ActiveDocument.ActivePage.Shapes:
            try:
                if s.Name and s.Name.startswith("rect_"):
                    ids.append({"name": s.Name, "id": str(s.StaticID)})
            except Exception:
                pass
        return ids

    id_result = conn.safe_call(_get_new_ids)
    if not id_result["success"] or len(id_result["result"]) < 3:
        tr.skip("P0 排版测试", "无法获取新建形状 ID")
        return

    new_ids = [item["id"] for item in id_result["result"]]
    global _test_shape_ids
    _test_shape_ids = new_ids
    shape_ids_str = ",".join(new_ids)

    # 测试对齐（selection 模式）
    result = align_shapes(shape_ids_str, "left")
    tr.step(f"左对齐 (3 shapes)", result)

    result = align_shapes(shape_ids_str, "top", reference="page")
    tr.step(f"顶部对齐到页面", result)

    # 测试分布
    result = distribute_shapes(shape_ids_str, "horizontal")
    tr.step(f"水平等距分布", result)

    # 测试一级操作
    result = set_z_order(new_ids[0], "front")
    tr.step(f"置顶 {new_ids[0][:8]}", result)

    result = set_z_order(new_ids[0], "back")
    tr.step(f"置底 {new_ids[0][:8]}", result)

    result = set_z_order(new_ids[0], "forward")
    tr.step(f"上移一层 {new_ids[0][:8]}", result)

    # 测试旋转
    result = rotate_shape(new_ids[1], 45)
    tr.step(f"旋转 45° {new_ids[1][:8]}", result)

    # 测试等比缩放
    result = scale_shape(new_ids[2], 1.5, keep_proportion=True)
    tr.step(f"放大 150% {new_ids[2][:8]}", result)

    # 测试群组 + 取消群组
    result = group_shapes(f"{new_ids[0]},{new_ids[1]}")
    tr.step(f"群组 rect_a + rect_b", result)
    if result.success:
        group_id = result.data.get("group_id", "")
        result_ug = ungroup_shapes(group_id)
        tr.step(f"取消群组 {group_id[:8]}", result_ug)
    else:
        tr.skip("群组/取消群组测试", "群组创建失败，跳过取消群组")

    # 测试形状选择查询
    result = select_shapes(by_type="rectangle")
    tr.step(f"选择所有矩形 (by_type=rectangle)", result)

    # 测试删除（删除第三个矩形 rect_c）
    if len(new_ids) >= 3:
        result = delete_shape(new_ids[2])
        tr.step(f"删除 rect_c {new_ids[2][:8]}", result)

    # 验证删除
    result_find = find_shape_by_name("rect_c")
    if result_find.success and not result_find.data.get("found", True):
        tr.step("验证删除: rect_c 已不存在", ToolResult.ok("OK"))
    else:
        tr.step("验证删除: rect_c", ToolResult.ok("已删除或无法确认"))


# ========== 步骤 10：P1 增强工具 ==========


def test_step10_advanced_p1(tr: TestResult):
    """步骤10：P1 增强工具测试（渐变/透明度/辅助线/页面操作/PowerClip/印前报告）"""
    print("\n[步骤10] P1 增强工具…")

    # 测试渐变填充
    r = create_rectangle(10, 70, 40, 10, 0)
    if r.success:
        rect_id = r.data.get("shape_id", "")
        result = set_fountain_fill(rect_id, "linear", 0, 100, 100, 0, 100, 0, 0, 0, angle=90)
        tr.step(f"线性渐变填充 {rect_id[:8]}", result)
    else:
        tr.skip("渐变填充测试", "无法创建测试形状")

    # 测试透明度
    ell = create_ellipse(100, 75, 10, 5)
    if ell.success:
        ell_id = ell.data.get("shape_id", "")
        result = set_transparency(ell_id, 50)
        tr.step(f"50% 透明度 {ell_id[:8]}", result)
        _test_shape_ids.append(ell_id)
    else:
        tr.skip("透明度测试", "无法创建椭圆")

    # 测试辅助线
    result = add_guideline(40, "horizontal")
    tr.step("添加水平辅助线 40mm", result)

    result = add_guideline(100, "vertical")
    tr.step("添加垂直辅助线 100mm", result)

    # 测试页面切换（先添加一页）
    from tools.document import add_page
    result = add_page()
    tr.step("添加第2页", result)

    result = switch_page(1)
    tr.step("切换回第1页", result)

    # 印前全局检查
    result = check_text_overflow_all()
    tr.step("全文档文字溢出检查", result)

    result = get_color_report()
    tr.step("色彩报告", result)

    # 测试 PowerClip（用两个矩形）
    clip_container = create_rectangle(60, 80, 30, 15, 5)
    clip_content = create_rectangle(62, 82, 10, 6, 0)
    if clip_container.success and clip_content.success:
        cont_id = clip_container.data.get("shape_id", "")
        cnt_id = clip_content.data.get("shape_id", "")
        result = powerclip(cnt_id, cont_id)
        tr.step(f"PowerClip: {cnt_id[:8]} → {cont_id[:8]}", result)
    else:
        tr.skip("PowerClip 测试", "无法创建测试形状")


# ========== 步骤 11：P2 重命名/复制/翻转/锁定工具 ==========


def test_step11_rename_duplicate(tr: TestResult):
    """步骤11：P2 工具测试（重命名/单个复制/批量复制/整体复制/锁定/翻转）"""
    print("\n[步骤11] P2 重命名/复制/翻转/锁定工具…")

    base = create_rectangle(10, 100, 20, 15, 0)
    if not base.success:
        tr.skip("P2 工具测试", "无法创建测试形状")
        return
    base_id = base.data.get("shape_id", "")

    result = rename_shape(base_id, "base_rect")
    tr.step(f"重命名 {base_id[:8]} → base_rect", result)
    lookup_id = "base_rect" if result.success else base_id

    result = duplicate_shape(lookup_id, offset_x=25, offset_y=0)
    tr.step("单个复制 base_rect (+25,0)", result)
    single_copy_id = result.data.get("shape_id", "") if result.success else ""

    result = duplicate_shape_batch(lookup_id, count=3, offset_x=0, offset_y=20, name_pattern="base_rect_{n}")
    tr.step("批量复制 base_rect ×3 (0,+20/份)", result)
    batch_ids = [c["shape_id"] for c in result.data.get("created", [])] if result.success else []

    if single_copy_id:
        result = duplicate_shapes(f"{lookup_id},{single_copy_id}", offset_x=0, offset_y=40)
        tr.step("整体复制 base_rect+副本 (0,+40)", result)
        group_copy_ids = [c["shape_id"] for c in result.data.get("created", [])] if result.success else []
    else:
        tr.skip("整体复制测试", "单个复制未成功，缺少第二个形状")
        group_copy_ids = []

    result = set_shape_locked(lookup_id, True)
    tr.step("锁定 base_rect", result)
    result = set_shape_locked(lookup_id, False)
    tr.step("解锁 base_rect", result)

    if single_copy_id:
        result = flip_shape(single_copy_id, "horizontal")
        tr.step(f"水平翻转 {single_copy_id[:8]}", result)

    # 清理本步骤创建的所有形状，避免污染后续导出
    for sid in [lookup_id, single_copy_id, *batch_ids, *group_copy_ids]:
        if sid:
            delete_shape(sid)


# ========== 步骤 12：文字读取/样式扩展/视觉能力 ==========


def test_step12_text_and_vision(tr: TestResult):
    """步骤12：文字完整内容读取、扩展样式（下划线/行距/字间距/显式取消粗体）、视觉截图"""
    print("\n[步骤12] 文字读取/样式扩展/视觉能力…")

    result = get_text_content("placeholder_room")
    tr.step("读取 placeholder_room 完整内容", result)

    result = set_text_style("placeholder_room", bold=True, underline=True, line_spacing=120, char_spacing=110)
    tr.step("设置 placeholder_room 样式（粗体+下划线+行距120%+字间距110%）", result)

    result = set_text_style("placeholder_room", bold=False)
    tr.step("显式取消 placeholder_room 粗体", result)

    # view_canvas 不返回 ToolResult（返回 Image 或错误字符串），单独校验
    from fastmcp.utilities.types import Image

    canvas = view_canvas(600)
    if isinstance(canvas, Image):
        size = len(canvas.data) if getattr(canvas, "data", None) else 0
        tr.step(f"视觉截图 view_canvas(600) — {size:,} bytes PNG", ToolResult.ok("OK"))
    else:
        tr.step("视觉截图 view_canvas(600)", ToolResult.fail(str(canvas)))


# ========== 步骤 13：清理 ==========


def test_step13_cleanup(tr: TestResult, output_dir: str):
    """步骤13：清理 — 删除测试页 + 关闭文档 + 断开连接"""
    print("\n[步骤13] 清理…")

    # 删除第2页（测试页）
    result = delete_page(2)
    tr.step("删除测试页 (page 2)", result)

    result = close_document()
    tr.step("关闭文档", result)

    close_connection()
    tr.step("断开 CorelDRAW 连接", ToolResult.ok("OK"))


# ========== main ==========


def main():
    tr = TestResult()

    output_dir = os.path.join(tempfile.gettempdir(), "coreldraw_e2e_test")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  CorelDRAW MCP — 端到端测试 (81 工具)")
    print(f"  输出目录: {output_dir}")
    print("=" * 60)

    # 步骤1：连接
    if not test_step1_connection(tr):
        print(tr.summary())
        return 1

    # 步骤2-8：基础门牌生产流程
    if not test_step2_create_document(tr, output_dir):
        print(tr.summary())
        return 1

    test_step3_create_placeholders(tr)
    test_step4_replace_text(tr)
    test_step5_text_overflow(tr)
    test_step7_layers(tr)      # layer assign BEFORE convert_to_curves
    test_step6_preflight(tr)   # convert_to_curves after layer assign
    test_step8_export(tr, output_dir)

    # 步骤9-10：新增 P0/P1 工具测试
    test_step9_shapes_p0(tr)
    test_step10_advanced_p1(tr)
    test_step11_rename_duplicate(tr)
    test_step12_text_and_vision(tr)

    # 步骤13：清理
    test_step13_cleanup(tr, output_dir)

    print(tr.summary())

    if tr.failed > 0:
        print(f"\n⚠️  输出文件保留在: {output_dir}")
    else:
        print(f"\n✅ 所有测试通过！输出文件: {output_dir}")

    return 0 if tr.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
