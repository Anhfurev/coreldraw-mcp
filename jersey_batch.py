"""球衣批量改名改号 —— 不用 AI，直接改，最快。

用法：
    1. 确认 CorelDRAW 已经打开你要改的球衣文件
    2. 改下面 PLAYERS 里的名字和号码
    3. 运行：  .venv\\Scripts\\python.exe jersey_batch.py
    4. 确认没问题后，把 DRY_RUN 改成 False 再运行一次，才会真正写入

DRY_RUN = True 时只显示"将要改什么"，不动文件。建议每次先这样看一遍。

注意：row 编号必须是页面上已存在的球衣行号（用 scan_jersey_rows 结果确认，
当前文件只有 11 行）。想测更多行，要先在 CorelDRAW 里用"整体 group 后
duplicate"的方法把参考件复制出更多行，再在这里填号。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "server"))

from core.connection import init_connection  # noqa: E402
from tools.jersey import scan_jersey_rows, set_jersey_players  # noqa: E402

# ============================================================
# 改这里
# ============================================================

DRY_RUN = True  # 先 True 看一遍，确认无误再改成 False 真正写入

# 20 条占位测试数据（虚构姓名/号码，非真实球员）。row 1-11 对应当前页面已有的
# 11 件球衣，可直接测试；row 12-20 要先在 CorelDRAW 里加够行数才能用。
PLAYERS = [
    {"row": 1, "name": "MARTINEZ", "number": "17"},
    {"row": 2, "name": "GARCIA", "number": "7"},
    {"row": 3, "name": "SMITH", "number": "23"},
    {"row": 4, "name": "MULLER", "number": "11"},
    {"row": 5, "name": "TANAKA", "number": "9"},
    {"row": 6, "name": "IVANOV", "number": "34"},
    {"row": 7, "name": "KOVACS", "number": "5"},
    {"row": 8, "name": "SILVA", "number": "88"},
    {"row": 9, "name": "NGUYEN", "number": "14"},
    {"row": 10, "name": "HASSAN", "number": "42"},
    {"row": 11, "name": "OCONNOR", "number": "3"},
    # row 12-20 需要先在 CorelDRAW 里加够行数（duplicate 参考件 group）才能写入：
    {"row": 12, "name": "WILLIAMS", "number": "21"},
    {"row": 13, "name": "CHEN", "number": "8"},
    {"row": 14, "name": "BROWN", "number": "99"},
    {"row": 15, "name": "SATO", "number": "12"},
    {"row": 16, "name": "PETROV", "number": "27"},
    {"row": 17, "name": "OKAFOR", "number": "6"},
    {"row": 18, "name": "ROSSI", "number": "15"},
    {"row": 19, "name": "ANDERSSON", "number": "77"},
    {"row": 20, "name": "KIM", "number": "10"},
]

# ============================================================
# 下面不用改
# ============================================================


def main() -> int:
    if not init_connection():
        print("连接 CorelDRAW 失败：请先打开 CorelDRAW 和你的球衣文件")
        return 1

    scan = scan_jersey_rows()
    if not scan.success:
        print(f"扫描失败: {scan.message}")
        return 1

    rows = (scan.data or {}).get("rows", [])
    print(f"当前文件里有 {len(rows)} 件球衣：\n")
    print(f"{'行号':>4}  {'姓名':<10} {'号码':>4}   居中偏移(mm)")
    for r in rows:
        o = r["center_offset"]
        offsets = [v for v in (o["back_name"], o["back_num"], o["front_num"]) if v is not None]
        worst = max((abs(v) for v in offsets), default=0)
        flag = "  ← 跑偏了" if worst > 1 else ""
        print(f"{r['row']:>4}  {r['name']:<10} {r['number']:>4}   {worst:.2f}{flag}")

    if not PLAYERS:
        print("\nPLAYERS 是空的 —— 把要改的人填进去再运行。")
        return 0

    max_row = len(rows)
    usable = [p for p in PLAYERS if p["row"] <= max_row]
    skipped = [p for p in PLAYERS if p["row"] > max_row]
    if skipped:
        print(f"\n跳过 {len(skipped)} 条（行号超过当前 {max_row} 行）："
              f"{[p['row'] for p in skipped]}")
    if not usable:
        print("没有可写入的记录。")
        return 0

    print(f"\n{'（试运行，不会写入）' if DRY_RUN else '（正在真正写入）'}")
    result = set_jersey_players(usable, dry_run=DRY_RUN)
    if not result.success:
        print(f"失败: {result.message}")
        return 1

    for item in (result.data or {}).get("results", []):
        print(f"\n第 {item['row']} 件：")
        for c in item["changes"]:
            if "skipped" in c:
                print(f"    {c['shape']}: 跳过（{c['skipped']}）")
            else:
                print(f"    {c['shape']}: {c['old']!r} → {c['new']!r}")

    print(f"\n{result.message}")
    if DRY_RUN:
        print("确认无误后，把文件里的 DRY_RUN 改成 False 再跑一次才会真正写入。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
