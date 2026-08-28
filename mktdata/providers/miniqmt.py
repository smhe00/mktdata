"""miniQMT（本机 xtquant/xtdata）provider：A 股+港股行情、A 股三表/指标/估值自算。"""

import math

from ..normalize import norm_dt_ymd, norm_num

MINIQMT_STMT = {
    "income": ("Income", [("revenue", "revenue"), ("net_profit_excl_min_int_inc", "np_parent")]),
    "balance": ("Balance", [("tot_assets", "assets_total"), ("tot_liab", "total_debt"), ("total_equity", "holder_equity_total")]),
    "cashflow": ("CashFlow", [("net_cash_flows_oper_act", "act_cash_flow_net"), ("net_cash_flows_inv_act", "invest_cash_flow_net"), ("net_cash_flows_fnc_act", "financing_cash_flow_net")]),
}


def _dedup_latest_announce(df):
    """同一报告期出现多行（财报重述）时，保留 m_anntime 最新（重述后当前版）的一行。"""
    if df is None or len(df) == 0 or "m_anntime" not in df.columns or "m_timetag" not in df.columns:
        return df
    idx = df.groupby("m_timetag")["m_anntime"].idxmax()
    return df.loc[idx]


def miniqmt_history(code, start, end, period, adjust):
    try:
        from xtquant import xtdata
    except ImportError:
        return None, "xtquant 未安装（需用 miniQMT 项目 venv Python）"
    xtdata.enable_hello = False
    xtdata.connect()
    try:
        xtdata.download_history_data(code, period=period, start_time=start, end_time=end)
        data = xtdata.get_market_data_ex(
            [], [code], period=period, start_time=start, end_time=end, dividend_type=adjust
        )
    except Exception as e:
        return None, f"miniQMT 调用异常: {e!r}"
    df = data.get(code)
    if df is None or len(df) == 0:
        return None, "miniQMT 无数据"
    rows = []
    for t, r in df.iterrows():
        rows.append(
            {
                "date": norm_dt_ymd(int(t)),  # 8位→日期；14位(分钟)→日期+时间
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
                "amount": float(r["amount"]),
            }
        )
    if not rows:
        return None, "miniQMT 返回空数据"
    return rows, None


def miniqmt_financial(code, statement, period, limit):
    table, fields = MINIQMT_STMT[statement]
    try:
        from xtquant import xtdata
    except ImportError:
        return None, "xtquant 未安装（需用 miniQMT 项目 venv Python）"
    xtdata.enable_hello = False
    xtdata.connect()
    try:
        xtdata.download_financial_data([code], [table])
        res = xtdata.get_financial_data([code], [table], "20000101", "", "report_time")
    except Exception as e:
        return None, f"miniQMT 调用异常: {e!r}"
    df = (res.get(code) or {}).get(table)
    if df is None or len(df) == 0:
        return None, "miniQMT 无该报表数据"
    df = _dedup_latest_announce(df)
    if period == "annual":
        df = df[df["m_timetag"].astype(str).str.endswith("1231")]
    df = df.sort_values("m_timetag").tail(limit)
    rows = []
    for _, r in df.iterrows():
        def _num(v):
            try:
                v = float(v)
                return None if math.isnan(v) else v
            except Exception:
                return None
        row = {"period": str(r["m_timetag"])}
        for src_k, out_k in fields:
            row[out_k] = _num(r.get(src_k))
        rows.append(row)
    if not rows:
        return None, "miniQMT 无该报表数据"
    return rows, None


