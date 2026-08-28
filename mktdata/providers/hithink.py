"""hithink（同花顺 REST API）provider：A 股行情 / 财务三表 / 指标 / 估值。

错误一律抛结构化异常（P0-3）：
  ProviderAuthError / ProviderRateLimited / ProviderUnavailable /
  InvalidParameter / InvalidSymbol / ProviderUnsupported / ProviderDataEmpty
"""

import json
import os
import re
import urllib.error
import urllib.request

from ..errors import (
    InvalidParameter,
    InvalidSymbol,
    ProviderAuthError,
    ProviderDataEmpty,
    ProviderRateLimited,
    ProviderUnsupported,
    ProviderUnavailable,
)
from ..normalize import norm_date_ms, norm_num, to_ms_utc

HITHINK_KEY_FILE = os.path.join(os.environ.get("APPDATA", ""), "hithink-finance", "credentials.env")
HITHINK_BASE = "https://fuyao.aicubes.cn"

HITHINK_STMT = {
    "income": ("income-statements", [("operating_income", "revenue"), ("parent_holder_net_profit", "np_parent")]),
    "balance": ("balance-sheets", [("assets_total", "assets_total"), ("total_debt", "total_debt"), ("holder_equity_total", "holder_equity_total")]),
    "cashflow": ("cash-flow-statements", [("act_cash_flow_net", "act_cash_flow_net"), ("invest_cash_flow_net", "invest_cash_flow_net"), ("financing_cash_flow_net", "financing_cash_flow_net")]),
}

HITHINK_IND = {
    "calculate_operating_income_yoy_growth_ratio": "revenue_yoy",
    "calculate_parent_holder_net_profit_yoy_growth_ratio": "np_yoy",
    "sale_gross_margin": "gross_margin",
    "sale_net_interest_ratio": "net_margin",
    "index_weighted_avg_roe": "roe",
    "assets_debt_ratio": "debt_ratio",
    "current_ratio": "current_ratio",
    "operating_cash_flow_net_divide_income": "ocf_to_revenue",
}


def _read_hithink_key():
    try:
        with open(HITHINK_KEY_FILE, "r", encoding="utf-8") as f:
            m = re.search(r"^HITHINK_FINANCE_API_KEY=(.+)$", f.read(), re.M)
        return m.group(1).strip() if m else None
    except Exception:
        return None


def _raise_biz(code, message):
    """业务码 → 结构化异常。"""
    c = int(code)
    if c in (2001, 2003):
        raise ProviderAuthError(f"hithink {c}: {message}")
    if c == 4001:
        raise ProviderRateLimited(f"hithink {c}: {message}")
    if c >= 5000:
        raise ProviderUnavailable(f"hithink {c}: {message}")
    if c in (1001, 1002, 1003, 1004):
        raise InvalidParameter(f"hithink {c}: {message}")
    if c == 3001:
        raise InvalidSymbol(f"hithink {c}: {message}")
    if c == 3004:
        raise ProviderUnsupported(f"hithink {c}: {message}")
    raise ProviderUnavailable(f"hithink {c}: {message}")


def _request(url, key):
    req = urllib.request.Request(url, headers={"X-api-key": key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ProviderAuthError(f"hithink HTTP {e.code}")
        if e.code == 429:
            raise ProviderRateLimited(f"hithink HTTP {e.code}")
        raise ProviderUnavailable(f"hithink HTTP {e.code}: {e.reason}")
    except Exception as e:
        raise ProviderUnavailable(f"hithink 网络异常: {e!r}")


def hithink_history(code, start, end, adjust):
    key = _read_hithink_key()
    if not key:
        raise ProviderAuthError("hithink key 未找到（" + HITHINK_KEY_FILE + "）")
    adj = {"none": "none", "front": "forward", "back": "backward"}.get(adjust, "backward")
    url = (
        f"{HITHINK_BASE}/api/a-share/prices/historical?thscode={code}&interval=1d"
        f"&start={to_ms_utc(start)}&end={to_ms_utc(end)}&adjust={adj}&offset=0"
    )
    j = _request(url, key)
    if j.get("code") != 0:
        _raise_biz(j.get("code"), j.get("message"))
    rows = []
    for b in j.get("data", {}).get("item", []) or []:
        if b.get("date_ms") is None or b.get("close_price") is None:
            continue
        rows.append({
            "date": norm_date_ms(b["date_ms"]),
            "open": norm_num(b.get("open_price")),
            "high": norm_num(b.get("high_price")),
            "low": norm_num(b.get("low_price")),
            "close": norm_num(b["close_price"]),
            "volume": norm_num(b.get("volume")),   # hithink volume 单位=股（shares）
            "amount": norm_num(b.get("amount")),
        })
    if not rows:
        raise ProviderDataEmpty("hithink 返回空数据")
    return rows


def hithink_financial(code, statement, period, limit):
    endpoint, fields = HITHINK_STMT[statement]
    key = _read_hithink_key()
    if not key:
        raise ProviderAuthError("hithink key 未找到（" + HITHINK_KEY_FILE + "）")
    url = f"{HITHINK_BASE}/api/a-share/financials/{endpoint}?thscode={code}&period={period}&limit={limit}"
    j = _request(url, key)
    if j.get("code") != 0:
        _raise_biz(j.get("code"), j.get("message"))
    rows = []
    for it in j.get("data", {}).get("item", []) or []:
        if period == "annual":
            label = f"FY{it.get('fiscal_year')}"
        else:
            label = f"{it.get('fiscal_year')}{it.get('fiscal_period') or ''}"
        row = {"period": label}
        for src_k, out_k in fields:
            row[out_k] = it.get(src_k)
        rows.append(row)
    if not rows:
        raise ProviderDataEmpty("hithink 无该报表数据")
    return rows


def hithink_indicators(code, report):
    key = _read_hithink_key()
    if not key:
        raise ProviderAuthError("hithink key 未找到（" + HITHINK_KEY_FILE + "）")
    url = f"{HITHINK_BASE}/api/a-share/financials/indicators?thscode={code}&report={report}"
    j = _request(url, key)
    if j.get("code") != 0:
        _raise_biz(j.get("code"), j.get("message"))
    out = {"period": report}
    for ab in (j.get("data") or {}).get("abilities") or []:
        for ind in ab.get("indicators") or []:
            k = HITHINK_IND.get(ind.get("index_id"))
            if k:
                out[k] = norm_num(ind.get("value"))
    return out


def hithink_valuation(codes):
    key = _read_hithink_key()
    if not key:
        raise ProviderAuthError("hithink key 未找到（" + HITHINK_KEY_FILE + "）")
    url = f"{HITHINK_BASE}/api/a-share/valuations/snapshot?thscodes=" + ",".join(codes)
    j = _request(url, key)
    if j.get("code") != 0:
        _raise_biz(j.get("code"), j.get("message"))
    out = {}
    for it in (j.get("data") or {}).get("item") or []:
        out[it.get("thscode")] = {
            "name": it.get("name"), "pe_ttm": it.get("pe_ttm"), "pe_mrq": it.get("pe_mrq"),
            "pb_mrq": it.get("pb_mrq"), "ps_ttm": it.get("ps_ttm"), "pcf_ttm": it.get("pcf_ttm"),
        }
    return out
