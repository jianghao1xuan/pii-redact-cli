# pii-redact-cli

命令行中文脱敏工具：把文件里的手机号、身份证、银行卡这些换成占位符，需要时再换回来。

**不需要 Open WebUI，也不需要联网**，装个 Python 就能跑。处理和还原都在你自己电脑上完成，一个字节都不出去。

> **这一版只覆盖八类有规则的写法，处理过的内容请复核一遍。**

---

## 装

需要 **Python 3.8 或更高**，没有第三方依赖。

- Windows：到 https://www.python.org/downloads/ 下最新版，安装时**把「Add Python to PATH」勾上**
- macOS / Linux：一般自带

处理 `.xlsx` 需要额外装一个库：

```bash
pip install openpyxl
```

---

## 用

三条命令，都在文件所在目录执行：

```bash
# 1. 先看会改哪几处（不动文件）
python pii_tool.py preview 客户.csv

# 2. 出脱敏版 + 映射表
python pii_tool.py redact 客户.csv

# 3. 需要时还原
python pii_tool.py restore 客户.redacted.csv --map 客户.map.json
```

`redact` 会生成两个文件：`客户.redacted.csv`（给 AI 看的）和 `客户.map.json`（把占位符换回真值的钥匙）。

实际跑起来是这样：

```
这张表里换掉 4 处：
  PHONE       2 处
  TEL         1 处
  PLATE       1 处

脱敏版 → 客户.redacted.csv
映射表 → 客户.map.json

姓名,手机,订单
张伟,[PHONE_1],20261124001
李娜,[PHONE_2],20261124002
```

订单号、日期、金额这些不会被误伤。

**映射表里是真值**，别外传，用完删掉。还原是逐字的（`+86 139-0000-2222` 还原回来连横杠都在）。

---

## 支持

`.txt`、`.md`、`.csv`（逐格，不动分隔符）、`.xlsx`（逐格，需要 openpyxl）。

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

## 和 Open WebUI 那个插件的关系

两个独立项目，用户不重叠：

- **这个**：处理文件，命令行，不联网
- **[openwebui-pii-redact](https://github.com/jianghao1xuan/openwebui-pii-redact)**：Open WebUI 的插件，聊天时自动拦

规则同源、各自维护，互不依赖——你不用装 Open WebUI 才能用它。

---

## 自己验

```bash
python tests/test_rules.py   # 十三种写法、六种不该误伤、同号复用
python tests/test_tool.py    # txt / csv 的文件级流程
```

预期：`应挡 13/13｜误伤 0/6｜同号复用 True`、`文件级全过`。

---

## 反馈

发现漏挡或误伤，把**脱敏后**的样子贴出来（别贴真号），到 [Issues](https://github.com/jianghao1xuan/pii-redact-cli/issues) 说一声。

如果你**不会装 Python**、又确实想用，也开个 Issue 说一句——我再看要不要打包成 exe。

## 许可

MIT，见 [LICENSE](LICENSE)。
