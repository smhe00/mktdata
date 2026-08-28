"""mktdata 统一 Python API（P0-1）。

用法:
    from mktdata import MarketData
    md = MarketData()
    bars = md.history(["600519.SH", "000858.SZ"], "20260101", "20260828", adjust="none")
    cal  = md.calendar(market="SH", start="20260101", end="20260828")
    inst = md.instrument("600519.SH")
    act  = md.corporate_actions("600519.SH", "20200101", "20260828")
"""

from typing import Any, Dict, List, Optional, Union

from . import router
from .errors import MktDataError
from .models import DataResult


def _as_list(codes) -> List[str]:
    return [codes] if isinstance(codes, str) else list(codes)


class MarketData:
    """多市场、多数据源、自动 fallback 的只读市场数据入口。

    所有返回均为 DataResult（含 .data / .source / .fallback_chain / .provenance()）。
    失败（全部源不可用）时抛 MktDataError。
    """

    def history(self, codes, start, end, period="1d", adjust="none", source="auto") -> Dict[str, DataResult]:
        """历史 K 线。返回 {code: DataResult}，data 为统一字段的 list[dict]。"""
        return {c: router.execute_history(c, start, end, period, adjust, requested=source) for c in _as_list(codes)}

    def financial(self, code, statement="income", period="annual", limit=4, source="auto") -> DataResult:
        """财务报表（A股 hithink→miniqmt；港股走东财 F10）。statement: income/balance/cashflow。"""
        rows, src, fb = router.execute_financial(code, statement, period, limit, requested=source)
        if rows is None:
            raise MktDataError(f"financial {code} {statement}: 无可用源 ({src})")
        return DataResult(data=rows, source=src, ok=True, fallback_chain=fb)

    def valuation(self, code, source="auto") -> DataResult:
        """估值快照（A股 hithink→miniqmt→tdx；港股东财）。"""
        row, src, fb = router.execute_valuation(code, requested=source)
        if row is None:
            raise MktDataError(f"valuation {code}: 无可用源 ({src})")
        return DataResult(data=row, source=src, ok=True, fallback_chain=fb)

    def crosscheck(self, codes, start, end) -> Dict[str, Dict[str, Any]]:
        """hithink/miniQMT/tdx 三源收盘+PB 一致性对账。返回 {code: {closes, pb, close_ok, pb_ok}}。"""
        out: Dict[str, Dict[str, Any]] = {}
        for code in _as_list(codes):
            closes: Dict[str, Dict[str, float]] = {}
            for src, fn in (("hh", lambda: __import__("mktdata.providers.hithink", fromlist=["hithink_history"]).hithink_history(code, start, end, "none")),
                            ("mq", lambda: __import__("mktdata.providers.miniqmt", fromlist=["miniqmt_history"]).miniqmt_history(code, start, end, "1d", "none")),
                            ("tdx", lambda: __import__("mktdata.providers.tdx", fromlist=["tdx_history"]).tdx_history(code, start, end, "1d", "none"))):
                rows, _ = fn()
                closes[src] = {r["date"]: r["close"] for r in rows} if rows else {}
            common = set(closes["hh"]) & set(closes["mq"]) & set(closes["tdx"])
            last_day = max(common) if common else None
            close_vals = {s: closes[s].get(last_day) for s in ("hh", "mq", "tdx")} if last_day else {}
            pb = {"hh": None, "mq": None, "tdx": None}
            if last_day:
                hh_val, _ = __import__("mktdata.providers.hithink", fromlist=["hithink_valuation"]).hithink_valuation([code])
                pb["hh"] = (hh_val or {}).get(code, {}).get("pb_mrq")
                pb["mq"] = (router.execute_valuation(code, requested="miniqmt").data or {}).get("pb_mrq")
                pb["tdx"] = (router.execute_valuation(code, requested="tdx").data or {}).get("pb_mrq") if close_vals.get("tdx") else None
            close_ok = last_day is not None and max((abs(close_vals[a] - close_vals[b]) for a in ("hh", "mq", "tdx") for b in ("hh", "mq", "tdx") if a < b)) < 0.02
            out[code] = {"last_day": last_day, "closes": close_vals, "pb": pb, "close_ok": bool(close_ok)}
        return out

    # ---- miniQMT 原生市场数据（Step 5 并入：统一 API 的日历/资料/公司行为/板块）----
    def calendar(self, market="SH", start="", end="", count=-1) -> DataResult:
        """交易日历（miniQMT get_trading_dates）。market: SH/SZ/HK。"""
        try:
            from xtquant import xtdata
        except ImportError:
            raise MktDataError("xtquant 未安装（需 miniQMT 终端+venv）")
        xtdata.enable_hello = False
        xtdata.connect()
        try:
            dates = xtdata.get_trading_dates(market, start_time=start, end_time=end, count=count)
        except Exception as e:
            raise MktDataError(f"miniQMT calendar 失败: {e!r}")
        return DataResult(data=dates, source="miniqmt")

    def instrument(self, code) -> DataResult:
        """证券基础资料（miniQMT get_instrument_detail）。"""
        try:
            from xtquant import xtdata
        except ImportError:
            raise MktDataError("xtquant 未安装（需 miniQMT 终端+venv）")
        xtdata.enable_hello = False
        xtdata.connect()
        try:
            det = xtdata.get_instrument_detail(code)
        except Exception as e:
            raise MktDataError(f"miniQMT instrument 失败: {e!r}")
        return DataResult(data=det, source="miniqmt")

    def corporate_actions(self, code, start="", end="") -> DataResult:
        """分红/送转/除权事件流（miniQMT get_divid_factors）。"""
        try:
            from xtquant import xtdata
        except ImportError:
            raise MktDataError("xtquant 未安装（需 miniQMT 终端+venv）")
        xtdata.enable_hello = False
        xtdata.connect()
        try:
            factors = xtdata.get_divid_factors(code, start_time=start, end_time=end)
        except Exception as e:
            raise MktDataError(f"miniQMT dividends 失败: {e!r}")
        return DataResult(data=factors, source="miniqmt")

    def sector(self, name) -> DataResult:
        """板块成分（miniQMT get_stock_list_in_sector），如 '沪深300'/'上证50'。"""
        try:
            from xtquant import xtdata
        except ImportError:
            raise MktDataError("xtquant 未安装（需 miniQMT 终端+venv）")
        xtdata.enable_hello = False
        xtdata.connect()
        try:
            lst = xtdata.get_stock_list_in_sector(name)
        except Exception as e:
            raise MktDataError(f"miniQMT sector 失败: {e!r}")
        return DataResult(data=lst, source="miniqmt")
