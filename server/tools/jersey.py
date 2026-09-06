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

# 背面姓名的最大宽度（mm）——用户的硬性规则："姓名最大宽度 25cm，超出时等比例缩小
# （不允许非等比拉伸变形）"。长名字换上去后经常超限，必须写完内容量到真实宽度再判断。
_MAX_NAME_WIDTH = 250.0

# 球衣文字的最小高度（mm）。批量文件里存在小号文字（面料代码标签"3016"，约 30×10mm）
# 沿用了 REF_BACK_NAME 这个名字：只靠名字匹配，它既会被误判成多出来的一件球衣，又会在
# 归行时覆盖掉同一行真正的姓名形状（导致改名字改到标签上）。真实球衣文字高 35~65mm，
# 取 20mm 作为分界线，在收集阶段就把这类小标签排除掉。
_MIN_TEXT_HEIGHT = 20.0

# 面料标签除了"矮"，还必须"窄"。2026-09-06 加上宽度判据，起因是一个真实的破坏性 bug：
# 长姓名按"最大 250mm，超出等比例缩小"的规则缩完之后，高度会跟着等比例变矮（例如
# 700mm×50mm 的长名字缩到 250mm 宽时高度只剩 16mm），于是它比 _MIN_TEXT_HEIGHT 还矮，
# 被 set_jersey_material 当成面料标签、把球员姓名直接覆盖成了"3016"。
# 真实面料标签("3016"这类)大约 24~40mm 宽，而缩过的姓名是 250mm 宽 —— 宽度能干净地
# 区分两者，所以判定标签必须同时满足"矮"和"窄"。
_MAX_LABEL_WIDTH = 120.0


def _is_material_label(w: float, h: float) -> bool:
    """是否是面料标签那种小文字（必须又矮又窄，见 _MAX_LABEL_WIDTH 上面的说明）"""
    return h < _MIN_TEXT_HEIGHT and w < _MAX_LABEL_WIDTH


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
            if not _is_material_label(w, h):
                texts.append({"shape": s, "name": name, "x": x, "y": y, "w": w, "h": h})
        elif w > 200 and h > 200:
            # 面板矩形：足够大、能把文字整个装进去的形状
            panels.append({"x": x, "y": y, "w": w, "h": h})
    return texts, panels


def _snap_text_to_panel_bottom(shape, panel) -> Optional[float]:
    """Текст өөрийн панелийн доод ирмэгээс доош унжсан бол дээш нь панелийн доод ирмэгтэй
    яг тулгаж шилжүүлнэ (өндөр/хэмжээ огт хөндөгдөхгүй, зөвхөн Y байрлал). Хэдэн мм дээш
    шилжүүлснийг буцаана, шилжүүлээгүй бол None.

    Яагаад хэрэгтэй вэ (2026-09-06 олдсон бодит алдаа): нэг жинхэнэ мөрийн текст (жишээ нь
    REF_FRONT_NUM) өөрийн панелийн доод ирмэгээс 307mm ч гэсэн доош унжиж байсан — ганц
    мөрийн хувьд харагдахгүй ч, duplicate_jersey_rows мөр хоорондын зайг "мөрийн БҮХ
    хэлбэрийн жинхэнэ доод цэг" дээр үндэслэн тооцдог тул энэ нь "20mm зай" дүрмийг зөв
    мөрдсөн ч ЖИНХЭНЭ ПАНЕЛЬ хоорондын хоосон зайг зуу гаруй мм болгож хувиргадаг байсан
    (хэрэглэгч "gap too much" гэж мэдээлсэн шалтгаан)."""
    hang = panel.PositionY - shape.PositionY
    if hang > 0:
        shape.PositionY = shape.PositionY + hang
        return round(hang, 1)
    return None


def _crosshair_center_x(side_shapes) -> Optional[float]:
    """Тухайн талын 十字 тэмдгийг (crosshair, Type != 6) олж, түүний хэвтээ төв X-ийг
    буцаана. Олдохгүй бол None.

    2026-09-06 нэмсэн: crosshair бол хэвлэлийн БОДИТ зэрэгцүүлэх тэмдэглэгээ (хэрэглэгч
    хэвлэхдээ үүгээр зэрэгцүүлдэг), панелийн математик геометрийн төвтэй ЯГ ТААРАХГҮЙ
    байдаг нь бодит хэмжилтээр батлагдсан (жишээ: нэг мөрөнд ар талын crosshair
    панелийн төвөөс ~30mm зөрүүтэй байсан бол текст өөрөө панелийн төвд төвлөрсөн үед
    crosshair-тай ~130mm зөрүүтэй харагдсан). Иймд текстийг crosshair байвал ТҮҮНТЭЙ
    нь зэрэгцүүлэх ёстой, зөвхөн панелийн төвтэй биш — эс тэгвэл хэрэглэгчид "төв биш
    шиг" харагдана (яг энэ гомдлыг хэрэглэгч зурган дээр үзүүлсэн)."""
    crosshair = next((s for s in side_shapes if s.Type != 6), None)
    if crosshair is None:
        return None
    return crosshair.PositionX + crosshair.SizeWidth / 2


