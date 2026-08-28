"""hithink（同花顺 REST API）provider：A 股行情 / 财务三表 / 指标 / 估值。"""

import json
import os
import re
import urllib.request

from ..normalize import norm_date_ms, norm_num, to_ms_utc

HITHINK_KEY_FILE = os.path.join(os.environ.get("APPDATA", ""), "hithink-finance", "credentials.env")
HITHINK_BASE = "https://fuyao.aicubes.cn"

# 三张报表在 hithink 端点 与 输出键 的映射
HITHINK_STMT = {
    "income": ("income-statements", [("operating_income", "revenue"), ("parent_holder_net_profit", "np_parent")]),
    "balance": ("balance-sheets", [("assets_total", "assets_total"), ("total_debt", "total_debt"), ("holder_equity_total", "holder_equity_total")]),
    "cashflow": ("cash-flow-statements", [("act_cash_flow_net", "act_cash_flow_net"), ("invest_cash_flow_net", "invest_cash_flow_net"), ("financing_cash_flow_net", "financing_cash_flow_net")]),
}

# hithink indicators index_id -> 统一键
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


def hithink_history(code, start, end, adjust):
    key = _read_hithink_key()
    if not key:
        return None, "hithink key 未找到（" + HITHINK_KEY_FILE + "）"
    adj = {"none": "none", "front": "forward", "back": "backward"}.get(adjust, "backward")
    url = (
        f"{HITHINK_BASE}/api/a-share/prices/historical?thscode={code}&interval=1d"
        f"&start={to_ms_utc(start)}&end={to_ms_utc(end)}&adjust={adj}&offset=0"
    )
    try:
        req = urllib.request.Request(url, headers={"X-api-key": key, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            j = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None, f"hithink 网络/解析异常: {e!r}"
    if j.get("code") != 0:
        return None, f"hithink 业务码 {j.get('code')}: {j.get('message')}"
    rows = []
    for b in j.get("data", {}).get("item", []) or []:
        if b.get("date_ms") is None or b.get("close_price") is None:
            continue
        rows.append(
            {
                "date": norm_date_ms(b["date_ms"]),
                "open": float(b.get("open_price") or 0),
                "high": float(b.get("high_price") or 0),
                "low": float(b.get("low_price") or 0),
                "close": float(b["close_price"]),
                "volume": float(b.get("volume") or 0),
                "amount": float(b.get("amount") or 0),
            }
        )
    if not rows:
        return None, "hithink 返回空数据"
    return rows, None


def hithink_financial(code, statement, period, limit):
    endpoint, fields = HITHINK_STMT[statement]
    key = _read_hithink_key()
    if not key:
        return None, "hithink key 未找到（" + HITHINK_KEY_FILE + "）"
    url = f"{HITHINK_BASE}/api/a-share/financials/{endpoint}?thscode={code}&period={period}&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"X-api-key": key, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            j = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None, f"hithink 网络/解析异常: {e!r}"
    if j.get("code") != 0:
        return None, f"hithink 业务码 {j.get('code')}: {j.get('message')}"
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
        return None, "hithink 无该报表数据"
    return rows, None


def hithink_indicators(code, report):
    key = _read_hithink_key()
    if not key:
        return None, "hithink key 未找到（" + HITHINK_KEY_FILE + "）"
    url = f"{HITHINK_BASE}/api/a-share/financials/indicators?thscode={code}&report={report}"
    try:
        req = urllib.request.Request(url, headers={"X-api-key": key, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            j = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None, f"hithink 网络/解析异常: {e!r}"
    if j.get("code") != 0:
        return None, f"hithink 业务码 {j.get('code')}: {j.get('message')}"
    out = {"period": report}
    for ab in (j.get("data") or {}).get("abilities") or []:
        for ind in ab.get("indicators") or []:
            k = HITHINK_IND.get(ind.get("index_id"))
            if k:
                out[k] = norm_num(ind.get("value"))
    return out, None


def hithink_valuation(codes):
    key = _read_hithink_key()
    if not key:
        return None, "hithink key 未找到（" + HITHINK_KEY_FILE + "）"
    url = f"{HITHINK_BASE}/api/a-share/valuations/snapshot?thscodes=" + ",".join(codes)
    try:
        req = urllib.request.Request(url, headers={"X-api-key": key, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            j = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None, f"hithink 网络/解析异常: {e!r}"
    if j.get("code") != 0:
        return None, f"hithink 业务码 {j.get('code')}: {j.get('message')}"
    out = {}
    for it in (j.get("data") or {}).get("item") or []:
        out[it.get("thscode")] = {
            "name": it.get("name"), "pe_ttm": it.get("pe_ttm"), "pe_mrq": it.get("pe_mrq"),
            "pb_mrq": it.get("pb_mrq"), "ps_ttm": it.get("ps_ttm"), "pcf_ttm": it.get("pcf_ttm"),
        }
    return out, None
