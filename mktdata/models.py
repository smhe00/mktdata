"""mktdata 通用结果结构与枚举。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Market(str, Enum):
    CN = "CN"
    HK = "HK"
    US = "US"


class SecurityType(str, Enum):
    STOCK = "stock"
    INDEX = "index"
    ETF = "etf"
    FUND = "fund"
    OTHER = "other"


class Period(str, Enum):
    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    MIN_60 = "60m"
    DAY = "1d"
    WEEK = "week"
    MONTH = "month"


class Adjust(str, Enum):
    NONE = "none"   # 原始价
    FRONT = "front"  # 前复权（最近价对齐）
    BACK = "back"    # 后复权（早期价对齐，含分红送转；不含回购）


@dataclass(frozen=True)
class Symbol:
    code: str        # 纯代码，如 600519 / 00700 / AAPL
    exchange: str    # SH / SZ / BJ / HK / US
    market: str      # CN / HK / US
    canonical: str   # 规范代码，如 600519.SH


@dataclass
class DataResult:
    data: Any
    source: str
    ok: bool = True
    error: Optional[str] = None
    fallback_chain: Optional[List[Dict[str, str]]] = None
    requested_source: str = "auto"  # 用户请求的源（P0-7）；缺省 auto

    def provenance(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "requested_source": self.requested_source,
            "fallback_chain": self.fallback_chain or [],
        }


# history 统一输出字段（canonical schema，P0-1）
HISTORY_FIELDS = [
    "symbol", "datetime", "open", "high", "low", "close",
    "volume", "amount", "source",
]

# 语义约定（P0-2）：
#   volume: 统一为 shares（股）。provider 在边界转换（miniQMT 原为"手"×100）。
#   amount: 统一为成交额（本市场货币）。
#   datetime: 日线 YYYY-MM-DD；分钟 YYYY-MM-DD HH:MM。
#   缺失值: 用 None / NaN，禁止用 0 顶替缺失行情。
