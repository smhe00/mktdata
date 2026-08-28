"""通达信 easy-tdx provider：A 股日线/分钟（原始价）、PB（每股净资产）、历史资金流向。"""

from ..errors import (
    ProviderDataEmpty,
    ProviderUnsupported,
    ProviderUnavailable,
)
from ..normalize import norm_num

TDX_HOSTS = [
    "115.238.56.198", "60.191.117.167", "180.153.18.170",
    "218.75.126.9", "123.125.108.90", "180.153.18.171",
]

TDX_CAT = {"1d": "DAY", "1m": "MIN_1", "5m": "MIN_5", "15m": "MIN_15", "30m": "MIN_30", "60m": "MIN_60"}


def _tdx_code(code):
    u = code.upper()
    if u.endswith(".SH"):
        return 1, u[:6]
    if u.endswith(".SZ"):
        return 0, u[:6]
    return None, None


def _tdx_connect():
    try:
        import easy_tdx as e
    except ImportError:
        raise ProviderUnavailable("easy-tdx 未安装（pip install easy-tdx）")
    last_err = None
    for host in TDX_HOSTS:
        try:
            c = e.TdxClient(host=host, port=7709, timeout=6)
            c.connect()
            return c
        except Exception as ex:
            last_err = f"{host}:{ex!r}"
    raise ProviderUnavailable("easy-tdx 全部服务器不可用: " + str(last_err))


def _tdx_market(mkt):
    try:
        import easy_tdx as e
        return e.Market.SH if mkt == 1 else e.Market.SZ
    except ImportError:
        raise ProviderUnavailable("easy-tdx 未安装")


def tdx_history(code, start, end, period, adjust):
    """通达信 K 线（easy-tdx，原始价，日线+分钟线）。volume 原始=股（shares，P0-2）。"""
    if adjust != "none":
        raise ProviderUnsupported("tdx 源仅支持 --adjust none（原始价）；复权请用 hithink/miniqmt")
    mkt, scode = _tdx_code(code)
    if mkt is None:
        raise ProviderUnsupported(f"tdx 源暂只支持 A 股 SH/SZ：{code}")
    cat = TDX_CAT.get(period)
    if cat is None:
        raise ProviderUnsupported(f"tdx 源暂不支持周期 {period}（支持 1d/1m/5m/15m/30m/60m）")
    try:
        import easy_tdx as e
        import pandas as pd
    except ImportError:
        raise ProviderUnavailable("easy-tdx/pandas 未安装")
    c = _tdx_connect()
    try:
        frames = []
        idx = 0
        while True:
            page = c.get_security_bars(_tdx_market(mkt), scode, getattr(e.KlineCategory, cat), idx, 800)
            if page is None or len(page) == 0:
                break
            frames.append(page)
            idx += 800
            if sum(len(f) for f in frames) > 6000:
                break
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    except Exception as ex:
        c.disconnect()
        raise ProviderUnavailable(f"easy-tdx 拉取异常: {ex!r}")
    c.disconnect()
    if len(df) == 0:
        raise ProviderDataEmpty("tdx 无数据")
    d0 = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
    d1 = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
    tcol = "datetime" if "datetime" in df.columns else "date"
    rows = []
    for _, r in df.drop_duplicates(tcol).sort_values(tcol).iterrows():
        ds = str(r[tcol])[:10]
        if ds < d0 or ds > d1:
            continue
        rows.append({
            "date": (str(r[tcol])[:16] if period != "1d" else ds),
            "open": norm_num(r["open"]), "high": norm_num(r["high"]),
            "low": norm_num(r["low"]), "close": norm_num(r["close"]),
            "volume": norm_num(r["vol"]),   # easy-tdx vol 原始=股（shares，不再 /100）
            "amount": norm_num(r["amount"]),
        })
    if not rows:
        raise ProviderDataEmpty("tdx 该区间无数据")
    return rows


def tdx_valuation(code, asof_close=None):
    """通达信 PB（easy-tdx）：最新价 / 每股净资产。asof_close 可指定对账日收盘价。"""
    mkt, scode = _tdx_code(code)
    if mkt is None:
        raise ProviderUnsupported(f"tdx 估值仅支持 A 股 SH/SZ：{code}")
    try:
        import easy_tdx as e
    except ImportError:
        raise ProviderUnavailable("easy-tdx 未安装（pip install easy-tdx）")
    c = _tdx_connect()
    try:
        bars = c.get_security_bars(_tdx_market(mkt), scode, e.KlineCategory.DAY, 0, 2)
        if bars is None or len(bars) == 0:
            raise ProviderDataEmpty("tdx 无最新行情")
        px = asof_close if asof_close is not None else norm_num(bars.iloc[-1]["close"])
        fi = c.get_finance_info(_tdx_market(mkt), scode)
    except Exception as ex:
        c.disconnect()
        if isinstance(ex, Exception) and type(ex).__name__ == "ProviderDataEmpty":
            c.disconnect()
            raise
        c.disconnect()
        raise ProviderUnavailable(f"easy-tdx 调用异常: {ex!r}")
    c.disconnect()
    row = {"name": None, "pe_ttm": None, "pe_mrq": None, "pb_mrq": None, "ps_ttm": None, "pcf_ttm": None}
    bvps = fi["meigujing_zichan"].iloc[0] if fi is not None and len(fi) else None
    bvps = norm_num(bvps)
    if bvps and bvps > 0:
        row["pb_mrq"] = px / bvps
    return row


def tdx_fundflow(code, count):
    """通达信历史资金流向（easy-tdx 独有能力）：主力/超大/大/中/小单净流入。"""
    mkt, scode = _tdx_code(code)
    if mkt is None:
        raise ProviderUnsupported(f"资金流向仅支持 A 股 SH/SZ：{code}")
    try:
        import easy_tdx as e
    except ImportError:
        raise ProviderUnavailable("easy-tdx 未安装（pip install easy-tdx）")
    c = _tdx_connect()
    try:
        df = c.get_history_fund_flow(_tdx_market(mkt), scode, 0, count)
    except Exception as ex:
        c.disconnect()
        raise ProviderUnavailable(f"easy-tdx 资金流异常: {ex!r}")
    c.disconnect()
    if df is None or len(df) == 0:
        raise ProviderDataEmpty("easy-tdx 无资金流数据")
    return df
