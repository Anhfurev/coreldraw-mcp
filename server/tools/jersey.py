"""球衣批量工具 — 不经过 LLM 的确定性快速路径

与其他工具模块的区别：本模块面向"已经排好版的球衣批量文件"这一个具体场景，
把姓名/号码修改这类可预测的操作固化成一次 COM 往返就能完成的确定性函数，
不需要 Agent 先截图、再判断、再决定调哪个工具。实测一次 LLM 往返要 2~7 秒，
而这里的一次修改在 1 秒以内。

版式约定（来自现有批量文件，形状名称在每一行都重复，因此只能靠 Y 坐标区分行）：
    REF_BACK_NAME   背面姓名（每行一个，用它来界定"一行"）
    REF_BACK_NUM    背面号码
    REF_FRONT_NUM   正面号码
    REF_FRONT_TEAM  正面队名

本模块固化了三条踩过坑的规则（详见 .harness/product/backlog.md 已知约束）：
    1. 改完文字内容后绝不调用 set_shape_size —— 会把新文字强行拉伸到旧文字的包围盒
    2. 重新居中的基准必须是"所在面板矩形的真实几何中心"，不能用文字自己修改前的中心
       （否则会把之前就已经跑偏的错误原样保留下去）
    3. 2 位以上号码用 char_spacing=-15 收紧，单字符重置为 0
"""

from typing import Optional

from core.connection import get_connection
from core.models import ToolResult

_CDR_MILLIMETER = 3

_NAME_BACK_NAME = "REF_BACK_NAME"
_NAME_BACK_NUM = "REF_BACK_NUM"
_NAME_FRONT_NUM = "REF_FRONT_NUM"
_NAME_FRONT_TEAM = "REF_FRONT_TEAM"
_ROW_ANCHOR = _NAME_BACK_NAME

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
    """遍历一次页面，分出文字形状和候选面板形状（必须在 COM 线程内调用）"""
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


def _build_rows(texts: list[dict], panels: list[dict]) -> list[dict]:
    """按 Y 坐标把文字形状归拢成"每件球衣一行"，行号 1 = 页面最上面那件"""
    anchors = sorted(
        [t for t in texts if t["name"] == _ROW_ANCHOR],
        key=lambda t: t["y"],
        reverse=True,
    )
    if not anchors:
        return []

    rows = [{"row": i + 1, "anchor_y": a["y"], "shapes": {}} for i, a in enumerate(anchors)]
    for t in texts:
        nearest = min(rows, key=lambda r: abs(r["anchor_y"] - t["y"]))
        nearest["shapes"][t["name"]] = t
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
            raise ValueError("当前页面没有找到球衣（缺少 REF_BACK_NAME 形状）")

        results = []
        for item in updates:
            row = int(item.get("row", 0))
            if row < 1 or row > len(rows):
                raise ValueError(f"行号 {row} 超出范围，当前共 {len(rows)} 件球衣")
            name = str(item.get("name", "") or "")
            number = str(item.get("number", "") or "")
            if not name and not number:
                raise ValueError(f"第 {row} 项既没有 name 也没有 number")
            results.append({
                "row": row,
                "changes": _apply_one(rows[row - 1], panels, name, number, dry_run),
            })
        return {"dry_run": dry_run, "total_rows": len(rows), "results": results}

    result = conn.safe_call(_apply)
    if result["success"]:
        data = result["result"]
        verb = "将要修改" if dry_run else "已修改"
        return ToolResult.ok(f"{verb} {len(data['results'])} 件球衣", **data)
    return ToolResult.fail(result.get("error", "批量修改球衣失败"))
