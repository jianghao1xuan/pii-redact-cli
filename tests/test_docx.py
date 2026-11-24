# -*- coding: utf-8 -*-
"""Word 支持：段落 + 表格都要能改，也要能还原。"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
根 = Path(__file__).resolve().parent.parent
工具 = 根 / "pii_tool.py"
临 = Path(tempfile.mkdtemp(prefix="pii_docx_"))


def 跑(*参):
    r = subprocess.run([sys.executable, str(工具), *map(str, 参)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


import docx  # noqa: E402

文 = docx.Document()
文.add_heading("客户名单", level=1)
文.add_paragraph("张伟，电话 13812345678，邮箱 zw@example.com")
文.add_paragraph("李娜，电话 +86 139-0000-2222，卡号 4111 1111 1111 1111")
表 = 文.add_table(rows=2, cols=3)
表.cell(0, 0).text = "姓名"
表.cell(0, 1).text = "手机"
表.cell(0, 2).text = "订单"
表.cell(1, 0).text = "王强"
表.cell(1, 1).text = "13700003333"
表.cell(1, 2).text = "20261124001"
源 = 临 / "客户.docx"
文.save(str(源))

码, 出 = 跑("preview", 源)
print("== preview ==")
print(出.strip())
assert "预览" in 出 and "[PHONE_1]" in 出

码, 出 = 跑("redact", 源)
脱 = 临 / "客户.redacted.docx"
映 = 临 / "客户.map.json"
assert 脱.is_file(), 出
读 = docx.Document(str(脱))
正文 = "\n".join(p.text for p in 读.paragraphs)
格 = " ".join(c.text for r in 读.tables[0].rows for c in r.cells)
print("\n== 脱敏后正文 ==")
print(正文)
print("表格：", 格)
assert "13812345678" not in 正文 and "[PHONE_1]" in 正文
assert "4111 1111 1111 1111" not in 正文 and "[BANK_1]" in 正文
assert "13700003333" not in 格 and "[PHONE_3]" in 格
assert "20261124001" in 格, "订单号不该被动"

码, 出 = 跑("restore", 脱, "--map", 映)
还 = docx.Document(str(临 / "客户.redacted.restored.docx"))
还正 = "\n".join(p.text for p in 还.paragraphs)
还格 = " ".join(c.text for r in 还.tables[0].rows for c in r.cells)
print("\n== 还原 ==")
print(还正)
print("表格：", 还格)
assert "13812345678" in 还正 and "4111 1111 1111 1111" in 还正
assert "13700003333" in 还格

print("\nWord 全过")
