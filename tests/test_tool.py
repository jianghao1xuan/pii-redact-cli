# -*- coding: utf-8 -*-
"""文件级自测：txt / csv 的预览、脱敏、还原。"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
根 = Path(__file__).resolve().parent.parent
工具 = 根 / "pii_tool.py"
临 = Path(tempfile.mkdtemp(prefix="pii_cli_"))


def 跑(*参):
    r = subprocess.run([sys.executable, str(工具), *map(str, 参)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


原文 = "张伟 13812345678\n李娜 +86 139-0000-2222\n固话 0571-88888888 车牌 京A12345 订单 20261124001\n"
源 = 临 / "客户.txt"
源.write_text(原文, encoding="utf-8")

码, 出 = 跑("preview", 源)
print("== preview ==")
print(出.strip())
assert 码 == 0 and "4 处" in 出

码, 出 = 跑("redact", 源)
脱 = 临 / "客户.redacted.txt"
映 = 临 / "客户.map.json"
assert 脱.is_file() and 映.is_file()
内容 = 脱.read_text(encoding="utf-8")
print("\n== 脱敏后 ==")
print(内容.strip())
assert "13812345678" not in 内容 and "[PHONE_1]" in 内容
assert "20261124001" in 内容, "订单号不该被动"

码, 出 = 跑("restore", 脱, "--map", 映)
还 = 临 / "客户.redacted.restored.txt"
print("\n== 还原 ==", 出.strip())
print("逐字一致：", 还.read_text(encoding="utf-8") == 原文)
assert 还.read_text(encoding="utf-8") == 原文

# csv
表 = 临 / "客户.csv"
表.write_text("姓名,手机,订单\n张伟,13812345678,20261124001\n李娜,13900002222,20261124002\n",
              encoding="utf-8-sig")
码, 出 = 跑("redact", 表)
表脱 = 临 / "客户.redacted.csv"
print("\n== csv ==")
print(表脱.read_text(encoding="utf-8-sig").strip())
assert "[PHONE_1]" in 表脱.read_text(encoding="utf-8-sig")

print("\n文件级全过")
