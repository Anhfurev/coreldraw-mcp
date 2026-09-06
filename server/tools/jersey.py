"""球衣批量工具 — 不经过 LLM 的确定性快速路径

与其他工具模块的区别：本模块面向"已经排好版的球衣批量文件"这一个具体场景，
把姓名/号码修改这类可预测的操作固化成一次 COM 往返就能完成的确定性函数，
不需要 Agent 先截图、再判断、再决定调哪个工具。实测一次 LLM 往返要 2~7 秒，
而这里的一次修改在 1 秒以内。

版式约定（形状名称在每一行都重复，因此只能靠 Y 坐标区分行）：
    REF_BACK_NAME   背面姓名
    REF_BACK_NUM    背面号码
    REF_FRONT_NUM   正面号码
    REF_FRONT_TEAM  正面队名

"一行=一件球衣"由成对的面板矩形（正/背）界定，不依赖上面 4 个命名文字——2026-09-06
改的，之前用 REF_BACK_NAME 是否存在来界定行，导致教练服/无号码热身服（没有姓名/号码，
只有面板）完全无法被识别成一行。现在这 4 个命名文字对每一行都是可选的（0~4 个任意组合
都行），只有"面板矩形凑成一对"才是真正必要条件。

本模块固化了几条踩过坑的规则（详见 .harness/product/backlog.md 已知约束）：
    1. 改完文字内容后绝不调用 set_shape_size —— 会把新文字强行拉伸到旧文字的包围盒
    2. 重新居中的基准必须是"所在面板矩形的真实几何中心"，不能用文字自己修改前的中心
       （否则会把之前就已经跑偏的错误原样保留下去）
    3. 2 位以上号码用 char_spacing=-15 收紧，单字符重置为 0
    4. 按 Y 坐标圈一行的形状时，不能用固定半径——用"离哪个行的锚点最近"分类，
       固定半径在 resize_jersey_row 出现、行可以变得很大之后会失效
"""

from typing import Optional

from core.connection import get_connection
from core.models import ToolResult

_CDR_MILLIMETER = 3

_NAME_BACK_NAME = "REF_BACK_NAME"
_NAME_BACK_NUM = "REF_BACK_NUM"
_NAME_FRONT_NUM = "REF_FRONT_NUM"
_NAME_FRONT_TEAM = "REF_FRONT_TEAM"

# 多位数号码的字间距（实测 -15 紧凑且自然，-30 过挤）
_MULTI_CHAR_SPACING = -15.0

# 球衣文字的最小高度（mm）。批量文件里存在小号文字（面料代码标签"3016"，约 30×10mm）
# 沿用了 REF_BACK_NAME 这个名字：只靠名字匹配，它既会被误判成多出来的一件球衣，又会在
# 归行时覆盖掉同一行真正的姓名形状（导致改名字改到标签上）。真实球衣文字高 35~65mm，
# 取 20mm 作为分界线，在收集阶段就把这类小标签排除掉。
_MIN_TEXT_HEIGHT = 20.0


def _read_text(shape) -> str:
    for getter in (lambda: shape.Text.Story.Text, lambda: shape.Text.Contents):
        try:
            value = getter()
            if isinstance(value, str):
                return value
        except Exception:
            continue
    return ""


def _write_text(shape, content: str) -> None:
    for setter in (
        lambda: setattr(shape.Text, "Contents", content),
        lambda: shape.Text.SetContents(2, content),
        lambda: setattr(shape.Text, "Story", content),
    ):
        try:
            setter()
            return
        except Exception:
            continue
    raise RuntimeError("当前 CorelDRAW 版本不支持已知的文字内容写入 API")


def _set_char_spacing(shape, value: float) -> bool:
    for setter in (
        lambda: setattr(shape.Text.Story, "CharSpacing", value),
        lambda: setattr(shape.Text, "CharSpacing", value),
    ):
        try:
            setter()
            return True
        except Exception:
            continue
    return False