def _row_reference_centers(doc, row_obj: dict, all_anchors: list[float]) -> dict:
    """Нэг мөрийн 4 нэрлэгдсэн текст тус бүрд ашиглах зэрэгцүүлэх X-ийг (crosshair
    байвал түүний төв, үгүй бол панелийн төв) урьдчилан тооцоод буцаана —
    {key: center_x}. `_apply_one`-д дамжуулж ашиглана."""
    anchor_y = row_obj["anchor_y"]
    row_shapes = _row_shapes_by_y(doc, anchor_y, all_anchors)
    row_panels = [s for s in row_shapes if s.SizeWidth > 200 and s.SizeHeight > 200]
    if len(row_panels) != 2:
        return {}
    front_panel, back_panel = sorted(row_panels, key=lambda s: s.PositionX)
    midpoint_x = (front_panel.PositionX + front_panel.SizeWidth + back_panel.PositionX) / 2
    front_others = [s for s in row_shapes
                    if s.PositionX < midpoint_x and not (s.SizeWidth > 200 and s.SizeHeight > 200)]
    back_others = [s for s in row_shapes
                   if s.PositionX >= midpoint_x and not (s.SizeWidth > 200 and s.SizeHeight > 200)]
    front_ref = _crosshair_center_x(front_others)
    if front_ref is None:
        front_ref = front_panel.PositionX + front_panel.SizeWidth / 2
    back_ref = _crosshair_center_x(back_others)
    if back_ref is None:
        back_ref = back_panel.PositionX + back_panel.SizeWidth / 2
    return {
        _NAME_FRONT_TEAM: front_ref, _NAME_FRONT_NUM: front_ref,
        _NAME_BACK_NAME: back_ref, _NAME_BACK_NUM: back_ref,
    }


def _row_side_panels(doc, row_obj: dict, all_anchors: list[float]) -> dict:
    """{key: panel_shape} — тухайн текст аль талд харьяалагдахыг мэдэхийн тулд (нүүр/ар
    панелийн аль нэгийг нь буцаана). `_snap_text_to_panel_bottom`-д ашиглана."""
    anchor_y = row_obj["anchor_y"]
    row_shapes = _row_shapes_by_y(doc, anchor_y, all_anchors)
    row_panels = [s for s in row_shapes if s.SizeWidth > 200 and s.SizeHeight > 200]
    if len(row_panels) != 2:
        return {}
    front_panel, back_panel = sorted(row_panels, key=lambda s: s.PositionX)
    return {
        _NAME_FRONT_TEAM: front_panel, _NAME_FRONT_NUM: front_panel,
        _NAME_BACK_NAME: back_panel, _NAME_BACK_NUM: back_panel,
    }


def _panel_center_x(panels: list[dict], text: dict) -> Optional[float]:
    """找到装着这个文字的面板，返回面板的真实几何中心 X。

    只用 X 方向判断归属，不再要求文字的 Y 也落在面板 Y 范围内 —— 2026-09-06 改的：
    旧版假设 PositionY 是"顶边"来算文字的垂直中心，但本项目里形状的 Y 基准在"创建"
    和"重新定位"两类 API 之间本来就不一致（见 backlog 已知约束），而且这个参考件的
    正面队名/号码本来就故意挂在面板下方几百 mm（用户确认是有意为之，不是错位）。
    结果是垂直包含判断经常不成立，函数静默返回 None，调用方就跳过了居中——用户看到
    的"文字没居中"正是这个原因。同一行的正/背面板在 X 方向不重叠，因此单靠 X 就能
    唯一确定归属，不需要也不应该再卡 Y。"""
    cx = text["x"] + text["w"] / 2
    best = None
    for p in panels:
        if p["x"] <= cx <= p["x"] + p["w"]:
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


def _row_summary(row: dict, panels: list[dict], center_for: Optional[dict] = None) -> dict:
    shapes = row["shapes"]

    def _content(key: str) -> str:
        t = shapes.get(key)
        return _read_text(t["shape"]) if t else ""

    def _offset(key: str) -> Optional[float]:
        """文字中心相对"真正应该对齐的点"（十字标记的中心，没有就退回面板几何中心）
        的偏移量（mm），用来免截图核查是否跑偏 —— 2026-09-06 改成优先用十字标记，
        因为实测十字标记本身就不在面板几何中心上，只按面板中心判断会把本来对齐
        十字标记的文字误判成"跑偏了"。"""
        t = shapes.get(key)
        if not t:
            return None
        center = (center_for or {}).get(key)
        if center is None:
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
        all_anchors = [r["anchor_y"] for r in rows]
        return {
            "total": len(rows),
            "panels_found": len(panels),
            "rows": [_row_summary(r, panels, _row_reference_centers(doc, r, all_anchors)) for r in rows],
        }

    result = conn.safe_call(_scan)
    if result["success"]:
        data = result["result"]
        return ToolResult.ok(f"扫描到 {data['total']} 件球衣", **data)
    return ToolResult.fail(result.get("error", "扫描球衣失败"))


