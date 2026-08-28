"""证券代码 / 市场识别与规范化。

所有 provider 一律通过本模块识别市场，禁止散落 endswith(".SH") 判断。
"""

import re

from .errors import InvalidSymbol
from .models import Symbol

_SH = re.compile(r"^(\d{6})\.SH$", re.I)
_SZ = re.compile(r"^(\d{6})\.SZ$", re.I)
_BJ = re.compile(r"^(\d{6})\.BJ$", re.I)
_HK = re.compile(r"^(\d{5})\.HK$", re.I)
_US = re.compile(r"^([A-Za-z][A-Za-z.\-]{0,9})\.US$", re.I)


def normalize_symbol(symbol: str) -> Symbol:
    """把输入规范化成 Symbol。非法代码抛 InvalidSymbol。"""
    s = (symbol or "").strip().upper()
    if not s:
        raise InvalidSymbol("代码为空")
    for pat, exchange, market in (
        (_SH, "SH", "CN"),
        (_SZ, "SZ", "CN"),
        (_BJ, "BJ", "CN"),
        (_HK, "HK", "HK"),
        (_US, "US", "US"),
    ):
        m = pat.match(s)
        if m:
            code = m.group(1)
            return Symbol(code=code, exchange=exchange, market=market, canonical=f"{code}.{exchange}")
    raise InvalidSymbol(f"无法识别证券代码: {symbol!r}")


def detect_market(symbol: str) -> str:
    """返回市场：CN / HK / US。"""
    return normalize_symbol(symbol).market


def is_hk(symbol: str) -> bool:
    return (symbol or "").upper().endswith(".HK")


def is_us(symbol: str) -> bool:
    return (symbol or "").upper().endswith(".US")
