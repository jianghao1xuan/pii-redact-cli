# -*- coding: utf-8 -*-
"""pii-redact-cli：中文敏感信息脱敏（命令行，处理文件）。

不需要 Open WebUI，只要有 Python 3.8+。

    python pii_tool.py preview 客户.csv
    python pii_tool.py redact  客户.csv
    python pii_tool.py restore 客户.redacted.csv --map 客户.map.json
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pii_rules import 规则, 新场  # noqa: E402


def 读格(路: Path):
    """返回 (数据, 模式, 写回)。模式：'格' 是表格，'行' 是纯文本。"""
    后 = 路.suffix.lower()
    if 后 == ".csv":
        with 路.open(encoding="utf-8-sig", newline="") as f:
            行 = [r for r in csv.reader(f)]

        def 写(新行, 出: Path):
            with 出.open("w", encoding="utf-8-sig", newline="") as f:
                csv.writer(f).writerows(新行)
        return 行, "格", 写

    if 后 in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except Exception:
            print("处理 xlsx 需要 openpyxl：pip install openpyxl", file=sys.stderr)
            raise SystemExit(2)
        书 = openpyxl.load_workbook(路)
        行 = [[c.value for c in r] for r in 书.active.iter_rows()]

        def 写(新行, 出: Path):
            新 = openpyxl.Workbook()
            页 = 新.active
            for r in 新行:
                页.append(r)
            新.save(出)
        return 行, "格", 写

    return (路.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True), "行",
            lambda 新行, 出: 出.write_text("".join(新行), encoding="utf-8"))


def 主():
    解 = argparse.ArgumentParser(description="中文敏感信息脱敏（命令行版，不需要 Open WebUI）")
    解.add_argument("动作", choices=["preview", "redact", "restore"], help="预览 / 脱敏 / 还原")
    解.add_argument("文件", help="要处理的文件：.txt .md .csv .xlsx")
    解.add_argument("--out", default="", help="输出路径（默认在原文件旁边）")
    解.add_argument("--map", dest="映射", default="", help="映射表路径（还原时必填）")
    参 = 解.parse_args()

    源 = Path(参.文件)
    if not 源.is_file():
        print("找不到文件：", 源, file=sys.stderr)
        raise SystemExit(2)

    r = 规则()

    if 参.动作 == "restore":
        if not 参.映射:
            print("还原需要 --map 指向映射表", file=sys.stderr)
            raise SystemExit(2)
        反 = json.loads(Path(参.映射).read_text(encoding="utf-8"))

        def 换(文):
            for k, v in 反.items():
                文 = 文.replace(k, v)
            return 文

        行, 模式, 写回 = 读格(源)
        if 模式 == "格":
            新行 = [[换(c) if isinstance(c, str) else c for c in 行_] for 行_ in 行]
        else:
            新行 = [换(l) for l in 行]
        出 = Path(参.out) if 参.out else 源.with_name(源.stem + ".restored" + 源.suffix)
        写回(新行, 出)
        print("还原完成 →", 出)
        return

    场 = 新场()

    def 换(文):
        return r.脱一段(文, 场)

    行, 模式, 写回 = 读格(源)
    if 模式 == "格":
        新行 = [[换(c) if isinstance(c, str) else c for c in 行_] for 行_ in 行]
    else:
        新行 = [换(l) for l in 行]

    映射 = 场["map"]
    记数 = {}
    for k in 映射:
        类 = k.strip("[]").rsplit("_", 1)[0]
        记数[类] = 记数.get(类, 0) + 1

    print(f"这{'张表' if 模式 == '格' else '个文件'}里换掉 {len(映射)} 处：")
    for 类, n in sorted(记数.items()):
        print(f"  {类:<9} {n:>3} 处")

    if 参.动作 == "preview":
        if 映射:
            print("\n前几处长这样（左＝原文，右＝发出去的样子）：")
            for k, v in list(映射.items())[:5]:
                print(f"  {v[:28]:<30} → {k}")
        print("\n（只是预览，没写任何文件）")
        return

    出 = Path(参.out) if 参.out else 源.with_name(源.stem + ".redacted" + 源.suffix)
    写回(新行, 出)
    映射路 = Path(参.映射) if 参.映射 else 源.with_name(源.stem + ".map.json")
    映射路.write_text(json.dumps(映射, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n脱敏版 →", 出)
    print("映射表 →", 映射路)
    print("映射表里是真值，用完请删掉。")


if __name__ == "__main__":
    主()
