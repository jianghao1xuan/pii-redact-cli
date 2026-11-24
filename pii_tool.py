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
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pii_rules import 规则, 新场, 查可疑  # noqa: E402

编码们 = ("utf-8", "gb18030", "big5", "latin-1")


def 猜编码(路: Path) -> str:
    """按顺序试，能整篇解出来才算。最后兜底 latin-1（永不失败）。"""
    原 = 路.read_bytes()
    if 原.startswith(b"\xef\xbb\xbf"):      # 带 BOM 的 UTF-8，写回时也要留着
        return "utf-8-sig"
    for 编 in 编码们:
        try:
            原.decode(编)
            return 编
        except UnicodeDecodeError:
            continue
    return "latin-1"


def 读文件(路: Path):
    """返回 (数据, 模式, 编码, 写回)。模式：'格' 表格行×列；'行' 纯文本行。"""
    后 = 路.suffix.lower()

    if 后 == ".csv":
        编 = 猜编码(路)
        with 路.open(encoding=编, newline="") as f:
            数据 = [r for r in csv.reader(f)]

        def 写(新数据, 出: Path):
            with 出.open("w", encoding=编, newline="") as f:
                csv.writer(f).writerows(新数据)
        return 数据, "格", 编, 写

    if 后 in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except Exception:
            print("处理 xlsx 需要 openpyxl：pip install openpyxl", file=sys.stderr)
            raise SystemExit(2)
        书 = openpyxl.load_workbook(路)
        数据 = {}
        for 页 in 书.worksheets:
            数据[页.title] = [[c.value for c in r] for r in 页.iter_rows()]

        def 写(新数据, 出: Path):
            新 = openpyxl.Workbook()
            新.remove(新.active)
            for 名, 行们 in 新数据.items():
                页 = 新.create_sheet(title=名[:31])
                for r in 行们:
                    页.append(r)
            新.save(出)
        return 数据, "簿", "utf-8", 写

    编 = 猜编码(路)

    def 写(新数据, 出: Path):
        出.write_text("".join(新数据), encoding=编)
    return 路.read_text(encoding=编, errors="replace").splitlines(keepends=True), "行", 编, 写


def 处理(数据, 模式, r: 规则, 场: dict):
    """返回 (新数据, 明细, 可疑)。明细每条 = (位置, 原文, 占位符)。"""
    明细, 可疑 = [], []

    def 走(文, 位置):
        if not isinstance(文, str) or not 文:
            return 文
        前 = len(场["map"])
        新 = r.脱一段(文, 场)
        if len(场["map"]) > 前:
            已 = set(场["map"].values())
            for 键, 原 in 场["map"].items():
                if 原 in 文 and 键 not in {k for _, _, k in 明细}:
                    明细.append((位置, 原, 键))
        for 说明, 片 in 查可疑(新):
            可疑.append((位置, 说明, 片))
        return 新

    if 模式 == "行":
        return [走(l, f"第 {i} 行") for i, l in enumerate(数据, 1)], 明细, 可疑

    if 模式 == "格":
        新 = []
        for i, 行 in enumerate(数据, 1):
            新.append([走(c, f"第 {i} 行 第 {j} 列") for j, c in enumerate(行, 1)])
        return 新, 明细, 可疑

    新簿 = {}
    for 名, 行们 in 数据.items():
        新行们 = []
        for i, 行 in enumerate(行们, 1):
            新行们.append([走(c, f"[{名}] 第 {i} 行 第 {j} 列") for j, c in enumerate(行, 1)])
        新簿[名] = 新行们
    return 新簿, 明细, 可疑


def 报(明细, 可疑, 最多=20):
    记数 = {}
    for _, _, 键 in 明细:
        类 = 键.strip("[]").rsplit("_", 1)[0]
        记数[类] = 记数.get(类, 0) + 1
    print(f"换掉 {len(明细)} 处：")
    for 类, n in sorted(记数.items()):
        print(f"  {类:<9} {n:>3} 处")
    if 明细:
        print("\n明细（位置 / 原文 / 换成了）：")
        for 位置, 原, 键 in 明细[:最多]:
            print(f"  {位置:<22} {原[:26]:<28} → {键}")
        if len(明细) > 最多:
            print(f"  …还有 {len(明细) - 最多} 处，完整列表在映射表里")
    if 可疑:
        print(f"\n⚠ 这 {len(可疑)} 处像敏感信息，但校验没过，我没动——请自己看一眼：")
        for 位置, 说明, 片 in 可疑[:最多]:
            print(f"  {位置:<22} {片[:26]:<28} （{说明}）")
        if len(可疑) > 最多:
            print(f"  …还有 {len(可疑) - 最多} 处")