def _collect(doc) -> tuple[list[dict], list[dict]]:
    """遍历一次页面，分出文字形状和候选面板形状（必须在 COM 线程内调用）。

    !! 不要改用 GetBoundingBox() 代替 PositionX/PositionY/SizeWidth/SizeHeight —— 2026-09-05
    试过，虽然对单个形状测试时数值一致、实测快 3 倍，但对某些形状（怀疑是带描边/效果的）
    GetBoundingBox() 返回的是视觉包围盒（可能含描边宽度等），与 Position/Size 这两组
    属性不是同一件事，真实文件上直接导致多个球衣的居中偏移从 <0.1mm 错报成 200+mm。
    这里的性能优化必须等搞清楚两者的精确差异后再做，不能为了快而牺牲正确性。"""
    texts, panels = [], []
    shapes = doc.ActivePage.Shapes
    for i in range(1, shapes.Count + 1):
        s = shapes.Item(i)
        try:
            name = s.Name
            x, y = s.PositionX, s.PositionY
            w, h = s.SizeWidth, s.SizeHeight
        except Exception:
            continue

        if name in (_NAME_BACK_NAME, _NAME_BACK_NUM, _NAME_FRONT_NUM, _NAME_FRONT_TEAM):
            if h >= _MIN_TEXT_HEIGHT:
                texts.append({"shape": s, "name": name, "x": x, "y": y, "w": w, "h": h})
        elif w > 200 and h > 200:
            # 面板矩形：足够大、能把文字整个装进去的形状
            panels.append({"x": x, "y": y, "w": w, "h": h})
    return texts, panels


def _panel_center_x(panels: list[dict], text: dict) -> Optional[float]:
    """找到装着这个文字的面板，返回面板的真实几何中心 X"""
    cx = text["x"] + text["w"] / 2
    cy = text["y"] - text["h"] / 2  # PositionY 是顶边，Y 轴向上
    best = None
    for p in panels:
        if p["x"] <= cx <= p["x"] + p["w"] and p["y"] - p["h"] <= cy <= p["y"]:
            # 取能装下它的最小面板，避免匹配到更大的外框
            if best is None or p["w"] * p["h"] < best["w"] * best["h"]:
                best = p
    if best is None:
        return None
    return best["x"] + best["w"] / 2


_PANEL_PAIR_Y_TOLERANCE = 20.0  # mm，нэг мөрийн нүүр/ар панель ижил Y дээр байна гэж үзэх зөвшөөрөгдөх ялгаа


def _pair_panels(panels: list[dict]) -> list[dict]:
    """Панелиудыг ойролцоо Y координатаар хос болгоно (нүүр+ар тал = 1 мөр). Текст (нэр/
    дугаар/баг) байгаа эсэхээс огт хамаарахгүй — зөвхөн панелийн хосоор мөр гэж тодорхойлно,
    учир нь зарим джерси (дасгалжуулагч, дугааргүй дулаацуулах хувцас) нэр/дугааргүй байж
    болно (хэрэглэгчийн 2026-09-06 өгсөн тодорхойлолт), харин панель үргэлж байдаг."""
    used = set()
    pairs = []
    for i, p in enumerate(panels):
        if i in used:
            continue
        best_j, best_dist = None, None
        for j, q in enumerate(panels):
            if j == i or j in used:
                continue
            dist = abs(p["y"] - q["y"])
            if dist <= _PANEL_PAIR_Y_TOLERANCE and (best_dist is None or dist < best_dist):
                best_j, best_dist = j, dist
        if best_j is None:
            continue  # хослуулах панель олдсонгүй — хэвийн бус, алгасна
        used.add(i)
        used.add(best_j)
        left, right = sorted([p, panels[best_j]], key=lambda s: s["x"])
        pairs.append({"anchor_y": p["y"], "front_panel": left, "back_panel": right})
    return sorted(pairs, key=lambda r: -r["anchor_y"])


def _build_rows(texts: list[dict], panels: list[dict]) -> list[dict]:
    """Панелийн хосоор "нэг джерси = нэг мөр" гэж тодорхойлно (текст—нэр/дугаар/баг—0-ээс 4
    хүртэл ямар ч хослолоор байж болно, огт байхгүй байсан ч мөр гэж танигдана). Мөрийн
    дугаар 1 = хуудасны хамгийн дээд мөр."""
    pairs = _pair_panels(panels)
    if not pairs:
        return []

    rows = [{"row": i + 1, "anchor_y": p["anchor_y"], "shapes": {}} for i, p in enumerate(pairs)]
    row_anchors = [r["anchor_y"] for r in rows]
    for t in texts:
        nearest_anchor = min(row_anchors, key=lambda a: abs(a - t["y"]))
        for r in rows:
            if r["anchor_y"] == nearest_anchor:
                r["shapes"][t["name"]] = t
                break
    return rows