def miniqmt_indicators(code, fy):
    """miniQMT 无现成指标表，用三张原始报表自算核心指标。"""
    try:
        from xtquant import xtdata
    except ImportError:
        return None, "xtquant 未安装（需用 miniQMT 项目 venv Python）"
    xtdata.enable_hello = False
    xtdata.connect()
    try:
        xtdata.download_financial_data([code], ["Income", "Balance", "CashFlow"])
        res = xtdata.get_financial_data([code], ["Income", "Balance", "CashFlow"], "20000101", "", "report_time")
    except Exception as e:
        return None, f"miniQMT 调用异常: {e!r}"

    def _annual(table):
        df = (res.get(code) or {}).get(table)
        if df is None or len(df) == 0:
            return None
        df = _dedup_latest_announce(df)
        return df[df["m_timetag"].astype(str).str.endswith("1231")].sort_values("m_timetag")

    def _row(df, y):
        if df is None:
            return None
        m = df[df["m_timetag"].astype(str) == f"{y}1231"]
        return m.iloc[0] if len(m) else None

    inc, bal, cf = _annual("Income"), _annual("Balance"), _annual("CashFlow")
    r_i, r_i1 = _row(inc, fy), _row(inc, fy - 1)
    r_b, r_c = _row(bal, fy), _row(cf, fy)
    out = {"period": f"FY{fy}", "gross_margin": None}
    if r_i is not None and r_i1 is not None:
        rev0, rev1 = norm_num(r_i["revenue"]), norm_num(r_i1["revenue"])
        np0, np1 = norm_num(r_i["net_profit_excl_min_int_inc"]), norm_num(r_i1["net_profit_excl_min_int_inc"])
        out["revenue_yoy"] = (rev0 / rev1 - 1) * 100 if (rev0 and rev1) else None
        out["np_yoy"] = (np0 / np1 - 1) * 100 if (np0 and np1) else None
        out["net_margin"] = np0 / rev0 * 100 if (np0 and rev0) else None
    if r_b is not None:
        a, l, e = norm_num(r_b["tot_assets"]), norm_num(r_b["tot_liab"]), norm_num(r_b["total_equity"])
        out["debt_ratio"] = l / a * 100 if (a and l) else None
        ca, cl = norm_num(r_b["total_current_assets"]), norm_num(r_b.get("total_current_liability"))
        out["current_ratio"] = ca / cl if (ca and cl) else None
        if r_i is not None:
            np0 = norm_num(r_i["net_profit_excl_min_int_inc"])
            out["roe"] = np0 / e * 100 if (np0 and e) else None
    if r_c is not None and r_i is not None:
        ocf = norm_num(r_c["net_cash_flows_oper_act"])
        rev0 = norm_num(r_i["revenue"])
        out["ocf_to_revenue"] = ocf / rev0 * 100 if (ocf and rev0) else None
    return out, None


def miniqmt_valuation(code):
    """miniQMT 无估值接口，用 最新价×总股本 / TTM财报 自算 PE/PB/PS/PCF。"""
    try:
        from xtquant import xtdata
    except ImportError:
        return None, "xtquant 未安装（需用 miniQMT 项目 venv Python）"
    xtdata.enable_hello = False
    xtdata.connect()
    try:
        xtdata.download_financial_data([code], ["Income", "Balance", "CashFlow"])
        res = xtdata.get_financial_data([code], ["Income", "Balance", "CashFlow"], "20000101", "", "report_time")
        px_df = xtdata.get_market_data_ex([], [code], period="1d", count=1).get(code)
        det = xtdata.get_instrument_detail(code)
    except Exception as e:
        return None, f"miniQMT 调用异常: {e!r}"
    if px_df is None or len(px_df) == 0:
        return None, "miniQMT 无最新行情"
    px = float(px_df["close"].iloc[-1])
    sh = det.get("TotalVolume") if det else None
    if not sh:
        return None, "miniQMT 无总股本"
    inc = (res.get(code) or {}).get("Income")
    bal = (res.get(code) or {}).get("Balance")
    cf = (res.get(code) or {}).get("CashFlow")
    if inc is None or len(inc) == 0:
        return None, "miniQMT 无财务数据（港股财务不受支持）"
    inc, bal, cf = _dedup_latest_announce(inc), _dedup_latest_announce(bal), _dedup_latest_announce(cf)
    inc = inc.sort_values("m_timetag")
    L = str(inc["m_timetag"].iloc[-1])
    LY, LM, LD = int(L[:4]), int(L[4:6]), int(L[6:8])
    Y = f"{LY - 1 if LM < 12 else LY}1231"
    L1 = f"{LY - 1}{LM:02d}{LD:02d}"
    def val(df, t, col):
        m = df[df["m_timetag"].astype(str) == str(t)]
        if len(m) == 0:
            return None
        try:
            v = float(m.iloc[0][col])
            return None if math.isnan(v) else v
        except Exception:
            return None
    npY, npL, npL1 = (val(inc, t, "net_profit_excl_min_int_inc") for t in (Y, L, L1))
    rY, rL, rL1 = (val(inc, t, "revenue") for t in (Y, L, L1))
    oY, oL, oL1 = (val(cf, t, "net_cash_flows_oper_act") for t in (Y, L, L1)) if cf is not None else (None, None, None)
    gmd = None
    if bal is not None and len(bal):
        bal_s = bal.sort_values("m_timetag")
        Lb = str(bal_s["m_timetag"].iloc[-1])
        gmd = val(bal_s, Lb, "tot_shrhldr_eqy_excl_min_int")
        if not gmd:
            gmd = val(bal_s, Y, "tot_shrhldr_eqy_excl_min_int")
    mv = px * sh
    def div(a, b):
        return a / b if (a and b) else None
    ttm_np = npY + npL - npL1 if (npY and npL and npL1) else None
    ttm_r = rY + rL - rL1 if (rY and rL and rL1) else None
    ttm_o = oY + oL - oL1 if (oY and oL and oL1) else None
    return {
        "pe_ttm": div(mv, ttm_np), "pe_mrq": div(mv, npY), "pb_mrq": div(mv, gmd),
        "ps_ttm": div(mv, ttm_r), "pcf_ttm": div(mv, ttm_o),
    }, None
