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

编码们 = ("utf-8", "gb18030", "big5")

# BOM → 编码。UTF-16/32 的字节里全是 0，被 gb18030 读也能“成功”，
# 于是整篇成了乱码、一个号码都对不上，最后还报“完成”——2026-11-25 修的就是这个。
BOM表 = (
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
)


class 编码认不出(Exception):
    """猜不出编码时抛它——宁可报错，也不能“读成乱码还说完成了”。"""


def 猜编码(路: Path, 指定: str = "") -> str:
    if 指定:
        return 指定
    原 = 路.read_bytes()
    for bom, 编 in BOM表:
        if 原.startswith(bom):
            return 编
    for 编 in 编码们:
        try:
            原.decode(编)
            return 编
        except UnicodeDecodeError:
            continue
    raise 编码认不出(
        f"猜不出 {路.name} 的编码（试过 {', '.join(编码们)}）。"
        "请用 --encoding 指定，比如 --encoding gbk")


def 读文件(路: Path, 指定编码: str = ""):
    """返回 (数据, 模式, 编码, 写回)。模式：'格' 表格行×列；'行' 纯文本行。"""
    后 = 路.suffix.lower()

    if 后 == ".csv":
        编 = 猜编码(路, 指定编码)
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

        def 写(新数据, 出: Path):
            # 2026-11-25 改：以前是新建 Workbook 再 append，结果公式还在、格式全没了
            # （加粗、底色、数字格式、列宽、行高、合并单元格）。现在原地改完直接另存。
            新数据.save(出)
        return 书, "簿", "utf-8", 写

    编 = 猜编码(路, 指定编码)
    # 不再用 errors="replace"：解不出的字节换成 � 再写回去，等于悄悄改坏文件
    行们 = 路.read_text(encoding=编).splitlines(keepends=True)

    def 写(新数据, 出: Path):
        出.write_text("".join(新数据), encoding=编)
    return 行们, "行", 编, 写


def 处理(数据, 模式, r: 规则, 场: dict):
    """返回 (新数据, 明细, 可疑)。明细每条 = (位置, 原文, 占位符)。"""
    明细, 可疑 = [], []

    def 走(文, 位置):
        if not isinstance(文, str) or not 文:
            return 文
        场.pop("新键", None)
        新 = r.脱一段(文, 场)
        for 键 in 场.pop("新键", []):
            明细.append((位置, 场["map"][键], 键))
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

    for 页 in 数据.worksheets:
        for i, 行 in enumerate(页.iter_rows(), 1):
            for j, 格 in enumerate(行, 1):
                if isinstance(格.value, str) and 格.value:
                    格.value = 走(格.value, f"[{页.title}] 第 {i} 行 第 {j} 列")
    return 数据, 明细, 可疑


def 报(明细, 可疑, 最多=20):
    记数 = {}
    for _, _, 键 in 明细:
        类 = 键.strip("[]").rsplit("_", 1)[0]
        记数[类] = 记数.get(类, 0) + 1
    if not 明细:
        print("⚠ 一处都没换到。如果这份文件里确实有敏感信息，先确认编码对不对"
              "（可以试 --encoding gbk 或 utf-16），别直接当成“干净”。")
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

    def 换文(原: str, 位置: str) -> str:
        """把一段字符串脱敏，顺手记明细和可疑。段落、XML 文本节点都走它。"""
        if not 原 or not 原.strip():
            return 原
        前 = set(场["map"])
        新 = r.脱一段(原, 场)
        for 键, 值 in 场["map"].items():
            if 键 not in 前:
                明细.append((位置, 值, 键))
        for 说明, 片 in 查可疑(新):
            可疑.append((位置, 说明, 片))
        return 新

    def 走(段, 位置):
        原 = 段.text
        if not 原 or not 原.strip():
            return
        新 = 换文(原, 位置)
        if 新 != 原:
            for x in 段.runs[1:]:
                x.text = ""
            if 段.runs:
                段.runs[0].text = 新
            else:
                段.add_run(新)

    for i, 段 in enumerate(文档.paragraphs, 1):
        走(段, f"第 {i} 段")
    for k, 表 in enumerate(文档.tables, 1):
        for i, 行 in enumerate(表.rows, 1):
            for j, 格 in enumerate(行.cells, 1):
                for 段 in 格.paragraphs:
                    走(段, f"[表 {k}] 第 {i} 行 第 {j} 列")

    # 2026-11-25 补：页眉、页脚、脚注、尾注以前完全不过——合同类的敏感信息恰恰常在这儿。
    # 每一节各有自己的页眉页脚，首页还可能单独一套，所以要逐节走。
    for k, 节 in enumerate(文档.sections, 1):
        for 名, 部件 in (("页眉", 节.header), ("首页页眉", 节.first_page_header),
                         ("页脚", 节.footer), ("首页页脚", 节.first_page_footer)):
            try:
                for 段 in 部件.paragraphs:
                    走(段, f"[{名} {k}]")
                for i, 表 in enumerate(部件.tables, 1):
                    for ii, 行 in enumerate(表.rows, 1):
                        for jj, 格 in enumerate(行.cells, 1):
                            for 段 in 格.paragraphs:
                                走(段, f"[{名} {k} 表 {i}] 第 {ii} 行 第 {jj} 列")
            except Exception:
                continue          # 有些文档没有首页页眉这类部件，跳过就行

    # 2026-11-25 补：文本框（w:txbxContent）不在 paragraphs/tables/header 里，以前全漏。
    # 直接扫 XML 里的 <w:t> 文本节点，能把文本框里的字一起过掉；已经换成占位符的不会再变。
    try:
        from docx.oxml.ns import qn
        根们 = [文档.element]
        for 节2 in 文档.sections:
            for 部件2 in (节2.header, 节2.footer, 节2.first_page_header, 节2.first_page_footer):
                try:
                    if 部件2 is not None:
                        根们.append(部件2._element)
                except Exception:
                    pass
        for 根 in 根们:
            for 位, t in enumerate(根.iter(qn("w:t")), 1):
                if t.text:
                    t.text = 换文(t.text, f"[文本框/文本节点 {位}]")
    except Exception:
        pass

    for 名, 部件 in (("脚注", getattr(文档, "footnotes", None)),
                     ("尾注", getattr(文档, "endnotes", None))):
        try:
            for 段 in (部件.paragraphs if 部件 is not None else []):
                走(段, f"[{名}]")
        except Exception:
            continue
    return 文档, 明细, 可疑


