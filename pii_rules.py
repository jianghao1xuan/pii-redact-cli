# -*- coding: utf-8 -*-
"""规则本体：认什么、怎么校验、怎么编号、怎么还原。

这一份和 Open WebUI 插件那份是同源规则（插件仓库 openwebui-pii-redact），
但这里**不依赖 Open WebUI，也不依赖 pydantic**，只靠标准库。

改动规则时两边都要改，各自的测试会挡。
"""
import re

# 占位符里的类型名，还原时也认这些
类型 = ("PHONE", "ID", "BANK", "EMAIL", "TEL", "PLATE", "USCC", "PASSPORT")


def 新场() -> dict:
    """一场 = 一份映射。处理一个文件用一个场。"""
    return {"n": {}, "map": {}, "键": {}}


class 规则:
    # ---------- 正则 ----------
    _手机 = re.compile(r"(?<![\d])(?:\+?86[\s\-]?)?1[3-9](?:[\s\-]?\d){9}(?!\d)")
    _身份证 = re.compile(r"(?<![\d])\d{6}(?:[\s\-]?\d){11}[\dXx](?![\d])")
    _身份证15 = re.compile(r"(?<![\d])\d{6}(?:[\s\-]?\d){9}(?![\d])")
    _银行卡 = re.compile(r"(?<![\d])\d{4}(?:[\s\-]?\d){12,15}(?![\d])")
    _邮箱 = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
    _固话 = re.compile(r"(?<![\d])(?:\(0\d{2,3}\)|0\d{2,3})[\s\-]?\d{7,8}(?![\d])")
    _客服电话 = re.compile(r"(?<![\d])(?:400|800)[\s\-]?\d{3}[\s\-]?\d{4}(?![\d])")
    _车牌 = re.compile(
        r"(?<![A-Za-z0-9\u4e00-\u9fa5])"
        r"[京津冀晋蒙辽吉黑沪苏浙皖闽赣鲁豫鄂湘粤桂琼渝川贵云藏陕甘青宁新]"
        r"[A-HJ-NP-Z][A-HJ-NP-Z0-9]{4,5}[A-HJ-NP-Z0-9挂学警港澳]"
        r"(?![A-Za-z0-9])")
    _统一代码 = re.compile(r"(?<![0-9A-Z])[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}(?![0-9A-Z])")
    _护照 = re.compile(r"(?<![0-9A-Za-z])[EG]\d{8}(?![0-9A-Za-z])")

    # ---------- 校验 ----------
    @staticmethod
    def 身份证对(号: str) -> bool:
        权 = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
        码 = "10X98765432"
        try:
            和 = sum(int(号[i]) * 权[i] for i in range(17))
        except ValueError:
            return False
        return 码[和 % 11] == 号[17].upper()

    @staticmethod
    def 统一代码对(码: str) -> bool:
        字 = "0123456789ABCDEFGHJKLMNPQRTUWXY"
        权 = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)
        try:
            和 = sum(字.index(码[i]) * 权[i] for i in range(17))
        except ValueError:
            return False
        return 码[17] == 字[(31 - 和 % 31) % 31]

    @staticmethod
    def 银行卡对(号: str) -> bool:
        总 = 0
        for i, ch in enumerate(reversed(号)):
            数 = int(ch)
            if i % 2 == 1:
                数 *= 2
                if 数 > 9:
                    数 -= 9
            总 += 数
        return 总 % 10 == 0

    @staticmethod
    def 日期像样(月日: str) -> bool:
        try:
            月, 日 = int(月日[:2]), int(月日[2:])
        except ValueError:
            return False
        return 1 <= 月 <= 12 and 1 <= 日 <= 31

    @staticmethod
    def 只留数字(文: str) -> str:
        return re.sub(r"\D", "", 文)

    # ---------- 编号 ----------
    @staticmethod
    def 占位(场: dict, 类: str, 原: str, 归一: str = "") -> str:
        键值 = (类, 归一 or 原)
        已 = 场.setdefault("键", {})
        if 键值 in 已:
            return 已[键值]
        场["n"][类] = 场["n"].get(类, 0) + 1
        键 = f"[{类}_{场['n'][类]}]"
        场["map"][键] = 原
        已[键值] = 键
        return 键

    # ---------- 脱敏 ----------
    def 脱一段(self, 文: str, 场: dict) -> str:
        if not isinstance(文, str) or not 文:
            return 文
        占 = self.占位

        def 换身份证(m):
            段 = m.group(0)
            数 = re.sub(r"[^\dXx]", "", 段).upper()
            if len(数) == 18 and self.身份证对(数):
                return 占(场, "ID", 段, 数)
            if len(数) == 15 and self.日期像样(数[8:12]):
                return 占(场, "ID", 段, 数)
            return 段

        def 换卡(m):
            段 = m.group(0)
            数 = self.只留数字(段)
            if 16 <= len(数) <= 19 and self.银行卡对(数):
                return 占(场, "BANK", 段, 数)
            return 段

        def 换手机(m):
            段 = m.group(0)
            数 = self.只留数字(段)
            尾 = 数[-11:]
            if len(尾) == 11 and 尾[0] == "1":
                return 占(场, "PHONE", 段, 尾)
            return 段

        文 = self._邮箱.sub(lambda m: 占(场, "EMAIL", m.group(0)), 文)
        文 = self._身份证.sub(换身份证, 文)
        文 = self._身份证15.sub(换身份证, 文)
        文 = self._银行卡.sub(换卡, 文)
        文 = self._手机.sub(换手机, 文)
        文 = self._统一代码.sub(
            lambda m: 占(场, "USCC", m.group(0)) if self.统一代码对(m.group(0)) else m.group(0), 文)
        文 = self._固话.sub(lambda m: 占(场, "TEL", m.group(0)), 文)
        文 = self._客服电话.sub(lambda m: 占(场, "TEL", m.group(0)), 文)
        文 = self._车牌.sub(lambda m: 占(场, "PLATE", m.group(0)), 文)
        文 = self._护照.sub(lambda m: 占(场, "PASSPORT", m.group(0)), 文)
        return 文

    # ---------- 还原 ----------
    def 还原一段(self, 文: str, 场: dict) -> str:
        if not isinstance(文, str) or not 文:
            return 文
        for k, v in 场["map"].items():
            if k in 文:
                文 = 文.replace(k, v)

        def 换(m):
            键 = f"[{m.group(1)}_{m.group(2)}]"
            return 场["map"].get(键, m.group(0))

        文 = re.sub(r"\[\s*(PHONE|ID|BANK|EMAIL|TEL|PLATE|USCC|PASSPORT)\s*_\s*(\d+)\s*\]", 换, 文)
        return 文
