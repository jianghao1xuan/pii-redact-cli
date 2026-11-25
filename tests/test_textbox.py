# -*- coding: utf-8 -*-
"""验文本框：在 docx 里插一个 w:txbxContent，看号码能不能挡住、能不能还原。"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import docx  # noqa: E402
from docx.oxml import parse_xml  # noqa: E402
from docx.oxml.ns import nsdecls  # noqa: E402

根 = Path(__file__).resolve().parent.parent
工具 = 根 / "pii_tool.py"
临 = Path(tempfile.mkdtemp(prefix="tbx_"))


def 跑(*参):
    r = subprocess.run([sys.executable, str(工具), *map(str, 参)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


文 = docx.Document()
文.add_paragraph("正文：电话 13812345678")

# 手搓一个文本框节点塞进正文
tbx = parse_xml(
    f'<w:p {nsdecls("w")}><w:r><w:pict><v:shape xmlns:v="urn:schemas-microsoft-com:vml">'
    f'<v:textbox><w:txbxContent><w:p><w:r><w:t>文本框联系人 13900002222</w:t></w:r></w:p>'
    f'</w:txbxContent></v:textbox></v:shape></w:pict></w:r></w:p>')
文.element.body.append(tbx)

源 = 临 / "带文本框.docx"
文.save(str(源))

码, 出 = 跑("preview", 源)
print("== 预览 ==")
print(出.strip()[:500])

码, 出 = 跑("redact", 源)
脱 = 临 / "带文本框.redacted.docx"
读 = docx.Document(str(脱))
全文 = "\n".join(p.text for p in 读.paragraphs)
from docx.oxml.ns import qn  # noqa: E402
节点 = [t.text for t in 读.element.body.iter(qn("w:t")) if t.text]
print("\n== 脱敏后 ==")
print("  段落：", 全文)
print("  所有文本节点：", 节点)

好 = not any("13900002222" in (x or "") for x in 节点)
print("\n文本框里的号挡住：", 好)