def _row_summary(row: dict, panels: list[dict]) -> dict:
    shapes = row["shapes"]

    def _content(key: str) -> str:
        t = shapes.get(key)
        return _read_text(t["shape"]) if t else ""

    def _offset(key: str) -> Optional[float]:
        """文字中心相对面板真实中心的偏移量（mm），用来免截图核查是否跑偏"""
        t = shapes.get(key)
        if not t:
            return None
        center = _panel_center_x(panels, t)
        if center is None:
            return None
        return round(t["x"] + t["w"] / 2 - center, 2)

    return {
        "row": row["row"],
        "name": _content(_NAME_BACK_NAME),
        "number": _content(_NAME_BACK_NUM),
        "front_number": _content(_NAME_FRONT_NUM),
        "team": _content(_NAME_FRONT_TEAM),
        "y": round(row["anchor_y"], 1),
        "center_offset": {
            "back_name": _offset(_NAME_BACK_NAME),
            "back_num": _offset(_NAME_BACK_NUM),
            "front_num": _offset(_NAME_FRONT_NUM),
        },
    }


def scan_jersey_rows() -> ToolResult:
    """扫描当前页面的所有球衣，返回每件的行号、姓名、号码、队名，以及每个文字
    相对所在面板真实几何中心的偏移量（mm，0 表示正好居中）。
    用数据代替截图核查排版：偏移量非 0 就说明这个文字跑偏了，不需要导出图片用眼睛看。
    行号 1 = 页面最上面那件，依次往下。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")

    def _scan():
        doc = conn.app.ActiveDocument
        if doc is None:
            raise RuntimeError("没有打开的文档")
        doc.Unit = _CDR_MILLIMETER
        texts, panels = _collect(doc)
        rows = _build_rows(texts, panels)
        return {
            "total": len(rows),
            "panels_found": len(panels),
            "rows": [_row_summary(r, panels) for r in rows],
        }

    result = conn.safe_call(_scan)
    if result["success"]:
        data = result["result"]
        return ToolResult.ok(f"扫描到 {data['total']} 件球衣", **data)
    return ToolResult.fail(result.get("error", "扫描球衣失败"))


def _apply_one(row_obj: dict, panels: list[dict], name: str, number: str, dry_run: bool) -> list[dict]:
    """对一行执行姓名/号码修改（必须在 COM 线程内调用）"""
    jobs = []
    if name:
        jobs.append((_NAME_BACK_NAME, name))
    if number:
        jobs.append((_NAME_BACK_NUM, number))
        jobs.append((_NAME_FRONT_NUM, number))

    changes = []
    for key, content in jobs:
        t = row_obj["shapes"].get(key)
        if t is None:
            changes.append({"shape": key, "skipped": "该行没有这个形状"})
            continue

        shape = t["shape"]
        old = _read_text(shape)
        center = _panel_center_x(panels, t)

        if dry_run:
            changes.append({
                "shape": key, "old": old, "new": content,
                "panel_center_x": round(center, 2) if center is not None else None,
                "current_offset": round(t["x"] + t["w"] / 2 - center, 2) if center is not None else None,
            })
            continue

        _write_text(shape, content)

        # 号码字间距：2 位以上收紧，单字符重置为正常
        if key in (_NAME_BACK_NUM, _NAME_FRONT_NUM):
            _set_char_spacing(shape, _MULTI_CHAR_SPACING if len(content) >= 2 else 0.0)

        # 重新居中：基准是面板真实几何中心，不是文字自己原来的中心
        # 注意此处只改 X、绝不调用 set_shape_size（否则新文字会被拉伸到旧包围盒）
        new_offset = None
        if center is not None:
            shape.PositionX = center - shape.SizeWidth / 2
            new_offset = round(shape.PositionX + shape.SizeWidth / 2 - center, 2)

        changes.append({
            "shape": key, "old": old, "new": content,
            "recentered": center is not None, "offset_after": new_offset,
        })
    return changes


def set_jersey_player(
    row: int,
    name: str = "",
    number: str = "",
    dry_run: bool = False,
) -> ToolResult:
    """修改指定行球衣的姓名和/或号码，一次调用改完背面姓名 + 背面号码 + 正面号码。
    row 为行号（1 = 页面最上面那件，可先用 scan_jersey_rows 查看）。
    name 留空则不改姓名，number 留空则不改号码。
    改完自动按所在面板的真实几何中心重新居中，2 位以上号码自动收紧字间距。
    dry_run=True 时只计算不写入，用于确认将要改动的内容是否正确。
    改多个人时用 set_jersey_players 批量版本，避免每次都重新扫描整个页面。"""
    if not name and not number:
        return ToolResult.fail("name 和 number 至少要指定一个")
    result = set_jersey_players([{"row": row, "name": name, "number": number}], dry_run=dry_run)
    if not result.success:
        return result
    data = result.data or {}
    changes = data.get("results", [{}])[0].get("changes", [])
    verb = "将要修改" if dry_run else "已修改"
    return ToolResult.ok(f"第 {row} 件球衣{verb} {len(changes)} 个形状",
                         row=row, dry_run=dry_run, changes=changes)


def set_jersey_players(updates: list, dry_run: bool = False) -> ToolResult:
    """批量修改多件球衣的姓名/号码 —— 整页只扫描一次、所有改动在一次 COM 往返里完成。
    updates 为列表，每项形如 {"row": 1, "name": "SMITH", "number": "23"}，
    name/number 可只给其中一个。row 为行号（1 = 页面最上面那件）。
    这是批量场景应该用的接口：改 10 个人耗时与改 1 个人相当，而逐个调用
    set_jersey_player 会把整页扫描重复 10 次。
    dry_run=True 时只计算不写入。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")
    if not updates:
        return ToolResult.fail("updates 为空")

    def _apply():
        doc = conn.app.ActiveDocument
        if doc is None:
            raise RuntimeError("没有打开的文档")
        doc.Unit = _CDR_MILLIMETER
        texts, panels = _collect(doc)
        rows = _build_rows(texts, panels)
        if not rows:
            raise ValueError("当前页面没有找到球衣（找不到成对的面板矩形）")

        # 先校验全部记录，通过后才开始写入 —— 避免"改到一半发现某条行号超范围/
        # 内容为空才报错"，此时前面几条已经真实写进了 CorelDRAW 却整体报失败、
        # 用户看不出哪些其实已经改了。
        parsed = []
        for item in updates:
            row = int(item.get("row", 0))
            if row < 1 or row > len(rows):
                raise ValueError(f"行号 {row} 超出范围，当前共 {len(rows)} 件球衣，未写入任何内容")
            name = str(item.get("name", "") or "")
            number = str(item.get("number", "") or "")
            if not name and not number:
                raise ValueError(f"第 {row} 项既没有 name 也没有 number，未写入任何内容")
            parsed.append((row, name, number))

        results = [
            {"row": row, "changes": _apply_one(rows[row - 1], panels, name, number, dry_run)}
            for row, name, number in parsed
        ]
        return {"dry_run": dry_run, "total_rows": len(rows), "results": results}

    result = conn.safe_call(_apply)
    if result["success"]:
        data = result["result"]
        verb = "将要修改" if dry_run else "已修改"
        return ToolResult.ok(f"{verb} {len(data['results'])} 件球衣", **data)
    return ToolResult.fail(result.get("error", "批量修改球衣失败"))


