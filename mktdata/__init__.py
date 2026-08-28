"""mktdata — 多市场、多数据源、自动 fallback 的只读 Market Data Library + CLI。

职责边界：只提供市场数据访问层（数据源 / 代码识别 / 归一化 / 路由 / 质量 / provenance）。
不包含：Qlib、因子框架、回测、策略、交易、模型训练。

用法:
    from mktdata import MarketData          # Step 4 统一 API（开发中）
    from mktdata.providers import hithink  # 或直接 provider 层
    from mktdata import normalize_symbol, hithink_history  # 顶层便捷导出
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
from .normalize import norm_date_ms, norm_date_ymd, norm_dt_ymd, norm_num, to_ms_utc

# provider 顶层便捷导出（过渡期兼容：`import mktdata; mktdata.hithink_history(...)`）
from .providers.hithink import (  # noqa: F401,E402
    hithink_financial,
    hithink_history,
    hithink_indicators,
    hithink_valuation,
)
from .providers.miniqmt import (  # noqa: F401,E402
    miniqmt_financial,
    miniqmt_history,
    miniqmt_indicators,
    miniqmt_valuation,
)
from .providers.tdx import tdx_fundflow, tdx_history, tdx_valuation  # noqa: F401,E402
from .providers.yahoo import yahoo_history  # noqa: F401,E402
from .providers.akshare import ak_f10, ak_hk_history, ak_us_history  # noqa: F401,E402
from .api import MarketData  # noqa: F401,E402
from .capabilities import PROVIDER_CAPABILITIES, supports  # noqa: F401,E402

__version__ = "1.1.0"

__all__ = [
    "__version__",
    "MarketData",
    "PROVIDER_CAPABILITIES", "supports",
    "MktDataError", "InvalidParameter", "InvalidSymbol",
    "ProviderAuthError", "ProviderDataEmpty", "ProviderRateLimited",
    "ProviderUnavailable", "ProviderUnsupported",
    "Adjust", "DataResult", "Market", "Period", "SecurityType", "Symbol",
    "detect_market", "is_hk", "is_us", "normalize_symbol",
    "norm_date_ms", "norm_date_ymd", "norm_dt_ymd", "norm_num", "to_ms_utc",
    "hithink_financial", "hithink_history", "hithink_indicators", "hithink_valuation",
    "miniqmt_financial", "miniqmt_history", "miniqmt_indicators", "miniqmt_valuation",
    "tdx_fundflow", "tdx_history", "tdx_valuation",
    "yahoo_history",
    "ak_f10", "ak_hk_history", "ak_us_history",
]