def 处理docx(源: Path, r: 规则, 场: dict):
    """Word：逐段落、逐表格单元格改。返回 (文档, 明细, 可疑)。

    注意：为了保住位置，改过的段落会把文字并到第一个 run 里——
    段落样式还在，但段内局部的加粗/颜色会丢。这一点 README 里写了。
    """
    try:
        import docx
    except Exception:
        print("处理 .docx 需要 python-docx：pip install python-docx", file=sys.stderr)
        raise SystemExit(2)

    文档 = docx.Document(str(源))
    明细, 可疑 = [], []

    def 走(段, 位置):
        原 = 段.text
        if not 原 or not 原.strip():
            return
        前 = set(场["map"])
        新 = r.脱一段(原, 场)
        for 键, 值 in 场["map"].items():
            if 键 not in 前:
                明细.append((位置, 值, 键))
        if 新 != 原:
            for x in 段.runs[1:]:
                x.text = ""
            if 段.runs:
                段.runs[0].text = 新
            else:
                段.add_run(新)
        for 说明, 片 in 查可疑(新):
            可疑.append((位置, 说明, 片))

    for i, 段 in enumerate(文档.paragraphs, 1):
        走(段, f"第 {i} 段")
    for k, 表 in enumerate(文档.tables, 1):
        for i, 行 in enumerate(表.rows, 1):
            for j, 格 in enumerate(行.cells, 1):
                for 段 in 格.paragraphs:
                    走(段, f"[表 {k}] 第 {i} 行 第 {j} 列")
    return 文档, 明细, 可疑


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

        if 源.suffix.lower() == ".docx":
            try:
                import docx
            except Exception:
                print("还原 .docx 需要 python-docx：pip install python-docx", file=sys.stderr)
                raise SystemExit(2)
            文 = docx.Document(str(源))

            def 改段(段):
                原 = 段.text
                新 = 换(原)
                if 新 != 原:
                    for x in 段.runs[1:]:
                        x.text = ""
                    if 段.runs:
                        段.runs[0].text = 新
                    else:
                        段.add_run(新)

            for 段 in 文.paragraphs:
                改段(段)
            for 表 in 文.tables:
                for 行 in 表.rows:
                    for 格 in 行.cells:
                        for 段 in 格.paragraphs:
                            改段(段)
            出 = Path(参.out) if 参.out else 源.with_name(源.stem + ".restored" + 源.suffix)
            文.save(str(出))
            print("还原完成 →", 出)
            return

        数据, 模式, 编码, 写回 = 读文件(源)
        if 模式 == "行":
            新 = [换(l) for l in 数据]
        elif 模式 == "格":
            新 = [[换(c) if isinstance(c, str) else c for c in 行] for 行 in 数据]
        else:
            新 = {名: [[换(c) if isinstance(c, str) else c for c in 行] for 行 in 行们]
                  for 名, 行们 in 数据.items()}
        出 = Path(参.out) if 参.out else 源.with_name(源.stem + ".restored" + 源.suffix)
        写回(新, 出)
        print("还原完成 →", 出)
        return

    if 源.suffix.lower() == ".docx":
        场 = 新场()
        文档, 明细, 可疑 = 处理docx(源, r, 场)
        print(f"读入：{源.name}（Word）")
        报(明细, 可疑)
        if 参.动作 == "preview":
            print("\n（只是预览，没写任何文件）")
            return
        出 = Path(参.out) if 参.out else 源.with_name(源.stem + ".redacted" + 源.suffix)
        文档.save(str(出))
        映射路 = Path(参.映射) if 参.映射 else 源.with_name(源.stem + ".map.json")
        映射路.write_text(json.dumps(场["map"], ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n脱敏版 →", 出)
        print("映射表 →", 映射路)
        print("⚠ 映射表里是真值：谁拿到它就能还原全部。别外传，用完删掉。")
        return

    数据, 模式, 编码, 写回 = 读文件(源)
    print(f"读入：{源.name}（编码 {编码}）")
    场 = 新场()
    新, 明细, 可疑 = 处理(数据, 模式, r, 场)
    报(明细, 可疑)

    if 参.动作 == "preview":
        print("\n（只是预览，没写任何文件）")
        return

    出 = Path(参.out) if 参.out else 源.with_name(源.stem + ".redacted" + 源.suffix)
    写回(新, 出)
    映射路 = Path(参.映射) if 参.映射 else 源.with_name(源.stem + ".map.json")
    映射路.write_text(json.dumps(场["map"], ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n脱敏版 →", 出)
    print("映射表 →", 映射路)
    print("⚠ 映射表里是真值：谁拿到它就能还原全部。别外传，用完删掉。")


if __name__ == "__main__":
    主()