# 一行球衣的真实构成（2026-09-05 在真实文件上逐个形状核实过，比只看 4 个命名文字复杂得多）：
#   2 个面板矩形（正/背，尺寸按体型不同分 600x800 / 750x1000 等几档，不是固定值）+
#   4 个命名文字 + 背面十字标记(2条独立线) + 正面十字标记(1个含2条线的 group，做法与背面
#   不一致，是手工搭建参考件时留下的不一致，不是 bug) + 2 个面料标签（复制时误继承了
#   REF_BACK_NAME 这个名字，因此不能按名字识别一整行——只能按 Y 坐标）。
#
# 行与行之间的间距不是固定值——不同体型（童装/成人/大码）面板高度不同，行间距会跟着变。
# 相邻两行之间的固定规则是面板边缘留白 20mm（已向用户确认），不是锚点到锚点的固定距离。
_ROW_CLEARANCE = 20.0  # mm，相邻两行"面板边缘到面板边缘"的固定留白（已向用户确认，与体型无关）


def _row_shapes_by_y(doc, anchor_y: float, all_anchors: list[float]) -> list:
    """整行的全部 top-level 形状（含面板/十字标记/面料标签等非文字形状），按"离哪个锚点
    最近"分类，不用固定半径圈——固定半径（曾用 600mm，按旧的"最大面板 1000mm"假设定的）
    在 resize_jersey_row 出现之后就靠不住了：一行被放大到 1500mm 高之后，半径要么包不住
    自己的全部形状，要么会连到隔壁行去（2026-09-06 用一次性测试文档验证过这个真实 bug）。
    "离哪个锚点最近算哪行"不依赖固定尺寸假设，行多大都一样成立，前提是行与行之间确实留了
    间隙（duplicate_jersey_rows 已保证）。all_anchors 需要是当前文档里全部行的锚点列表。"""
    shapes = doc.ActivePage.Shapes
    out = []
    for i in range(1, shapes.Count + 1):
        s = shapes.Item(i)
        try:
            y = s.PositionY
        except Exception:
            continue
        nearest = min(all_anchors, key=lambda a: abs(a - y))
        if abs(nearest - anchor_y) < 1e-6:
            out.append(s)
    return out


