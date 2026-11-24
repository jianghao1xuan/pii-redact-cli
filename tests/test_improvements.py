# -*- coding: utf-8 -*-
"""三件新东西的验收：GBK 编码、行列位置、可疑清单、多 sheet。"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
根 = Path(__file__).resolve().parent.parent
工具 = 根 / "pii_tool.py"
临 = Path(tempfile.mkdtemp(prefix="pii_new_"))


def 跑(*参):
    r = subprocess.run([sys.executable, str(工具), *map(str, 参)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# 1) GBK 编码的 CSV
表 = 临 / "gbk表.csv"
表.write_bytes("姓名,手机,订单\n张伟,13812345678,20261124001\n".encode("gbk"))
码, 出 = 跑("redact", 表)
print("== GBK ==")
print(出.strip()[:300])
脱 = 临 / "gbk表.redacted.csv"
print("脱敏后（按 gbk 读）：", 脱.read_bytes().decode("gbk").strip())

# 2) 行列位置 + 可疑清单
表2 = 临 / "可疑.csv"
表2.write_text("姓名,卡号,身份证,订单\n"
               "张伟,4111111111111111,11010519491231002X,20261124001\n"
               "李娜,4111111111111112,110105194912310021,20261124002\n",
               encoding="utf-8")
码, 出 = 跑("preview", 表2)
print("\n== 位置 + 可疑 ==")
print(出.strip())

# 3) 多 sheet
try:
    import openpyxl
    书 = openpyxl.Workbook()
    一 = 书.active
    一.title = "客户"
    一.append(["姓名", "手机"])
    一.append(["张伟", "13812345678"])
    二 = 书.create_sheet("备用")
    二.append(["姓名", "邮箱"])
    二.append(["李娜", "li@example.com"])
    p = 临 / "多表.xlsx"
    书.save(p)
    码, 出 = 跑("redact", p)
    print("\n== 多 sheet ==")
    print(出.strip()[:400])
    后 = openpyxl.load_workbook(临 / "多表.redacted.xlsx")
    print("工作表：", 后.sheetnames)
    for 名 in 后.sheetnames:
        print(" ", 名, [[c for c in r] for r in 后[名].iter_rows(values_only=True)])
except ImportError:
    print("\n（没装 openpyxl，多 sheet 那步跳过）")
