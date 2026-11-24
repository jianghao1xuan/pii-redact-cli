# -*- coding: utf-8 -*-
"""工具版的全量自检：边角、错误处理、还原、幂等。

跑法：python tests/test_edge.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
根 = Path(__file__).resolve().parent.parent
工具 = 根 / "pii_tool.py"
临 = Path(tempfile.mkdtemp(prefix="pii_edge_"))
错 = []


def 跑(*参):
    r = subprocess.run([sys.executable, str(工具), *map(str, 参)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def 查(名, 条件, 附=""):
    print(("✓ " if 条件 else "✗ ") + 名 + (f"｜{附}" if 附 and not 条件 else ""))
    if not 条件:
        错.append(名)


# 1 不支持的类型要明确报错，不能"假装成功"
p = 临 / "x.pdf"
p.write_bytes(b"%PDF-1.4 13812345678")
码, 出 = 跑("preview", p)
查("PDF 明确报错", 码 != 0 and "不支持" in 出, 出[:80])

# 2 空文件
e = 临 / "空.txt"
e.write_text("", encoding="utf-8")
码, 出 = 跑("redact", e)
查("空文件不崩", 码 == 0 and "0 处" in 出, 出[:80])

# 3 没有任何敏感信息
n = 临 / "干净.txt"
n.write_text("今天开工，订单一千二。\n", encoding="utf-8")
码, 出 = 跑("redact", n)
查("干净文件 0 处", 码 == 0 and "0 处" in 出)

# 4 重复跑幂等：对已脱敏的文件再跑一次，不该再改
源 = 临 / "原.txt"
原文 = "张伟 13812345678 卡 4111 1111 1111 1111\n"
源.write_text(原文, encoding="utf-8")
跑("redact", 源)
一次 = (临 / "原.redacted.txt").read_text(encoding="utf-8")
码, 出 = 跑("redact", 临 / "原.redacted.txt")
二次 = (临 / "原.redacted.redacted.txt").read_text(encoding="utf-8")
查("重复脱敏不变形", 一次 == 二次, f"{一次!r} vs {二次!r}")

# 5 还原精确（带空格横杠）
说, 还 = 临 / "还原.txt", None
说.write_text("电话 +86 139-0000-2222 车牌 粤BD12345\n", encoding="utf-8")
跑("redact", 说)
跑("restore", 临 / "还原.redacted.txt", "--map", 临 / "还原.map.json")
还 = (临 / "还原.redacted.restored.txt").read_text(encoding="utf-8")
查("还原逐字一致", 还 == 说.read_text(encoding="utf-8"), repr(还))

# 6 中文目录 + 空格路径
夹 = 临 / "客户 资料" / "十一月"
夹.mkdir(parents=True)
f = 夹 / "名单 表.txt"
f.write_text("李娜 13700002222\n", encoding="utf-8")
码, 出 = 跑("redact", f)
查("中文/空格路径能跑", 码 == 0 and (夹 / "名单 表.redacted.txt").is_file(), 出[:80])

# 7 GBK 文本
g = 临 / "gbk.txt"
g.write_bytes("王强 13600001111\n".encode("gbk"))
码, 出 = 跑("redact", g)
还原后 = (临 / "gbk.redacted.txt").read_bytes().decode("gbk")
查("GBK 文本读得对", "[PHONE_1]" in 还原后, 还原后)

# 8 缺少映射表要报错
码, 出 = 跑("restore", 临 / "原.redacted.txt")
查("还原缺 --map 报错", 码 != 0 and "映射表" in 出)

# 9 文件不存在
码, 出 = 跑("preview", 临 / "没有这个.txt")
查("文件不存在报错", 码 != 0 and "找不到" in 出)

# 10 一次多种类型
多 = 临 / "多.txt"
多.write_text("手机 13812345678，固话 0571-88888888，车牌 京A12345，护照 E12345678，"
              "信用代码 91350100M000100Y43，邮箱 a@b.com，身份证 11010519491231002X，"
              "卡 4111 1111 1111 1111\n", encoding="utf-8")
码, 出 = 跑("preview", 多)
类数 = sum(1 for x in ("PHONE", "TEL", "PLATE", "PASSPORT", "USCC", "EMAIL", "ID", "BANK") if x in 出)
查("八类一次全认", 类数 == 8, f"只认出 {类数} 类")

# 11 大文件：5000 行要在 5 秒内（以前是逐格重扫全表，2 万行要半分钟）
import csv  # noqa: E402
import time  # noqa: E402

大 = 临 / "大表.csv"
with 大.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["姓名", "手机", "订单"])
    for i in range(5000):
        w.writerow([f"客户{i}", f"138{i:08d}", f"2026{i:04d}"])
起 = time.time()
码, 出 = 跑("redact", 大)
用时 = time.time() - 起
查("5000 行 5 秒内", 码 == 0 and 用时 < 5 and "5000 处" in 出, f"{用时:.1f} 秒")

print("\n失败：", 错 if 错 else "无")
sys.exit(1 if 错 else 0)