def _shape_y_extent(s) -> tuple[float, float]:
    """(底边, 顶边)，不假设 PositionY 是哪个角——两个值都算出来再取 min/max 更稳妥。
    不要改用 GetBoundingBox()，原因见 _collect() 顶部注释。"""
    y, h = s.PositionY, s.SizeHeight
    return min(y, y + h), max(y, y + h)


def duplicate_jersey_rows(source_row: int, count: int = 1) -> ToolResult:
    """把已有的一整件球衣（面板、正反面文字、两个十字对位标记、两个面料标签，完整复制，
    不遗漏任何一个形状）复制出 count 份新的，追加在当前最下面一行的下方（用户明确要求：
    参考件放最顶上不动，新复制的依次往下摆，而不是往上摆——2026-09-06 从"往上"改成
    "往下"）。新行与现有最下面一行之间、以及新行彼此之间，按面板边缘留白 20mm 计算
    间距——不同体型的面板高度不同，因此不能假设行与行之间是固定的锚点间距。

    复制出的新行内容、位置、大小与源完全相同（相当于"再印一件一模一样的"），复制后需要
    再调用 set_jersey_players 改成员的姓名/号码——这是"先复制骨架、再批量填内容"两步流程
    里的第一步，目的是把"20 件球衣"从"AI 一步步想该怎么做"（每步都要等一次 2~7 秒的
    模型往返）变成"一次脚本调用"，详见 backlog.md 已知约束里的耗时实测。

    source_row: 作为复制模板的行号（1 = 页面最上面那件，决定新行的体型规格，
                用 scan_jersey_rows 查看现有行号）。
    count: 要新增几件，默认 1（建议先用 1 验证效果，确认无误再一次性复制剩余数量）。

    会拒绝执行而不是猜一个可能出错的位置的情况：新行会超出页面底部边界（Y<0）——页面里
    没有足够空间放这么多新行，需要先手动把页面调高（注意 set_page_size 会围绕页面中心
    缩放，已有形状坐标会整体偏移，调完之后所有涉及坐标的操作都要重新读取，不能用
    调整前的坐标）。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")
    if count < 1:
        return ToolResult.fail("count 必须 >= 1")

    def _duplicate():
        doc = conn.app.ActiveDocument
        if doc is None:
            raise RuntimeError("没有打开的文档")
        doc.Unit = _CDR_MILLIMETER
        texts, panels = _collect(doc)
        rows = _build_rows(texts, panels)
        if not rows:
            raise ValueError("当前页面没有找到球衣（找不到成对的面板矩形）")
        if source_row < 1 or source_row > len(rows):
            raise ValueError(f"行号 {source_row} 超出范围，当前共 {len(rows)} 件球衣")

        source_anchor_y = rows[source_row - 1]["anchor_y"]
        all_anchors = [r["anchor_y"] for r in rows]
        source_shapes = _row_shapes_by_y(doc, source_anchor_y, all_anchors)
        # Зөвхөн 2 панель (нүүр/ар) байгааг л шалгана — нэр/дугаар/баг текст 0-ээс 4 хүртэл
        # ямар ч хослолоор байж болно (дасгалжуулагч/дугааргүй джерси байж болно тул
        # тогтмол "хамгийн багадаа 8 хэлбэр" гэсэн хатуу шаардлага тавихгүй).
        source_panel_count = sum(1 for s in source_shapes if s.SizeWidth > 200 and s.SizeHeight > 200)
        if source_panel_count != 2:
            raise ValueError(
                f"{source_row}-р мөрөнд яг 2 панель байх ёстой байтал {source_panel_count} олдлоо, "
                "хуулбарлахаас татгалзав"
            )

        # 该行真实的底边/顶边相对锚点的偏移（不假设固定面板尺寸，直接量真实形状范围）
        extents = [_shape_y_extent(s) for s in source_shapes]
        row_bottom_offset = min(e[0] for e in extents) - source_anchor_y
        row_top_offset = max(e[1] for e in extents) - source_anchor_y
        row_height = row_top_offset - row_bottom_offset

        # 现有页面上所有形状的最低点（不止 source_row，因为最下面一行不一定是 source_row）
        all_shapes = [doc.ActivePage.Shapes.Item(i) for i in range(1, doc.ActivePage.Shapes.Count + 1)]
        current_bottom = min(_shape_y_extent(s)[0] for s in all_shapes)

        # 先算出全部 count 个目标位置并校验，全部通过才开始写——不要边写边查，
        # 否则第 k 件超出页面时前面 k-1 件已经真实创建了，却整体报"失败"
        margin = 5.0  # mm，留一点余量而不是刚好贴到页面边缘
        targets = []
        for k in range(count):
            # 第 1 件贴着现有最低行的底边留 20mm；第 2 件及以后贴着上一件新行的底边留 20mm
            # （新行彼此尺寸相同，间距自然一致，不需要再假设）
            prev_bottom = current_bottom if k == 0 else targets[-1] + row_bottom_offset
            new_row_top = prev_bottom - _ROW_CLEARANCE
            target_anchor_y = new_row_top - row_top_offset
            projected_bottom = target_anchor_y + row_bottom_offset
            if projected_bottom < margin:
                raise ValueError(
                    f"第 {k + 1} 件新球衣会超出页面底部（预计底部 {round(projected_bottom, 1)}mm，"
                    "Y 不能小于 0）——未写入任何新行，"
                    f"页面空间最多还能安全放 {k} 件；需要更多请先调高页面"
                )
            targets.append(target_anchor_y)

        created = []
        for target_anchor_y in targets:
            y_offset = target_anchor_y - source_anchor_y
            for shape in source_shapes:
                shape.Duplicate(0, y_offset)
            created.append({"anchor_y": round(target_anchor_y, 1)})

        return {
            "source_row": source_row,
            "row_height_mm": round(row_height, 1),
            "clearance_mm": _ROW_CLEARANCE,
            "shapes_per_row": len(source_shapes),
            "new_rows_created": len(created),
            "detail": created,
        }

    result = conn.safe_call(_duplicate)
    if result["success"]:
        data = result["result"]
        return ToolResult.ok(
            f"从第 {source_row} 行复制出 {data['new_rows_created']} 件新球衣"
            f"（每件 {data['shapes_per_row']} 个形状），用 scan_jersey_rows 确认后"
            "再用 set_jersey_players 填姓名/号码",
            **data,
        )
    return ToolResult.fail(result.get("error", "复制球衣行失败"))


def resize_jersey_row(row: int, width_cm: float, length_cm: float) -> ToolResult:
    """Тухайн нэг мөрийн джерсийг бодит биеийн хэмжээнд тааруулж ЖИНХЭНЭ хэмжээгээр өөрчилнө
    (өмнө нь width_cm/length_cm зөвхөн хүснэгтэд лавлагаанд байсан, CorelDRAW руу огт
    бичигддэггүй байсан — энэ функц тэрийг засна).

    Яг яаж хийдэг вэ: нэг талыг (нүүр эсвэл ар тал тус тусад нь) панель + түүнтэй хамт
    十字 тэмдэг + бичвэрүүдийг НЭГ бүлэг (group) болгож, тэр бүлгийг зорилтот өргөн/уртад
    тааруулж ХЭМЖЭЭГ ӨӨРЧЛӨӨД (SizeWidth/SizeHeight), дараа нь ungroup хийнэ. Group хэмжээ
    өөрчлөхөд дотор байгаа бүх зүйл (текст оруулаад) ЗӨВ ХАРЬЦААТАЙГААР дагаж масштаблагддаг
    нь тест хийж баталгаажуулсан зүйл (жишээ нь өндөр 1.125 дахин өсвөл дотор байгаа бичвэрийн
    өндөр ч яг 1.125 дахин өснө) — иймд хэмжээ өөрчлөгдсөний дараа текст төвөө алдахгүй,
    учир нь бүх зүйл ХАМТДАА, ХАРЬЦаагаа хадгалж томорч/жижигэрдэг тул панелийн жинхэнэ
    геометрийн төвтэй харьцангуй байрлал өөрчлөгдөхгүй.

    Нүүр/ар талыг ялгах нь: мөрөнд яг 2 панель байх ёстой (нүүр, ар), X координатаар
    жижиг нь нүүр тал. Бусад бүх хэлбэрийг (十字 тэмдэг, бичвэр) хоёр панелийн X завсрын
    голоор нь аль тал руугаа хамаарахыг тодорхойлно (тогтмол тоо биш, харьцангуй тооцоолол).

    row: мөрийн дугаар (1 = хамгийн дээд мөр, scan_jersey_rows-ээр харна).
    width_cm/length_cm: зорилтот өргөн/урт (см) — эдгээр нь панелийн SizeWidth/SizeHeight
    болж бичигдэнэ (см→мм хөрвүүлнэ). Аль нэг нь <= 0 бол алдаа буцаана (таамаглахгүй)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW тохирсонгүй")
    if width_cm <= 0 or length_cm <= 0:
        return ToolResult.fail("width_cm/length_cm 0-с их байх ёстой")

    target_w_mm = width_cm * 10.0
    target_h_mm = length_cm * 10.0

    def _resize():
        doc = conn.app.ActiveDocument
        if doc is None:
            raise RuntimeError("нээлттэй баримт байхгүй")
        doc.Unit = _CDR_MILLIMETER
        texts, panels = _collect(doc)
        rows = _build_rows(texts, panels)
        if not rows:
            raise ValueError("одоогийн хуудсанд джерси олдсонгүй (REF_BACK_NAME хэлбэр байхгүй)")
        if row < 1 or row > len(rows):
            raise ValueError(f"{row}-р мөр хязгаараас гарсан, одоо нийт {len(rows)} джерси байна")

        anchor_y = rows[row - 1]["anchor_y"]
        all_anchors = [r["anchor_y"] for r in rows]
        row_shapes = _row_shapes_by_y(doc, anchor_y, all_anchors)
        row_panels = [s for s in row_shapes if s.SizeWidth > 200 and s.SizeHeight > 200]
        if len(row_panels) != 2:
            raise ValueError(
                f"{row}-р мөрөнд яг 2 панель байх ёстой байтал {len(row_panels)} олдлоо — "
                "хэмжээ өөрчлөхөөс татгалзав"
            )

        front_panel, back_panel = sorted(row_panels, key=lambda s: s.PositionX)
        midpoint_x = (front_panel.PositionX + front_panel.SizeWidth + back_panel.PositionX) / 2
        front_side = [s for s in row_shapes if s.PositionX < midpoint_x]
        back_side = [s for s in row_shapes if s.PositionX >= midpoint_x]

        def _resize_side(side_shapes, panel, label):
            old_w, old_h = panel.SizeWidth, panel.SizeHeight
            rng = conn.app.CreateShapeRange()
            for s in side_shapes:
                rng.Add(s)
            group = rng.Group()
            group.SizeWidth = target_w_mm
            group.SizeHeight = target_h_mm
            group.Ungroup()
            return {"side": label, "old_size": (round(old_w, 1), round(old_h, 1)),
                    "new_size": (round(panel.SizeWidth, 1), round(panel.SizeHeight, 1))}

        results = [
            _resize_side(front_side, front_panel, "front"),
            _resize_side(back_side, back_panel, "back"),
        ]
        return {"row": row, "target_width_cm": width_cm, "target_length_cm": length_cm,
                "results": results}

    result = conn.safe_call(_resize)
    if result["success"]:
        data = result["result"]
        return ToolResult.ok(
            f"{row}-р джерсийг {width_cm}x{length_cm}см хэмжээтэй болгов", **data
        )
    return ToolResult.fail(result.get("error", "джерси хэмжээ өөрчлөхөд алдаа гарлаа"))


