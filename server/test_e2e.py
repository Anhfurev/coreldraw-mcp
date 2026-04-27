"""端到端验证脚本 — 单条门牌生成完整流程测试

使用方法（Windows + CorelDRAW 环境）:
    python server/test_e2e.py

测试流程:
    1. 创建测试文档 (200×80mm)
    2. 创建占位符文字
    3. 替换文字内容
    4. 文字溢出检查
    5. 印前检查（尺寸/颜色）
    6. 导出预览 PNG
    7. 导出印刷 PDF
    8. 导出激光 DXF
    9. 清理测试文件
"""

import os
import sys
import tempfile
from pathlib import Path

# 确保 server/ 在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.connection import init_connection, close_connection, get_connection
from core.models import ToolResult

# 工具导入
from tools.document import (
    create_document,
    close_document,
    get_document_info,
    set_page_size,
)
from tools.text import (
    create_text_frame,
    set_text_content,
    check_text_overflow,
    set_text_style,
    convert_text_to_curves,
)
from tools.shapes import find_shape_by_name
from tools.export import export_pdf, export_dxf, export_preview_png, export_png
from tools.preflight import check_dimensions, check_rgb_colors
from tools.colors import set_fill_cmyk, set_fill_rgb
from tools.layers import create_layer, assign_to_layer, get_layers


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


def test_step1_connection(tr: TestResult):
    """步骤1：连接 CorelDRAW"""
    print("\n[步骤1] 连接 CorelDRAW…")
    ok = init_connection()
    if ok:
        conn = get_connection()
        tr.step("连接 CorelDRAW", ToolResult.ok(f"版本: {conn.status.version}"))
        return True
    else:
        tr.step("连接 CorelDRAW", ToolResult.fail("连接失败，请确认 CorelDRAW 已启动"))
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
    doc = conn.app.ActiveDocument
    shapes = doc.ActivePage.Shapes

    # 找到第一个文字形状（room）并重命名
    text_shapes = []
    for s in shapes:
        if s.Type == 3:  # cdrTextShape
            text_shapes.append(s)

    if len(text_shapes) >= 1:
        text_shapes[0].Name = "placeholder_room"
        tr.step("重命名形状 → placeholder_room", ToolResult.ok("OK"))
    else:
        tr.skip("重命名形状", "文字形状不足")
        return

    if len(text_shapes) >= 2:
        text_shapes[1].Name = "placeholder_dept"
        tr.step("重命名形状 → placeholder_dept", ToolResult.ok("OK"))

    # 替换内容
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


def test_step7_export(tr: TestResult, output_dir: str):
    """步骤7：导出文件"""
    print("\n[步骤7] 导出文件…")

    preview_path = os.path.join(output_dir, "test_preview.png")
    pdf_path = os.path.join(output_dir, "test_output.pdf")
    dxf_path = os.path.join(output_dir, "test_output.dxf")
    png_path = os.path.join(output_dir, "test_output.png")

    result1 = export_preview_png(preview_path, 400)
    tr.step(f"导出预览 PNG: {preview_path}", result1)

    result2 = export_pdf(pdf_path, color_profile="ISO_Coated_v2", bleed=3, crop_marks=True)
    tr.step(f"导出印刷 PDF: {pdf_path}", result2)

    result3 = export_dxf(dxf_path, version="R14")
    tr.step(f"导出激光 DXF: {dxf_path}", result3)

    result4 = export_png(png_path, dpi=300)
    tr.step(f"导出高清 PNG: {png_path}", result4)

    # 检查文件是否存在
    for fpath, label in [(preview_path, "预览PNG"), (pdf_path, "PDF"), (dxf_path, "DXF"), (png_path, "高清PNG")]:
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            tr.step(f"文件验证: {label} ({size:,} bytes)", ToolResult.ok("OK"))
        else:
            tr.step(f"文件验证: {label}", ToolResult.fail("文件不存在"))


def test_step8_layers(tr: TestResult):
    """步骤8：图层管理"""
    print("\n[步骤8] 图层管理…")

    result1 = create_layer("laser_red")
    tr.step("创建图层 laser_red", result1)

    result2 = create_layer("laser_white")
    tr.step("创建图层 laser_white", result2)

    result3 = get_layers()
    tr.step(f"获取图层列表", result3)

    # 尝试分配形状到图层
    result4 = assign_to_layer("placeholder_room", "laser_white")
    tr.step(f"placeholder_room → laser_white", result4)


def test_step9_cleanup(tr: TestResult, keep_output: bool):
    """步骤9：清理"""
    print("\n[步骤9] 清理…")

    result = close_document()
    tr.step("关闭文档", result)

    close_connection()
    tr.step("断开 CorelDRAW 连接", ToolResult.ok("OK"))


def main():
    tr = TestResult()

    output_dir = os.path.join(tempfile.gettempdir(), "coreldraw_e2e_test")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  CorelDRAW MCP — 端到端门牌生成测试")
    print(f"  输出目录: {output_dir}")
    print("=" * 60)

    # 步骤1：连接
    if not test_step1_connection(tr):
        print(tr.summary())
        return 1

    # 步骤2-8：测试流程
    if not test_step2_create_document(tr, output_dir):
        print(tr.summary())
        return 1

    from tools.text import set_text_style as import_style
    from tools.colors import set_fill_rgb as import_fill

    test_step3_create_placeholders(tr)
    test_step4_replace_text(tr)
    test_step5_text_overflow(tr)
    test_step6_preflight(tr)
    test_step8_layers(tr)
    test_step7_export(tr, output_dir)

    # 步骤9：清理
    test_step9_cleanup(tr, keep_output=True)

    print(tr.summary())

    if tr.failed > 0:
        print(f"\n⚠️  输出文件保留在: {output_dir}")
    else:
        print(f"\n✅ 所有测试通过！输出文件: {output_dir}")

    return 0 if tr.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
