"""mktdata — 多市场、多数据源、自动 fallback 的只读 Market Data Library + CLI。

职责边界：只提供市场数据访问层（数据源 / 代码识别 / 归一化 / 路由 / 质量 / provenance）。
不包含：Qlib、因子框架、回测、策略、交易、模型训练。
"""

from .errors import (
    MktDataError,
    InvalidParameter,
    InvalidSymbol,
    ProviderAuthError,
    ProviderDataEmpty,
    ProviderRateLimited,
    ProviderUnavailable,
    ProviderUnsupported,
)
from .models import Adjust, DataResult, Market, Period, SecurityType, Symbol
from .symbols import detect_market, is_hk, is_us, normalize_symbol

__version__ = "1.1.0"

__all__ = [
    "__version__",
    "MktDataError", "InvalidParameter", "InvalidSymbol",
    "ProviderAuthError", "ProviderDataEmpty", "ProviderRateLimited",
    "ProviderUnavailable", "ProviderUnsupported",
    "Adjust", "DataResult", "Market", "Period", "SecurityType", "Symbol",
    "detect_market", "is_hk", "is_us", "normalize_symbol",
]