def set_jersey_material(rows: list, material: str) -> ToolResult:
    """把面料/材质代码写进指定几行球衣的面料标签（每行正/背各一个小标签，即之前发现的
    那个误继承了 REF_BACK_NAME 名字的 30x10mm 小文字，例如之前的示例"3016"）。
    按 Y 坐标 + 高度 < 20mm 识别这些标签（同 _collect 排除小标签的判断依据一致，反过来
    专门找它们），不依赖名称——名称本身不可靠，见模块顶部说明。

    rows: 行号列表（1 = 页面最上面那件），对这些行的全部面料标签统一写入同一个 material。
    找不到面料标签的行会在返回结果里标记 skipped，不会报错中断其它行。"""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW 未连接")
    if not rows:
        return ToolResult.fail("rows 为空")
    if not material:
        return ToolResult.fail("material 为空")

    def _apply():
        doc = conn.app.ActiveDocument
        if doc is None:
            raise RuntimeError("没有打开的文档")
        doc.Unit = _CDR_MILLIMETER
        texts, panels = _collect(doc)
        all_rows = _build_rows(texts, panels)
        if not all_rows:
            raise ValueError("当前页面没有找到球衣（找不到成对的面板矩形）")
        for row in rows:
            if row < 1 or row > len(all_rows):
                raise ValueError(f"行号 {row} 超出范围，当前共 {len(all_rows)} 件球衣")

        all_anchors = [r["anchor_y"] for r in all_rows]
        results = []
        for row in rows:
            anchor_y = all_rows[row - 1]["anchor_y"]
            row_shapes = _row_shapes_by_y(doc, anchor_y, all_anchors)
            labels = []
            for s in row_shapes:
                try:
                    h, shape_type = s.SizeHeight, s.Type
                except Exception:
                    continue
                # Type == 6 бол артистик текст (CLAUDE.md-д баримтжуулсан жинхэнэ код, 3 биш —
                # 3 бол шугам/муруй). Зөвхөн өндрөөр шүүвэл өндөр 0 байдаг загалмай
                # тэмдэглэгээний шугамууд ч санамсаргүй орж ирж болзошгүй тул Type-ийг зайлшгүй шалгана.
                if shape_type != 6 or h >= _MIN_TEXT_HEIGHT:
                    continue  # текст биш, эсвэл 4 үндсэн текстийн нэг (~30x10mm биш)
                labels.append(s)
            written = 0
            for s in labels:
                try:
                    _write_text(s, material)
                    written += 1
                except Exception:
                    continue
            results.append({"row": row, "labels_updated": written})
        return {"material": material, "results": results}

    result = conn.safe_call(_apply)
    if result["success"]:
        data = result["result"]
        total = sum(r["labels_updated"] for r in data["results"])
        return ToolResult.ok(f"{len(rows)} мөрөнд «{material}» гэж {total} шошго бичив", **data)
    return ToolResult.fail(result.get("error", "面料标签写入失败"))


