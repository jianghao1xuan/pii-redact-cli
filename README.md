# pii-redact-cli

命令行中文脱敏工具：把文件里的手机号、身份证、银行卡这些换成占位符，需要时再换回来。

**纯命令行，不要服务器、不要账号、不连网**——处理和还原都在你自己电脑上完成，一个字节都不出去。

依赖分三档，看你要处理什么：

| 处理什么 | 要装什么 |
|---|---|
| `.txt` / `.md` / `.csv` | **只要 Python**，不用装别的 |
| `.xlsx`（Excel） | 再装 `openpyxl` |
| `.docx`（Word） | 再装 `python-docx` |

> **这一版只覆盖八类有规则的写法，处理过的内容请复核一遍。**

---

## 装

先要 **Python 3.8 或更高**：

- Windows：到 https://www.python.org/downloads/ 下最新版，安装时**把「Add Python to PATH」勾上**
- macOS / Linux：一般自带

然后按你要处理的文件，决定要不要再装库：

```bash
# 只处理 txt / csv / md —— 到此为止，不用再装
python pii_tool.py preview 客户.csv

# 要处理 Excel
pip install openpyxl

# 要处理 Word
pip install python-docx
```

没装对应的库时，它会直接告诉你缺哪个、怎么装，不会静默失败。

---

## 用

三条命令，都在文件所在目录执行：

```bash
# 1. 先看会改哪几处（不动文件）
python pii_tool.py preview 客户.csv

# 2. 出脱敏版 + 映射表（.txt .md .csv .xlsx .docx 都行）
python pii_tool.py redact 客户.docx

# 3. 需要时还原
python pii_tool.py restore 客户.redacted.csv --map 客户.map.json
```

`redact` 会生成两个文件：`客户.redacted.csv`（给 AI 看的）和 `客户.map.json`（把占位符换回真值的钥匙）。

实际跑起来是这样：

```
读入：客户.csv（编码 gb18030）
换掉 4 处：
  PHONE       2 处
  TEL         1 处
  PLATE       1 处

明细（位置 / 原文 / 换成了）：
  第 2 行 第 2 列            13812345678                  → [PHONE_1]
  第 3 行 第 2 列            +86 139-0000-2222            → [PHONE_2]
  第 3 行 第 3 列            0571-88888888                → [TEL_1]
  第 4 行 第 3 列            京A12345                     → [PLATE_1]

⚠ 这 2 处像敏感信息，但校验没过，我没动——请自己看一眼：
  第 5 行 第 2 列            4111111111111112             （像银行卡，但 Luhn 校验不过）
  第 5 行 第 3 列            110105194912310021           （18 位、但校验位不对）
```

几个要紧的地方：

- **编码自动认**：UTF-8、GBK/GB18030、Big5 都试，读进来是什么编码，写出去也是什么编码。GBK 的 CSV 不会变乱码。
- **位置说清楚**：第几行第几列，表格用 `[工作表] 第 n 行 第 m 列`，对得上表。
- **"像但不对"单独列**：卡号差一位、身份证校验位错，它不会硬改，而是列出来让你自己看——**不然这种就是漏**。
- **Excel 所有 sheet 都处理**，不是只看第一个。

**映射表里是真值**，别外传，用完删掉。还原是逐字的（`+86 139-0000-2222` 还原回来连横杠都在）。

---

## 支持

`.txt`、`.md`、`.csv`（逐格，不动分隔符）、`.xlsx` / `.xlsm`（逐格，所有 sheet）、`.docx`（段落 + 表格）。

- Excel 要 `openpyxl`：`pip install openpyxl`
- Word 要 `python-docx`：`pip install python-docx`

编码自动识别：UTF-8（含 BOM）、GBK / GB18030、Big5。读进来什么编码，写出去还是什么编码。

**Word 的一个小心事**：改过的段落会把文字并到第一个 run 里——段落样式（标题、行距）还在，但段内局部的加粗、颜色会丢。要连这点也保住，得逐 run 拼位置，容易出错，这一版没做。

**还不支持**：PDF、图片。图片要先 OCR，认出来的字和原图对不上，做不到"改完还能还原"，所以不放进这个工具。

识别八类，带校验，不是看见数字就换：

| 类型 | 占位符 | 例子 |
|---|---|---|
| 手机号 | `[PHONE_n]` | `+86 138 0000 6666`、`138-0000-7777` |
| 身份证 18 位 | `[ID_n]` | `11010519491231002X`（校验位） |
| 老身份证 15 位 | `[ID_n]` | `110105491231003` |
| 银行卡 | `[BANK_n]` | `4111 1111 1111 1111`（Luhn） |
| 邮箱 | `[EMAIL_n]` | `a.b@example.com` |
| 固话 / 400 | `[TEL_n]` | `0571-88888888`、`400-123-4567` |
| 车牌 | `[PLATE_n]` | `京A12345`、`粤BD12345` |
| 统一社会信用代码 | `[USCC_n]` | `91350100M000100Y43`（GB 32100 校验） |
| 护照 | `[PASSPORT_n]` | `E12345678` |

**不做**：姓名、地址、公司名、金额、IP、QQ/微信。

---

## 自己验

```bash
python tests/test_rules.py         # 十三种写法、六种不该误伤、同号复用
python tests/test_tool.py          # txt / csv 的文件级流程
python tests/test_improvements.py  # GBK 编码、行列位置、可疑清单、多 sheet
python tests/test_docx.py          # Word：段落、表格、还原
python tests/test_edge.py          # 边角：不支持的类型、空文件、重复跑、中文路径
```

预期：`应挡 13/13｜误伤 0/6｜同号复用 True`、`文件级全过`、最后一段能看到 GBK 被正确识别、明细带行列号、多 sheet 都在。

---

## 反馈

发现漏挡或误伤，把**脱敏后**的样子贴出来（别贴真号），到 [Issues](https://github.com/jianghao1xuan/pii-redact-cli/issues) 说一声。

如果你**不会装 Python**、又确实想用，也开个 Issue 说一句——我再看要不要打包成 exe。

## 许可

MIT，见 [LICENSE](LICENSE)。