支持后缀 = {".txt", ".md", ".csv", ".xlsx", ".xlsm", ".docx"}
不支持说明 = {
    ".pdf": "PDF 这一版没做（要解析版式，容易出错）",
    ".doc": "老式 .doc 不支持，请在 Word 里另存为 .docx",
    ".jpg": "图片要先 OCR，做不到「改完还能还原」，所以不放进这个工具",
    ".jpeg": "同上",
    ".png": "同上",
    ".xls": "老式 .xls 不支持，请另存为 .xlsx",
}


def 主():
    解 = argparse.ArgumentParser(description="中文敏感信息脱敏（命令行版，不需要 Open WebUI）")
    解.add_argument("动作", choices=["preview", "redact", "restore"], help="预览 / 脱敏 / 还原")
    解.add_argument("文件", help="要处理的文件：.txt .md .csv .xlsx")
    解.add_argument("--out", default="", help="输出路径（默认在原文件旁边）")
    解.add_argument("--map", dest="映射", default="", help="映射表路径（还原时必填）")
    解.add_argument("--encoding", dest="指定编码", default="",
                    help="强制指定源文件编码（如 gbk、utf-16）；猜不出时会要求你指定")
    参 = 解.parse_args()

    源 = Path(参.文件)
    if not 源.is_file():
        print("找不到文件：", 源, file=sys.stderr)
        raise SystemExit(2)

    if 源.suffix.lower() not in 支持后缀:
        说 = 不支持说明.get(源.suffix.lower(), "这个格式没做")
        print(f"不支持 {源.suffix}：{说}", file=sys.stderr)
        print(f"现在支持：{'、'.join(sorted(支持后缀))}", file=sys.stderr)
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
            # 2026-11-25：文本框（XML 文本节点）也要还原
            try:
                from docx.oxml.ns import qn as _qn
                for 根 in [文.element] + [s2._element for s2 in 文.sections]:
                    for t in 根.iter(_qn("w:t")):
                        if t.text:
                            t.text = 换(t.text)
            except Exception:
                pass
            # 2026-11-25：页眉页脚也要还原，不然挡住了回不去
            for 节 in 文.sections:
                for 部件 in (节.header, 节.footer, 节.first_page_header, 节.first_page_footer):
                    try:
                        for 段 in 部件.paragraphs:
                            改段(段)
                        for 表 in 部件.tables:
                            for 行 in 表.rows:
                                for 格 in 行.cells:
                                    for 段 in 格.paragraphs:
                                        改段(段)
                    except Exception:
                        continue
            出 = Path(参.out) if 参.out else 源.with_name(源.stem + ".restored" + 源.suffix)
            文.save(str(出))
            print("还原完成 →", 出)
            return

        数据, 模式, 编码, 写回 = 读文件(源, 参.指定编码)
        if 模式 == "行":
            新 = [换(l) for l in 数据]
        elif 模式 == "格":
            新 = [[换(c) if isinstance(c, str) else c for c in 行] for 行 in 数据]
        elif 模式 == "簿":
            for 页 in 数据.worksheets:
                for 行 in 页.iter_rows():
                    for 格 in 行:
                        if isinstance(格.value, str):
                            格.value = 换(格.value)
            新 = 数据
        else:
            新 = [[换(c) if isinstance(c, str) else c for c in 行] for 行 in 数据]
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

    try:
        数据, 模式, 编码, 写回 = 读文件(源, 参.指定编码)
    except 编码认不出 as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(3)
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