def set_batch_mode(enabled: bool) -> ToolResult:
    """CorelDRAW-ийн дэлгэц дахин зурах (redraw) үйлдлийг цуцлах/сэргээх — олон удаагийн
    duplicate/resize/set_text зэрэг COM дуудлагыг дараалан хийхэд дэлгэц бүр удаа дахин
    зурагдахгүй тул хэрэглэгчид "each by each, stopping" мэт удаан санагдахгүй, мэдэгдэхүйц
    хурдасна. ЗААВАЛ batch эхлэхэд enabled=True, дуусаад (амжилттай ч, алдаатай ч) эцэст нь
    enabled=False дуудаж СЭРГЭЭХ ёстой — эс тэгвэл CorelDRAW цаашид ч дэлгэц зурахгүй хэвээр
    үлдэнэ. Энэ функц зөвхөн дэлгэцийн шинэчлэлтэй холбоотой, ямар ч байрлал/хэмжээ тооцоолол
    өөрчлөхгүй тул бусад функцүүдийн адил эрсдэлгүй."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW тохирсонгүй")

    def _toggle():
        conn.app.Optimization = enabled
        return {"optimization": enabled}

    result = conn.safe_call(_toggle)
    if result["success"]:
        return ToolResult.ok(f"batch mode {'идэвхжлээ' if enabled else 'унтарлаа'}", **result["result"])
    return ToolResult.fail(result.get("error", "batch mode тохируулж чадсангүй"))
