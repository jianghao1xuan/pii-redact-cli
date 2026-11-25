# -*- coding: utf-8 -*-
"""验 Word 页眉页脚：以前全漏，现在要能挡、也能还原。"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import docx  # noqa: E402

根 = Path(__file__).resolve().parent.parent
工具 = 根 / "pii_tool.py"
临 = Path(tempfile.mkdtemp(prefix="hdr_"))


def 跑(*参):
    r = subprocess.run([sys.executable, str(工具), *map(str, 参)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


文 = docx.Document()
文.add_paragraph("正文：客户张伟，电话 13812345678")
节 = 文.sections[0]
节.header.paragraphs[0].text = "页眉：合同编号 11010519491231002X"
节.footer.paragraphs[0].text = "页脚：联系人 13900002222"

源 = 临 / "合同.docx"
文.save(str(源))

码, 出 = 跑("preview", 源)
print("== 预览 ==")
print(出.strip()[:600])

码, 出 = 跑("redact", 源)
脱 = 临 / "合同.redacted.docx"
读 = docx.Document(str(脱))
头 = 读.sections[0].header.paragraphs[0].text
脚 = 读.sections[0].footer.paragraphs[0].text
正 = 读.paragraphs[0].text
print("\n== 脱敏后 ==")
print("  页眉：", 头)
print("  页脚：", 脚)
print("  正文：", 正)

好1 = ("11010519491231002X" not in 头) and ("[ID_" in 头)
好2 = ("13900002222" not in 脚) and ("[PHONE_" in 脚)
好3 = "[PHONE_1]" in 正 or "[PHONE_" in 正

码, 出 = 跑("restore", 脱, "--map", 临 / "合同.map.json")
还 = docx.Document(str(临 / "合同.redacted.restored.docx"))
头2 = 还.sections[0].header.paragraphs[0].text
脚2 = 还.sections[0].footer.paragraphs[0].text
print("\n== 还原后 ==")
print("  页眉：", 头2)
print("  页脚：", 脚2)
好4 = "11010519491231002X" in 头2 and "13900002222" in 脚2

print("\n页眉挡住:", 好1, "｜页脚挡住:", 好2, "｜正文挡住:", 好3, "｜还原回去:", 好4)
print("结论：", "过" if all((好1, 好2, 好3, 好4)) else "没过")
sys.exit(0 if all((好1, 好2, 好3, 好4)) else 1)
