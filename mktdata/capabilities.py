"""静态 Provider Capability 描述（P1L-4）。

统一、可查询、静态的能力表；supports() 供下游/README 引用。
本模块不引入插件系统 / ABC / 动态注册（超范围）。

capability: history / financial / indicators / valuation / calendar /
            instrument / corporate_actions / sector
"""

PROVIDER_CAPABILITIES = {
    "hithink": {
        "history": {"markets": {"CN"}, "periods": {"1d"}},
        "financial": {"markets": {"CN"}},
        "indicators": {"markets": {"CN"}},
        "valuation": {"markets": {"CN"}},
    },
    "miniqmt": {
        "history": {"markets": {"CN", "HK"}, "periods": {"1d", "1m", "5m", "15m", "30m", "60m"}},
        "financial": {"markets": {"CN"}},
        "indicators": {"markets": {"CN"}},
        "valuation": {"markets": {"CN"}},
        "calendar": {"markets": {"CN", "HK"}, "note": "CN=SH/SZ"},
        "instrument": {},
        "corporate_actions": {},
        "sector": {},
    },
    "tdx": {
        "history": {"markets": {"CN"}, "periods": {"1d", "1m", "5m", "15m", "30m", "60m"}},
        "valuation": {"markets": {"CN"}, "note": "PB only"},
    },
    "yahoo": {
        "history": {"markets": {"US"}, "periods": {"1d"}},
    },
    "akshare": {
        "history": {"markets": {"HK", "US"}, "periods": {"1d"}, "note": "sina 新浪"},
        "financial": {"markets": {"HK"}, "note": "东财 F10"},
        "valuation": {"markets": {"HK"}},
    },
}


def supports(provider, capability, market=None, period=None) -> bool:
    """查询某 provider 是否支持某能力（可再按 market / period 过滤）。未知一律 False。"""
    cap = PROVIDER_CAPABILITIES.get(provider, {}).get(capability)
    if not cap:
        return False
    if market is not None and cap.get("markets") is not None and market not in cap["markets"]:
        return False
    if period is not None and cap.get("periods") is not None and period not in cap["periods"]:
        return False
    return True
