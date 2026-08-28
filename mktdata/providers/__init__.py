"""mktdata providers — 每个数据源一个独立模块（Step 2）。

- hithink: 同花顺 REST API（行情/财务/指标/估值）
- miniqmt: 本机 xtquant/xtdata（A股+港股行情、A股财务/估值）
- tdx: 通达信 easy-tdx（A股日线/分钟/PB/资金流向）
- yahoo: Yahoo Finance（美股日线）
- akshare: 东财/同花顺/新浪/雪球（港股日线/美股/港股F10/A股摘要）

provider 只负责"取数 + 边界归一化"；路由 / fallback 见 mktdata.router（Step 3）。
"""

from .hithink import (  # noqa: F401
    HITHINK_BASE,
    HITHINK_IND,
    HITHINK_KEY_FILE,
    HITHINK_STMT,
    hithink_financial,
    hithink_history,
    hithink_indicators,
    hithink_valuation,
)
from .miniqmt import (  # noqa: F401
    MINIQMT_STMT,
    miniqmt_calendar,
    miniqmt_corporate_actions,
    miniqmt_financial,
    miniqmt_history,
    miniqmt_indicators,
    miniqmt_instrument,
    miniqmt_sector,
    miniqmt_valuation,
)
from .tdx import tdx_fundflow, tdx_history, tdx_valuation  # noqa: F401
from .yahoo import yahoo_history  # noqa: F401
from .akshare import ak_f10, ak_hk_history, ak_us_history  # noqa: F401
