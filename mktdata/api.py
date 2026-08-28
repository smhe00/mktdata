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

from . import providers as P
from . import router
from .errors import MktDataError
from .models import DataResult


def _as_list(codes) -> List[str]:
    return [codes] if isinstance(codes, str) else list(codes)


class MarketData:
    """多市场、多数据源、自动 fallback 的只读市场数据入口。

    history 返回 {code: DataResult}，data 为 canonical HISTORY_FIELDS
    （symbol/datetime/open/high/low/close/volume/amount/source，P0-1）。
    其余返回 DataResult（含 .data / .source / .requested_source / .fallback_chain / .provenance()）。
    """

    def history(self, codes, start, end, period="1d", adjust="none", source="auto") -> Dict[str, DataResult]:
        """历史 K 线（canonical schema）。返回 {code: DataResult}。"""
        return {c: router.execute_history(c, start, end, period, adjust, requested=source) for c in _as_list(codes)}

    def financial(self, code, statement="income", period="annual", limit=4, source="auto") -> DataResult:
        """财务报表（A股 hithink→miniqmt；港股走东财 F10）。statement: income/balance/cashflow。"""
        rows, src, fb = router.execute_financial(code, statement, period, limit, requested=source)
        if rows is None:
            raise MktDataError(f"financial {code} {statement}: 无可用源 ({src})")
        return DataResult(data=rows, source=src, ok=True, requested_source=source, fallback_chain=fb)

    def indicators(self, code, report=None, source="auto") -> DataResult:
        """财务指标（A股 hithink→miniqmt）。report 缺省自动取最新年报（如 '2025-4'，尊重 forced source）。"""
        if not report:
            fy = router.latest_fiscal_year(code, requested=source)
            if not fy:
                raise MktDataError(f"indicators {code}: 无法确定最新报告期")
            report = f"{fy}-4"
        row, src, fb = router.execute_indicators(code, report, requested=source)
        if row is None:
            raise MktDataError(f"indicators {code}: 无可用源 ({src})")
        return DataResult(data=row, source=src, ok=True, requested_source=source, fallback_chain=fb)

    def valuation(self, code, source="auto") -> DataResult:
        """估值快照（A股 hithink→miniqmt→tdx；港股东财）。"""
        row, src, fb = router.execute_valuation(code, requested=source)
        if row is None:
            raise MktDataError(f"valuation {code}: 无可用源 ({src})")
        return DataResult(data=row, source=src, ok=True, requested_source=source, fallback_chain=fb)

    def crosscheck(self, codes, start, end) -> Dict[str, Dict[str, Any]]:
        """hithink/miniQMT/tdx 三源收盘+PB 一致性对账（P0-6：含 pb_ok，5% 相对容差）。"""
        out: Dict[str, Dict[str, Any]] = {}
        for code in _as_list(codes):
            closes: Dict[str, Dict[str, float]] = {}
            for src, fn in (("hh", lambda: P.hithink_history(code, start, end, "none")),
                            ("mq", lambda: P.miniqmt_history(code, start, end, "1d", "none")),
                            ("tdx", lambda: P.tdx_history(code, start, end, "1d", "none"))):
                try:
                    rows = fn()
                    closes[src] = {r.get("datetime", r.get("date")): r["close"] for r in rows} if rows else {}
                except Exception:
                    closes[src] = {}
            common = set(closes["hh"]) & set(closes["mq"]) & set(closes["tdx"])
            last_day = max(common) if common else None
            close_vals = {s: closes[s].get(last_day) for s in ("hh", "mq", "tdx")} if last_day else {}
            pb = {"hh": None, "mq": None, "tdx": None}
            if last_day:
                try:
                    hh_val = P.hithink_valuation([code])
                    pb["hh"] = (hh_val or {}).get(code, {}).get("pb_mrq")
                except Exception:
                    pass
                try:
                    pb["mq"] = (P.miniqmt_valuation(code) or {}).get("pb_mrq")
                except Exception:
                    pass
                try:
                    pb["tdx"] = (P.tdx_valuation(code, asof_close=close_vals.get("tdx")) or {}).get("pb_mrq")
                except Exception:
                    pass
            close_ok = last_day is not None and max((abs(close_vals[a] - close_vals[b]) for a in ("hh", "mq", "tdx") for b in ("hh", "mq", "tdx") if a < b)) < 0.02
            pb_ok = False
            if all(v is not None for v in pb.values()):
                rel = max(
                    abs(pb["hh"] - pb["mq"]) / max(pb["hh"], pb["mq"], 1e-9),
                    abs(pb["mq"] - pb["tdx"]) / max(pb["mq"], pb["tdx"], 1e-9),
                    abs(pb["hh"] - pb["tdx"]) / max(pb["hh"], pb["tdx"], 1e-9),
                )
                pb_ok = rel < 0.05
            out[code] = {"last_day": last_day, "closes": close_vals, "pb": pb,
                         "close_ok": bool(close_ok), "pb_ok": bool(pb_ok)}
        return out

    # ---- 市场基础数据：统一由 provider 实现（P0-4，api 不再直接碰 xtdata）----
    def calendar(self, market="SH", start="", end="", count=-1) -> DataResult:
        """交易日历（miniQMT）。返回 YYYY-MM-DD 列表。"""
        return DataResult(data=P.miniqmt_calendar(market, start, end, count), source="miniqmt")

    def instrument(self, code) -> DataResult:
        """证券基础资料（miniQMT）。"""
        return DataResult(data=P.miniqmt_instrument(code), source="miniqmt")

    def corporate_actions(self, code, start="", end="") -> DataResult:
        """分红/送转/除权事件流（miniQMT）。"""
        return DataResult(data=P.miniqmt_corporate_actions(code, start, end), source="miniqmt")

    def sector(self, name) -> DataResult:
        """板块成分（miniQMT），如 '沪深300'/'上证50'。"""
        return DataResult(data=P.miniqmt_sector(name), source="miniqmt")
