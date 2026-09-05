"""球衣批量改名改号 —— 不用 AI，直接改，最快。

用法：
    1. 确认 CorelDRAW 已经打开你要改的球衣文件
    2. 改下面 PLAYERS 里的名字和号码
    3. 运行：  .venv\\Scripts\\python.exe jersey_batch.py
    4. 确认没问题后，把 DRY_RUN 改成 False 再运行一次，才会真正写入

DRY_RUN = True 时只显示"将要改什么"，不动文件。建议每次先这样看一遍。
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

PLAYERS = [
    # {"row": 1, "name": "MARTINEZ", "number": "17"},
    # {"row": 2, "name": "GARCIA",   "number": "7"},
    # row = 行号，1 是页面最上面那件。name/number 可以只写一个。
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

    print(f"\n{'（试运行，不会写入）' if DRY_RUN else '（正在真正写入）'}")
    result = set_jersey_players(PLAYERS, dry_run=DRY_RUN)
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