def _apply_one(
    row_obj: dict, panels: list[dict], name: str, number: str, dry_run: bool,
    center_for: Optional[dict] = None,
) -> list[dict]:
    """对一行执行姓名/号码修改（必须在 COM 线程内调用）。

    center_for: {key: center_x} — байвал (十字 тэмдэгт тулгуурлан урьдчилан тооцсон
    зэрэгцүүлэх X) үүнийг л ашиглана; байхгүй бол хуучин `_panel_center_x` fallback
    (crosshair мэдээлэлгүй үед ч ажиллах чадвартай хэвээр байлгах зорилготой)."""
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
        center = (center_for or {}).get(key)
        if center is None:
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

        # 姓名宽度上限（用户的硬性规则）：背面姓名最宽 250mm，超出必须 **等比例** 缩小，
        # 绝不允许只压宽度那种非等比拉伸变形。长名字（如 "ARIUNZAYA"、"ARIUN IRGL"）
        # 换上去之后经常超限，所以必须在写完内容、量到真实宽度之后再判断。
        shrunk_to = None
        if key == _NAME_BACK_NAME and shape.SizeWidth > _MAX_NAME_WIDTH:
            k = _MAX_NAME_WIDTH / shape.SizeWidth
            target_w, target_h = _MAX_NAME_WIDTH, shape.SizeHeight * k
            shape.SizeWidth = target_w
            shape.SizeHeight = target_h
            shrunk_to = round(shape.SizeWidth, 1)

        # 重新居中：基准是面板真实几何中心，不是文字自己原来的中心
        # 注意此处只改 X、绝不调用 set_shape_size（否则新文字会被拉伸到旧包围盒）
        new_offset = None
        if center is not None:
            shape.PositionX = center - shape.SizeWidth / 2
            new_offset = round(shape.PositionX + shape.SizeWidth / 2 - center, 2)

        entry = {
            "shape": key, "old": old, "new": content,
            "recentered": center is not None, "offset_after": new_offset,
        }
        if shrunk_to is not None:
            entry["name_shrunk_to_mm"] = shrunk_to
        changes.append(entry)
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

        all_anchors = [r["anchor_y"] for r in rows]

        results = [
            {"row": row, "changes": _apply_one(
                rows[row - 1], panels, name, number, dry_run,
                center_for=_row_reference_centers(doc, rows[row - 1], all_anchors),
            )}
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

    2026-09-06 бүрэн дахин бичсэн (хэрэглэгчийн олж мэдсэн 2 бодит алдааг засав):
    1. ӨМНӨ нь панель + бичвэрийг НЭГ group болгож хамт хэмжээг нь өөрчилдөг байсан — group
       resize дотор байгаа бичвэрийг ПРОПОРЦИОНАЛЬ дагуулж суналт хийдэг (тоо/нэр "сунаж"
       харагдах шалтгаан яг энэ байсан). Одоо ЗӨВХӨН панель (background тэгш өнцөгт)-ийг
       шууд SizeWidth/SizeHeight-ээр өөрчилнө, бичвэрт ХЭЗЭЭ Ч SizeWidth/Height хөндөхгүй —
       зөвхөн хэвтээ дахин төвлөрүүлнэ (байрлал өөрчлөгдөнө, хэмжээ өөрчлөгдөхгүй).
    2. ӨМНӨ нь нүүр/ар панель тус бүрийг ӨӨРИЙН зүүн ирмэгээс тус тусад нь томруулдаг
       байсан — нүүр панель өргөсвөл баруун тийш нь ургаж, ар панельтай хоорондын завсрыг
       (gap) идэж/давхцуулдаг байсан (хэрэглэгчийн олж мэдсэн бодит алдаа: "where is the
       gap"). Одоо өөрчлөхөөс ӨМНӨ жинхэнэ завсрыг хэмждэг, дараа нь ар панелийг нүүрийн
       ШИНЭ баруун ирмэгээс яг тэр хэмжээний завсартай байрлуулна — завсар ямар ч хэмжээнд
       өөрчлөгдөхгүй хадгалагдана. Ар талын бусад бүх хэлбэр (十字 тэмдэг, материалын
       шошго, текст) панелийн хамт яг ижил хэмжээгээр X тэнхлэгт шилждэг тул харьцангуй
       байрлал алдагдахгүй.

    Нүүр/ар талыг ялгах: мөрөнд яг 2 панель байх ёстой, X координатаар жижиг нь нүүр тал.
    Бусад хэлбэрийг хоёр панелийн X завсрын голоор нь аль тал руугаа хамаарахыг тогтооно.

    row: мөрийн дугаар (1 = хамгийн дээд мөр, scan_jersey_rows-ээр харна).
    width_cm/length_cm: зорилтот өргөн/урт (см) — панелийн SizeWidth/SizeHeight болж
    бичигдэнэ (см→мм). Аль нэг нь <= 0 бол алдаа буцаана. (Биеийн хэмжээнээс панелийн
    хэмжээ рүү хөрвүүлэх томьёо — жишээ нь өргөнд +7, урт/2 — байвал энэ функцийг дуудахаас
    ӨМНӨ дуудагч тал тооцоод дуудна, энэ функц зөвхөн өгсөн мм рүү шууд тааруулна.)"""
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
            raise ValueError("одоогийн хуудсанд джерси олдсонгүй (найдвартай хос панель байхгүй)")
        if row < 1 or row > len(rows):
            raise ValueError(f"{row}-р мөр хязгаараас гарсан, одоо нийт {len(rows)} джерси байна")

        anchor_y = rows[row - 1]["anchor_y"]
        all_anchors = [r["anchor_y"] for r in rows]
        row_shapes = _row_shapes_by_y(doc, anchor_y, all_anchors)

        def _is_panel(s):
            return s.SizeWidth > 200 and s.SizeHeight > 200

        row_panels = [s for s in row_shapes if _is_panel(s)]
        if len(row_panels) != 2:
            raise ValueError(
                f"{row}-р мөрөнд яг 2 панель байх ёстой байтал {len(row_panels)} олдлоо — "
                "хэмжээ өөрчлөхөөс татгалзав"
            )

        front_panel, back_panel = sorted(row_panels, key=lambda s: s.PositionX)
        old_front_size = (round(front_panel.SizeWidth, 1), round(front_panel.SizeHeight, 1))
        old_back_size = (round(back_panel.SizeWidth, 1), round(back_panel.SizeHeight, 1))
        gap = back_panel.PositionX - (front_panel.PositionX + front_panel.SizeWidth)
        old_back_x = back_panel.PositionX

        midpoint_x = (front_panel.PositionX + front_panel.SizeWidth + back_panel.PositionX) / 2
        front_others = [s for s in row_shapes if not _is_panel(s) and s.PositionX < midpoint_x]
        back_others = [s for s in row_shapes if not _is_panel(s) and s.PositionX >= midpoint_x]

        # 1) ЗӨВХӨН панелийг (background) шууд хэмжээг нь өөрчилнө — бичвэр огт хөндөгдөхгүй.
        front_panel.SizeWidth = target_w_mm
        front_panel.SizeHeight = target_h_mm
        back_panel.SizeWidth = target_w_mm
        back_panel.SizeHeight = target_h_mm

        # 2) Ар панелийг нүүрийн ШИНЭ баруун ирмэгээс хуучин завсрын зайгаар байрлуулна.
        back_panel.PositionX = front_panel.PositionX + front_panel.SizeWidth + gap
        back_shift_x = back_panel.PositionX - old_back_x

        # 3) Ар талын бусад бүх хэлбэр (十字 тэмдэг/шошго/текст) панелийн хамт яг тэр хэмжээгээр
        #    шилжинэ — байрлал (харьцангуй офсет) алдагдахгүй, хэмжээ хэзээ ч хөндөгдөхгүй.
        if back_shift_x:
            for s in back_others:
                s.PositionX = s.PositionX + back_shift_x

        # 4) 4 үндсэн нэрлэгдсэн текстийг зөвхөн ХЭВТЭЭ дахин төвлөрүүлнэ, хэмжээг нь
        #    огт хөндөхгүй. Зэрэгцүүлэх тэнхлэг: 十字 тэмдэг байвал ТҮҮНИЙ төв X
        #    (хэвлэлийн бодит зэрэгцүүлэх тэмдэглэгээ учир), үгүй бол панелийн
        #    геометрийн төв (доор тайлбарласан).
        def _recenter(shapes_list, panel):
            ref_center = _crosshair_center_x(shapes_list)
            if ref_center is None:
                ref_center = panel.PositionX + panel.SizeWidth / 2
            for s in shapes_list:
                if s.Type != 6 or _is_material_label(s.SizeWidth, s.SizeHeight):
                    continue  # шошго биш, жинхэнэ 4 текстийг л төвлөрүүлнэ
                s.PositionX = ref_center - s.SizeWidth / 2
                _snap_text_to_panel_bottom(s, panel)

        _recenter(front_others, front_panel)
        _recenter(back_others, back_panel)

        return {
            "row": row, "target_width_cm": width_cm, "target_length_cm": length_cm,
            "gap_preserved_mm": round(gap, 1),
            "front": {"old_size": old_front_size,
                      "new_size": (round(front_panel.SizeWidth, 1), round(front_panel.SizeHeight, 1))},
            "back": {"old_size": old_back_size,
                     "new_size": (round(back_panel.SizeWidth, 1), round(back_panel.SizeHeight, 1))},
        }

    result = conn.safe_call(_resize)
    if result["success"]:
        data = result["result"]
        return ToolResult.ok(
            f"{row}-р джерсийг {width_cm}x{length_cm}см хэмжээтэй болгов "
            f"(завсар {data['gap_preserved_mm']}mm хадгалагдав, бичвэр суналгүй)",
            **data,
        )
    return ToolResult.fail(result.get("error", "джерси хэмжээ өөрчлөхөд алдаа гарлаа"))


_MATERIAL_LABEL_HEIGHT = 8.0  # mm，面料标签的字高（沿用参考件里那个"3016"小标签的尺寸）
_MATERIAL_LABEL_MARGIN = 10.0  # mm，标签相对面板左下角的偏移


def _create_material_label(doc, panel, content: str):
    """在给定面板的左下角附近新建一个小的面料标签文字（高度 8mm，低于 _MIN_TEXT_HEIGHT，
    因此不会被误判成球衣的 4 个正式文字）。参考件本来就没有标签时用它自动补上——
    用户明确要求"你自己创建那个小标签，别再让我手动加"。"""
    layer = doc.ActivePage.ActiveLayer
    x = panel.PositionX + _MATERIAL_LABEL_MARGIN
    y = panel.PositionY + _MATERIAL_LABEL_MARGIN
    shape = None
    for attempt in (
        lambda: layer.CreateArtisticText(x, y, content, 0, 0, 0, "Arial", 20, False, False, False),
        lambda: layer.CreateArtisticText(x, y, content),
    ):
        try:
            shape = attempt()
            break
        except Exception:
            continue
    if shape is None:
        return None
    cur_h = shape.SizeHeight
    if cur_h > 0:
        scale = _MATERIAL_LABEL_HEIGHT / cur_h
        shape.SizeWidth = shape.SizeWidth * scale
        shape.SizeHeight = _MATERIAL_LABEL_HEIGHT
    shape.PositionX, shape.PositionY = x, y
    return shape


def set_jersey_material(rows: list, material: str) -> ToolResult:
    """把面料/材质代码写进指定几行球衣的面料标签（每行正/背各一个小标签，即之前发现的
    那个误继承了 REF_BACK_NAME 名字的 30x10mm 小文字，例如之前的示例"3016"）。
    按 Y 坐标 + 高度 < 20mm 识别这些标签（同 _collect 排除小标签的判断依据一致，反过来
    专门找它们），不依赖名称——名称本身不可靠，见模块顶部说明。

    某一行根本没有面料标签时，会在该行两个面板的左下角各**自动新建**一个（2026-09-06
    加的，用户明确要求"你自己创建那个小标签，别再让我手动加"）——以前只是返回
    labels_updated=0 并提示用户自己去加，用户重复反馈了很多次。

    rows: 行号列表（1 = 页面最上面那件），对这些行的全部面料标签统一写入同一个 material。"""
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
                    w, h, shape_type = s.SizeWidth, s.SizeHeight, s.Type
                except Exception:
                    continue
                # Type == 6 бол артистик текст (CLAUDE.md-д баримтжуулсан жинхэнэ код, 3 биш —
                # 3 бол шугам/муруй). Зөвхөн өндрөөр шүүвэл өндөр 0 байдаг загалмай
                # тэмдэглэгээний шугамууд ч санамсаргүй орж ирж болзошгүй тул Type-ийг зайлшгүй шалгана.
                # Өргөнийг ч заавал шалгана — 250mm хүртэл жижигрүүлсэн урт нэр намхан
                # болдог тул зөвхөн өндрөөр шүүвэл түүнийг шошго гэж андуурч, тоглогчийн
                # нэрийг материалын кодоор дарж бичдэг байсан (бодит алдаа).
                if shape_type != 6 or not _is_material_label(w, h):
                    continue
                labels.append(s)

            created = 0
            if not labels:
                # Энэ мөрөнд шошго огт байхгүй бол панель тус бүрд нэгийг ӨӨРӨӨ үүсгэнэ
                # (хэрэглэгчээс гараар нэмээрэй гэж гуйхаа болино).
                row_panels = [s for s in row_shapes if s.SizeWidth > 200 and s.SizeHeight > 200]
                for panel in sorted(row_panels, key=lambda s: s.PositionX):
                    new_label = _create_material_label(doc, panel, material)
                    if new_label is not None:
                        labels.append(new_label)
                        created += 1

            written = 0
            for s in labels:
                try:
                    _write_text(s, material)
                    written += 1
                except Exception:
                    continue
            results.append({"row": row, "labels_updated": written, "labels_created": created})
        return {"material": material, "results": results}

    result = conn.safe_call(_apply)
    if result["success"]:
        data = result["result"]
        total = sum(r["labels_updated"] for r in data["results"])
        made = sum(r.get("labels_created", 0) for r in data["results"])
        extra = f"（шинээр {made} шошго үүсгэв）" if made else ""
        return ToolResult.ok(f"{len(rows)} мөрөнд «{material}» гэж {total} шошго бичив{extra}", **data)
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


def recenter_jersey_texts(rows: Optional[list] = None) -> ToolResult:
    """Заасан мөрүүдийн (rows хоосон бол БҮХ мөрийн) 4 үндсэн бичвэрийг тухайн талын
    панелийн жинхэнэ геометрийн төвд дахин байрлуулна, мөн背面 姓名 250mm-ээс өргөн бол
    ЭТГЭЭ ХАРЬЦААГААР жижигрүүлнэ (хэрэглэгчийн хатуу дүрэм).

    Юунд хэрэгтэй вэ: өмнө нь `_panel_center_x` Y тэнхлэгийн шалгуураас болж чимээгүй
    алгасдаг байсан тул аль хэдийн үүсгэчихсэн мөрүүдийн бичвэр төвдөө биш үлдсэн —
    энэ функц тэдгээрийг бөөнөөр нь засна (шинээр юу ч үүсгэхгүй, зөвхөн байрлал/хэмжээ)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW тохирсонгүй")

    def _apply():
        doc = conn.app.ActiveDocument
        if doc is None:
            raise RuntimeError("нээлттэй баримт байхгүй")
        doc.Unit = _CDR_MILLIMETER
        texts, panels = _collect(doc)
        all_rows = _build_rows(texts, panels)
        if not all_rows:
            raise ValueError("当前页面没有找到球衣（找不到成对的面板矩形）")

        targets = rows or [r["row"] for r in all_rows]
        for row in targets:
            if row < 1 or row > len(all_rows):
                raise ValueError(f"行号 {row} 超出范围，当前共 {len(all_rows)} 件球衣")

        all_anchors = [r["anchor_y"] for r in all_rows]

        results = []
        for row in targets:
            row_obj = all_rows[row - 1]
            centers = _row_reference_centers(doc, row_obj, all_anchors)
            side_panels = _row_side_panels(doc, row_obj, all_anchors)
            fixed = []
            if not centers:
                results.append({"row": row, "fixed": [], "skipped": "2 панель олдсонгүй"})
                continue

            for key, t in row_obj["shapes"].items():
                shape = t["shape"]
                center = centers.get(key)
                if center is None:
                    fixed.append({"shape": key, "skipped": "зэрэгцүүлэх цэг олдсонгүй"})
                    continue
                shrunk = None
                if key == _NAME_BACK_NAME and shape.SizeWidth > _MAX_NAME_WIDTH:
                    k = _MAX_NAME_WIDTH / shape.SizeWidth
                    target_h = shape.SizeHeight * k
                    shape.SizeWidth = _MAX_NAME_WIDTH
                    shape.SizeHeight = target_h
                    shrunk = round(shape.SizeWidth, 1)
                before_offset = round(shape.PositionX + shape.SizeWidth / 2 - center, 2)
                shape.PositionX = center - shape.SizeWidth / 2
                panel = side_panels.get(key)
                hang_fixed = _snap_text_to_panel_bottom(shape, panel) if panel is not None else None
                entry = {"shape": key, "offset_before": before_offset,
                         "offset_after": round(shape.PositionX + shape.SizeWidth / 2 - center, 2)}
                if shrunk is not None:
                    entry["name_shrunk_to_mm"] = shrunk
                if hang_fixed is not None:
                    entry["moved_up_mm"] = hang_fixed
                fixed.append(entry)
            results.append({"row": row, "fixed": fixed})
        return {"rows_processed": len(targets), "results": results}

    result = conn.safe_call(_apply)
    if result["success"]:
        data = result["result"]
        return ToolResult.ok(f"{data['rows_processed']} мөрийн бичвэрийг дахин төвлөрүүлэв", **data)
    return ToolResult.fail(result.get("error", "дахин төвлөрүүлэхэд алдаа гарлаа"))


def delete_jersey_row(row: int) -> ToolResult:
    """Заасан нэг мөрийн БҮХ хэлбэрийг (2 панель + бичвэрүүд + 十字 тэмдэг + шошго)
    устгана. Жишээ хэрэглээ: багц үүсгэж дууссаны дараа хамгийн дээрх загвар мөрийг
    (template) устгах. Устгахын өмнө тухайн мөрийн агуулгыг буцаадаг тул дуудагч тал
    юу устгасныг бүртгэж/харуулж чадна.

    row: мөрийн дугаар (1 = хамгийн дээд мөр, scan_jersey_rows-ээр шалгана)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW тохирсонгүй")

    def _delete():
        doc = conn.app.ActiveDocument
        if doc is None:
            raise RuntimeError("нээлттэй баримт байхгүй")
        doc.Unit = _CDR_MILLIMETER
        texts, panels = _collect(doc)
        all_rows = _build_rows(texts, panels)
        if not all_rows:
            raise ValueError("当前页面没有找到球衣（找不到成对的面板矩形）")
        if row < 1 or row > len(all_rows):
            raise ValueError(f"行号 {row} 超出范围，当前共 {len(all_rows)} 件球衣")

        summary = _row_summary(all_rows[row - 1], panels)
        anchor_y = all_rows[row - 1]["anchor_y"]
        all_anchors = [r["anchor_y"] for r in all_rows]
        row_shapes = _row_shapes_by_y(doc, anchor_y, all_anchors)
        deleted = 0
        for s in row_shapes:
            try:
                s.Delete()
                deleted += 1
            except Exception:
                continue
        return {"row": row, "deleted_shapes": deleted, "was": summary,
                "rows_left": len(all_rows) - 1}

    result = conn.safe_call(_delete)
    if result["success"]:
        data = result["result"]
        was = data["was"]
        return ToolResult.ok(
            f"{data['row']}-р мөрийг устгав («{was['name']}» #{was['number']}, "
            f"{data['deleted_shapes']} хэлбэр), үлдсэн {data['rows_left']} мөр",
            **data,
        )
    return ToolResult.fail(result.get("error", "мөр устгахад алдаа гарлаа"))


_HEADER_TEXT_HEIGHT = 40.0  # mm，页眉信息文字的字高（够大、一眼能看到，又不会被当成球衣文字）


def set_batch_header(info: str) -> ToolResult:
    """Хуудасны хамгийн дээд талд багцын мэдээллийн гарчиг бичнэ (жишээ нь
    "ЭМЭГТЭЙ · VOLLEYBALL · 3016 · зай 20mm"). Өмнө нь ийм гарчиг байсан бол
    агуулгыг нь шинэчилнэ, байгаагүй бол шинээр үүсгэнэ.

    Гарчгийг таних арга: хамгийн дээд джерси мөрнөөс ДЭЭР байрлах, өндөр нь
    _MIN_TEXT_HEIGHT-ээс их текст — джерсийн мөрүүдэд ердөө хамаарахгүй тул
    мөр таних логикт саад болохгүй.

    info: бичих мэдээллийн мөр (дуудагч тал хүйс/спорт/материал зэргийг нэгтгэж өгнө)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW тохирсонгүй")
    if not info:
        return ToolResult.fail("info хоосон байна")

    def _apply():
        doc = conn.app.ActiveDocument
        if doc is None:
            raise RuntimeError("нээлттэй баримт байхгүй")
        doc.Unit = _CDR_MILLIMETER
        texts, panels = _collect(doc)
        all_rows = _build_rows(texts, panels)
        if not all_rows:
            raise ValueError("当前页面没有找到球衣（找不到成对的面板矩形）")

        # Хамгийн дээд мөрийн бүх хэлбэрийн дээд ирмэг + зай
        top_anchor = all_rows[0]["anchor_y"]
        all_anchors = [r["anchor_y"] for r in all_rows]
        top_shapes = _row_shapes_by_y(doc, top_anchor, all_anchors)
        top_edge = max(_shape_y_extent(s)[1] for s in top_shapes)
        left_edge = min(s.PositionX for s in top_shapes)
        header_y = top_edge + 80.0

        shapes = doc.ActivePage.Shapes
        existing = None
        for i in range(1, shapes.Count + 1):
            s = shapes.Item(i)
            try:
                if s.Type == 6 and s.SizeHeight >= _MIN_TEXT_HEIGHT and s.PositionY > top_edge:
                    existing = s
                    break
            except Exception:
                continue

        if existing is not None:
            _write_text(existing, info)
            existing.PositionX, existing.PositionY = left_edge, header_y
            return {"created": False, "text": info,
                    "at": (round(left_edge, 1), round(header_y, 1))}

        layer = doc.ActivePage.ActiveLayer
        shape = None
        for attempt in (
            lambda: layer.CreateArtisticText(left_edge, header_y, info, 0, 0, 0, "Arial", 60, False, False, False),
            lambda: layer.CreateArtisticText(left_edge, header_y, info),
        ):
            try:
                shape = attempt()
                break
            except Exception:
                continue
        if shape is None:
            raise RuntimeError("гарчиг үүсгэж чадсангүй")
        if shape.SizeHeight > 0:
            k = _HEADER_TEXT_HEIGHT / shape.SizeHeight
            shape.SizeWidth = shape.SizeWidth * k
            shape.SizeHeight = _HEADER_TEXT_HEIGHT
        shape.PositionX, shape.PositionY = left_edge, header_y
        return {"created": True, "text": info,
                "at": (round(left_edge, 1), round(header_y, 1))}

    result = conn.safe_call(_apply)
    if result["success"]:
        data = result["result"]
        verb = "үүсгэв" if data["created"] else "шинэчлэв"
        return ToolResult.ok(f"Гарчиг {verb}: «{info}»", **data)
    return ToolResult.fail(result.get("error", "гарчиг бичихэд алдаа гарлаа"))


def compact_jersey_rows() -> ToolResult:
    """Аль хэдийн үүсгэсэн бүх мөрийг ХООРОНДОО _ROW_CLEARANCE (20mm) зайтай болтол
    ойртуулна — панелийн доод/дээд ирмэгийг л ашиглана, `recenter_jersey_texts`-ийн адил
    текстийн унжилтад итгэхгүй.

    Яагаад хэрэгтэй вэ: текст панелаасаа хэдэн зуун мм доош унжсан үед
    duplicate_jersey_rows шинэ мөрийг тухайн (буруу, хэт том) "жинхэнэ хамрах хүрээгээр"
    зайлуулж байрлуулсан тул мөрүүд хоорондоо 300mm+ хол зайтай болчихсон байсан
    (`recenter_jersey_texts` зөвхөн текстийг л засдаг тул энэ зайг арилгахгүй, учир нь
    панель аль хэдийн тэр байрандаа "хатаж" үлдсэн). Энэ функц мөр бүрийг (панель+十字
    тэмдэг+бичвэр+шошго бүгдийг НЭГ нэгж болгож) дээрээс доош чиглэлд шилжүүлж, зөвхөн
    панелийн ирмэгүүдийг ашиглан 20mm болтол шахна — эхний (хамгийн дээд) мөр хөдлөхгүй,
    үлдсэн бүгд доош чиглэлд өөрийн ирэх байрлал руугаа шилжинэ.

    Хэмжээ/агуулга огт хөндөгдөхгүй, зөвхөн Y байрлал (бүхэл мөр = нэг block шилжинэ)."""
    conn = get_connection()
    if not conn.status.connected:
        return ToolResult.fail("CorelDRAW тохирсонгүй")

    def _apply():
        doc = conn.app.ActiveDocument
        if doc is None:
            raise RuntimeError("нээлттэй баримт байхгүй")
        doc.Unit = _CDR_MILLIMETER
        texts, panels = _collect(doc)
        all_rows = _build_rows(texts, panels)
        if len(all_rows) < 2:
            return {"rows_processed": len(all_rows), "shifts": []}

        all_anchors = [r["anchor_y"] for r in all_rows]
        shifts = []
        # rows[0] = хамгийн дээд мөр — хөдлөхгүй, суурь болно. Дараагийн мөр бүрийг
        # өмнөх (шинэчлэгдсэн) мөрийн доод ирмэгээс яг 20mm доор байхаар шилжүүлнэ.
        prev_panel_bottom = None
        for idx, row_obj in enumerate(all_rows):
            row_shapes = _row_shapes_by_y(doc, row_obj["anchor_y"], all_anchors)
            row_panels = [s for s in row_shapes if s.SizeWidth > 200 and s.SizeHeight > 200]
            if len(row_panels) != 2:
                shifts.append({"row": row_obj["row"], "skipped": f"{len(row_panels)} панель олдлоо"})
                prev_panel_bottom = None  # дараагийн мөрийг ч найдвартай тооцож чадахгүй тул алгасна
                continue
            panel_bottom = min(s.PositionY for s in row_panels)
            panel_top = max(s.PositionY + s.SizeHeight for s in row_panels)

            if idx == 0 or prev_panel_bottom is None:
                delta = 0.0
            else:
                target_top = prev_panel_bottom - _ROW_CLEARANCE
                delta = target_top - panel_top

            if abs(delta) > 1e-6:
                for s in row_shapes:
                    s.PositionY = s.PositionY + delta
                panel_bottom += delta

            shifts.append({"row": row_obj["row"], "shifted_up_mm": round(delta, 1)})
            prev_panel_bottom = panel_bottom

        return {"rows_processed": len(all_rows), "shifts": shifts}

    result = conn.safe_call(_apply)
    if result["success"]:
        data = result["result"]
        total_shift = sum(abs(s.get("shifted_up_mm", 0)) for s in data["shifts"])
        return ToolResult.ok(
            f"{data['rows_processed']} мөрийг {_ROW_CLEARANCE}mm зайтай болтол шахав "
            f"(нийт {round(total_shift, 1)}mm)", **data,
        )
    return ToolResult.fail(result.get("error", "мөр шахахад алдаа гарлаа"))
