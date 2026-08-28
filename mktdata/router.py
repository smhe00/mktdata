"""mktdata 路由 / fallback（P0-2、P0-3 error_type、P0-7 requested_source）。

CLI 不再直接写 fallback 逻辑；修改源链只需改本文件。provider 抛结构化异常，
router 捕获后记录 {source, error_type, reason}，成功结果带真实 requested_source。

用法:
    from mktdata.router import execute_history, resolve_valuation
    result = execute_history("600519.SH", "20260101", "20260824")   # DataResult
    chain  = resolve_valuation("CN", requested="auto")               # ["hithink","miniqmt","tdx"]
"""

from typing import List, Optional, Tuple

from . import providers as P
from .errors import MktDataError
from .models import DataResult
from .normalize import normalize_history_rows
from .symbols import normalize_symbol

# ---- 源链定义（顺序 = fallback 顺序）----
HISTORY_CHAINS = {
    ("CN", "1d"): ["hithink", "miniqmt", "tdx"],
    ("CN", "minute"): ["miniqmt", "tdx"],
    ("HK", "1d"): ["miniqmt", "sina"],
    ("US", "1d"): ["yahoo", "sina"],
}
FINANCIAL_CHAINS = {"CN": ["hithink", "miniqmt"], "HK": ["akshare"]}
VALUATION_CHAINS = {"CN": ["hithink", "miniqmt", "tdx"], "HK": ["akshare"]}
CROSSCHECK_CHAINS = {"CN": ["hithink", "miniqmt", "tdx"]}


def _period_kind(period: str) -> str:
    return "minute" if period and period != "1d" else "1d"


def _market_of(code: str) -> str:
    return normalize_symbol(code).market


def resolve_history(market: str, period: str = "1d", requested: str = "auto") -> List[str]:
    chain = list(HISTORY_CHAINS.get((market, _period_kind(period)), []))
    if requested and requested != "auto":
        return [requested]
    return chain


def resolve_financial(market: str, requested: str = "auto") -> List[str]:
    chain = list(FINANCIAL_CHAINS.get(market, []))
    if requested and requested != "auto":
        return [requested]
    return chain


def resolve_valuation(market: str, requested: str = "auto") -> List[str]:
    chain = list(VALUATION_CHAINS.get(market, []))
    if requested and requested != "auto":
        return [requested]
    return chain


def resolve_crosscheck(market: str) -> List[str]:
    return list(CROSSCHECK_CHAINS.get(market, []))


def _err_entry(src: str, e: Exception) -> dict:
    return {"source": src, "error_type": type(e).__name__, "reason": str(e)[:80]}


# ---- 单 provider 调用（失败抛 MktDataError，由 execute_* 捕获）----
def _call_history(src: str, code: str, start: str, end: str, period: str, adjust: str):
    if src == "hithink":
        return P.hithink_history(code, start, end, adjust)
    if src == "miniqmt":
        return P.miniqmt_history(code, start, end, period, adjust)
    if src == "tdx":
        return P.tdx_history(code, start, end, period, adjust)
    if src == "sina":
        return P.ak_hk_history(code, start, end) if code.upper().endswith(".HK") else P.ak_us_history(code, start, end)
    if src == "yahoo":
        return P.yahoo_history(code, start, end)
    raise MktDataError(f"未知源: {src}")


def execute_history(code, start, end, period="1d", adjust="none", requested="auto") -> DataResult:
    """按源链执行 history；成功返回 canonical schema（symbol/datetime/.../source）。"""
    market = _market_of(code)
    chain = resolve_history(market, period, requested)
    fallback: List[dict] = []
    for src in chain:
        try:
            rows = _call_history(src, code, start, end, period, adjust)
        except MktDataError as e:
            fallback.append(_err_entry(src, e))
        except Exception as e:
            fallback.append(_err_entry(src, MktDataError(str(e))))
        else:
            return DataResult(
                data=normalize_history_rows(rows, code, src, period),
                source=src, ok=True, requested_source=requested, fallback_chain=fallback or None,
            )
    last = fallback[-1] if fallback else {}
    return DataResult(data=None, source=chain[-1] if chain else "none", ok=False,
                      error=last.get("reason", "无可用源"),
                      requested_source=requested, fallback_chain=fallback or None)


def _call_financial(src: str, code: str, statement: str, period: str, limit: int):
    if src == "hithink":
        return P.hithink_financial(code, statement, period, limit)
    if src == "miniqmt":
        return P.miniqmt_financial(code, statement, period, limit)
    if src == "akshare":
        return P.ak_f10(code, limit)  # 港股 F10（statement 忽略）
    raise MktDataError(f"未知源: {src}")


def execute_financial(code, statement, period="annual", limit=4, requested="auto"):
    """按源链执行财务报表；返回 (rows_or_dict, source, fallback_chain)。"""
    market = _market_of(code)
    chain = resolve_financial(market, requested)
    fallback: List[dict] = []
    for src in chain:
        try:
            rows = _call_financial(src, code, statement, period, limit)
        except MktDataError as e:
            fallback.append(_err_entry(src, e))
        except Exception as e:
            fallback.append(_err_entry(src, MktDataError(str(e))))
        else:
            return rows, src, (fallback or None)
    return None, (chain[-1] if chain else "none"), (fallback or None)


def _call_valuation(src: str, code: str):
    if src == "hithink":
        m = P.hithink_valuation([code])
        return m.get(code)
    if src == "miniqmt":
        return P.miniqmt_valuation(code)
    if src == "tdx":
        return P.tdx_valuation(code)
    if src == "akshare":
        out = P.ak_f10(code, 3)
        iv = out.get("指标估值")
        if isinstance(iv, dict) and iv.get("PE") is not None:
            return {"name": None, "pe_ttm": iv.get("PE"), "pe_mrq": None,
                    "pb_mrq": iv.get("PB"), "ps_ttm": None, "pcf_ttm": None}
        raise MktDataError("akshare 港股估值不可用")
    raise MktDataError(f"未知源: {src}")


def execute_valuation(code, requested="auto"):
    """按源链执行估值；返回 (row_dict, source, fallback_chain)。"""
    market = _market_of(code)
    chain = resolve_valuation(market, requested)
    fallback: List[dict] = []
    for src in chain:
        try:
            row = _call_valuation(src, code)
        except MktDataError as e:
            fallback.append(_err_entry(src, e))
        except Exception as e:
            fallback.append(_err_entry(src, MktDataError(str(e))))
        else:
            if row is not None:
                return row, src, (fallback or None)
            fallback.append(_err_entry(src, MktDataError("空结果")))
    return None, (chain[-1] if chain else "none"), (fallback or None)
