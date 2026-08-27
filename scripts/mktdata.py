#!/usr/bin/env python
"""mktdata: 行情数据统一入口（hithink 优先、miniQMT 兜底）。

设计目标：hithink（同花顺）能查的走 hithink；查不了或调用失败时自动转本机
miniQMT 兜底。两者都输出统一格式（date,open,high,low,close,volume,amount）。

来源路由（--source auto，默认）:
  - 港股（代码以 .HK 结尾）或分钟级（--period 5m/1m）→ 直接 miniQMT（hithink 不支持）
  - A 股日线 → 先 hithink；hithink 返回非 0 业务码 / 网络异常 / 数据为空 → 转 miniQMT
  - --source hithink|miniqmt 可强制只用单一来源（不兜底）

用法:
  python mktdata.py history --codes 00700.HK,600519.SH,601318.SH --start 20240101 --end 20260824 --adjust back
  python mktdata.py history --codes 00700.HK --period 5m --start 20260820 --end 20260821 --outdir ./out
  python mktdata.py history --codes 600519.SH --source hithink   # 强制 hithink，便于测试/对账
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import sys
import urllib.request

HITHINK_KEY_FILE = os.path.join(os.environ.get("APPDATA", ""), "hithink-finance", "credentials.env")
HITHINK_BASE = "https://fuyao.aicubes.cn"


def _read_hithink_key():
    try:
        with open(HITHINK_KEY_FILE, "r", encoding="utf-8") as f:
            m = re.search(r"^HITHINK_FINANCE_API_KEY=(.+)$", f.read(), re.M)
        return m.group(1).strip() if m else None
    except Exception:
        return None


def _is_hk(code: str) -> bool:
    return code.upper().endswith(".HK")


def _fmt_date_from_ymd(x) -> str:
    # 日线索引 8 位 YYYYMMDD；分钟线索引 14 位 YYYYMMDDHHMMSS
    s = str(int(x))
    if len(s) >= 14:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _fmt_date_from_ms(ms: int) -> str:
    # hithink date_ms 为北京时间 0 点（UTC+8），转成日期字符串
    return (dt.datetime(1970, 1, 1) + dt.timedelta(milliseconds=int(ms) + 8 * 3600 * 1000)).strftime("%Y-%m-%d")


def _to_ms_utc(s: str) -> int:
    return int(
        dt.datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), tzinfo=dt.timezone.utc).timestamp() * 1000
    )


def hithink_history(code, start, end, adjust):
    key = _read_hithink_key()
    if not key:
        return None, "hithink key 未找到（" + HITHINK_KEY_FILE + "）"
    adj = {"none": "none", "front": "forward", "back": "backward"}.get(adjust, "backward")
    url = (
        f"{HITHINK_BASE}/api/a-share/prices/historical?thscode={code}&interval=1d"
        f"&start={_to_ms_utc(start)}&end={_to_ms_utc(end)}&adjust={adj}&offset=0"
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
                "date": _fmt_date_from_ms(b["date_ms"]),
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
                "date": _fmt_date_from_ymd(int(t)),
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


# ---- 通达信 easy-tdx 第三方源（零认证，独立于 hithink/miniQMT；全面替代 pytdx）----
# easy-tdx 覆盖 pytdx 全部数据方法，并额外提供历史资金流向/涨跌停价/市场统计/财务文件。
# 数据：A 股日线/分钟(原始价) / 每股净资产(→PB) / 历史资金流向 / 除权除息


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
        return None, "easy-tdx 未安装（pip install easy-tdx）"
    try:
        c = e.TdxClient()  # 自动从 KNOWN_HOSTS 选最佳服务器
        c.connect()
        return c, None
    except Exception as ex:
        return None, f"easy-tdx 连接失败: {ex!r}"


def _tdx_market(mkt):
    try:
        import easy_tdx as e
        return e.Market.SH if mkt == 1 else e.Market.SZ
    except ImportError:
        return None


TDX_CAT = {"1d": "DAY", "1m": "MIN_1", "5m": "MIN_5", "15m": "MIN_15", "30m": "MIN_30", "60m": "MIN_60"}


def tdx_history(code, start, end, period, adjust):
    """通达信 K 线（easy-tdx，原始价，日线+分钟线）。与 miniQMT none-adjust 逐日一致（已实测）。"""
    if adjust != "none":
        return None, "tdx 源仅支持 --adjust none（原始价）；复权请用 hithink/miniqmt"
    mkt, scode = _tdx_code(code)
    if mkt is None:
        return None, f"tdx 源暂只支持 A 股 SH/SZ：{code}"
    cat = TDX_CAT.get(period)
    if cat is None:
        return None, f"tdx 源暂不支持周期 {period}（支持 1d/1m/5m/15m/30m/60m）"
    try:
        import easy_tdx as e
        import pandas as pd
    except ImportError:
        return None, "easy-tdx/pandas 未安装"
    c, err = _tdx_connect()
    if c is None:
        return None, err
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
        return None, f"easy-tdx 拉取异常: {ex!r}"
    c.disconnect()
    if len(df) == 0:
        return None, "tdx 无数据"
    d0 = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
    d1 = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
    tcol = "datetime" if "datetime" in df.columns else "date"  # 分钟线用 datetime，日线用 date
    rows = []
    for _, r in df.drop_duplicates(tcol).sort_values(tcol).iterrows():
        ds = str(r[tcol])[:10]
        if ds < d0 or ds > d1:
            continue
        rows.append({
            "date": (str(r[tcol])[:16] if period != "1d" else ds),
            "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
            "volume": float(r["vol"]) / 100.0,  # easy-tdx vol 单位=股 → 手（与 miniQMT/pytdx 一致）
            "amount": float(r["amount"]),
        })
    if not rows:
        return None, "tdx 该区间无数据"
    return rows, None


def tdx_valuation(code, asof_close=None):
    """通达信 PB（easy-tdx）：最新价 / 每股净资产（meigujing_zichan，归母/普通股口径，与 hithink 一致）。
    仅出 PB，PE/PS/PCF 置 None。asof_close 可指定对账日收盘价（跨源同日期比较用）。"""
    mkt, scode = _tdx_code(code)
    if mkt is None:
        return None, f"tdx 估值仅支持 A 股 SH/SZ：{code}"
    try:
        import easy_tdx as e
    except ImportError:
        return None, "easy-tdx 未安装（pip install easy-tdx）"
    c, err = _tdx_connect()
    if c is None:
        return None, err
    try:
        bars = c.get_security_bars(_tdx_market(mkt), scode, e.KlineCategory.DAY, 0, 2)
        if bars is None or len(bars) == 0:
            return None, "tdx 无最新行情"
        px = asof_close if asof_close is not None else float(bars.iloc[-1]["close"])
        fi = c.get_finance_info(_tdx_market(mkt), scode)
    except Exception as ex:
        c.disconnect()
        return None, f"easy-tdx 调用异常: {ex!r}"
    c.disconnect()
    row = {"name": None, "pe_ttm": None, "pe_mrq": None, "pb_mrq": None, "ps_ttm": None, "pcf_ttm": None}
    bvps = fi["meigujing_zichan"].iloc[0] if fi is not None and len(fi) else None
    try:
        bvps = float(bvps)
        if bvps and bvps > 0:
            row["pb_mrq"] = px / bvps
    except Exception:
        pass
    return row, None


def tdx_fundflow(code, count):
    """通达信历史资金流向（easy-tdx 独有能力）：主力/超大/大/中/小单净流入。"""
    mkt, scode = _tdx_code(code)
    if mkt is None:
        return None, f"资金流向仅支持 A 股 SH/SZ：{code}"
    try:
        import easy_tdx as e
    except ImportError:
        return None, "easy-tdx 未安装（pip install easy-tdx）"
    c, err = _tdx_connect()
    if c is None:
        return None, err
    try:
        df = c.get_history_fund_flow(_tdx_market(mkt), scode, 0, count)
    except Exception as ex:
        c.disconnect()
        return None, f"easy-tdx 资金流异常: {ex!r}"
    c.disconnect()
    if df is None or len(df) == 0:
        return None, "easy-tdx 无资金流数据"
    return df, None


# 三张报表在 hithink 端点 与 miniQMT 表/字段 的映射（均已实测）
# 输出键统一为：revenue/np_parent（利润表）、assets_total/total_debt/holder_equity_total（资产负债表）、
#            act_cash_flow_net/invest_cash_flow_net/financing_cash_flow_net（现金流量表）
HITHINK_STMT = {
    "income": ("income-statements", [("operating_income", "revenue"), ("parent_holder_net_profit", "np_parent")]),
    "balance": ("balance-sheets", [("assets_total", "assets_total"), ("total_debt", "total_debt"), ("holder_equity_total", "holder_equity_total")]),
    "cashflow": ("cash-flow-statements", [("act_cash_flow_net", "act_cash_flow_net"), ("invest_cash_flow_net", "invest_cash_flow_net"), ("financing_cash_flow_net", "financing_cash_flow_net")]),
}
MINIQMT_STMT = {
    "income": ("Income", [("revenue", "revenue"), ("net_profit_excl_min_int_inc", "np_parent")]),
    "balance": ("Balance", [("tot_assets", "assets_total"), ("tot_liab", "total_debt"), ("total_equity", "holder_equity_total")]),
    "cashflow": ("CashFlow", [("net_cash_flows_oper_act", "act_cash_flow_net"), ("net_cash_flows_inv_act", "invest_cash_flow_net"), ("net_cash_flows_fnc_act", "financing_cash_flow_net")]),
}


def _dedup_latest_announce(df):
    """同一报告期出现多行（财报重述，如五粮液 2025 各季有两版）时，保留 m_anntime 最新（重述后当前版）的一行。"""
    if df is None or len(df) == 0 or "m_anntime" not in df.columns or "m_timetag" not in df.columns:
        return df
    idx = df.groupby("m_timetag")["m_anntime"].idxmax()
    return df.loc[idx]


def hithink_financial(code, statement, period, limit):
    """hithink 财务报表（A 股）。statement: income/balance/cashflow。"""
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


def miniqmt_financial(code, statement, period, limit):
    """miniQMT 财务报表（A 股，ASHARE 表）。statement: income/balance/cashflow。"""
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


_STMT_LABELS = {
    "income": "利润表(营收/归母净利)",
    "balance": "资产负债表(总资产/总负债/净资产)",
    "cashflow": "现金流量表(经营/投资/筹资净额)",
    "indicators": "财务指标(成长/盈利/偿债)",
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
_IND_UNITS = {"current_ratio": "倍", "revenue_yoy": "%", "np_yoy": "%", "gross_margin": "%", "net_margin": "%", "roe": "%", "debt_ratio": "%", "ocf_to_revenue": "%"}


def _num(v):
    try:
        v = float(v)
        return None if math.isnan(v) else v
    except Exception:
        return None


def hithink_indicators(code, report):
    """hithink 财务指标（A 股）。report 形如 2025-4。"""
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
                out[k] = _num(ind.get("value"))
    return out, None


def _latest_fy(code):
    """最新会计年度（优先 hithink income，失败用 miniQMT）。"""
    rows, err = hithink_financial(code, "income", "annual", 1)
    if rows:
        p = str(rows[0].get("period", ""))
        m = re.match(r"FY(\d{4})", p)
        if m:
            return int(m.group(1))
    rows2, _ = miniqmt_financial(code, "income", "annual", 1)
    if rows2:
        m = re.match(r"(\d{4})", str(rows2[0].get("period", "")))
        if m:
            return int(m.group(1))
    return None


def miniqmt_indicators(code, fy):
    """miniQMT 无现成指标表，用已逐位一致的三张原始报表自算核心指标（口径见注释）。"""
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
    out = {"period": f"FY{fy}", "gross_margin": None}  # miniQMT 无可靠营业成本字段，毛利率不计算
    if r_i is not None and r_i1 is not None:
        rev0, rev1 = _num(r_i["revenue"]), _num(r_i1["revenue"])
        np0, np1 = _num(r_i["net_profit_excl_min_int_inc"]), _num(r_i1["net_profit_excl_min_int_inc"])
        out["revenue_yoy"] = (rev0 / rev1 - 1) * 100 if (rev0 and rev1) else None
        out["np_yoy"] = (np0 / np1 - 1) * 100 if (np0 and np1) else None
        out["net_margin"] = np0 / rev0 * 100 if (np0 and rev0) else None
    if r_b is not None:
        a, l, e = _num(r_b["tot_assets"]), _num(r_b["tot_liab"]), _num(r_b["total_equity"])
        out["debt_ratio"] = l / a * 100 if (a and l) else None
        ca, cl = _num(r_b["total_current_assets"]), _num(r_b.get("total_current_liability"))
        out["current_ratio"] = ca / cl if (ca and cl) else None
        if r_i is not None:
            np0 = _num(r_i["net_profit_excl_min_int_inc"])
            out["roe"] = np0 / e * 100 if (np0 and e) else None
    if r_c is not None and r_i is not None:
        ocf = _num(r_c["net_cash_flows_oper_act"])
        rev0 = _num(r_i["revenue"])
        out["ocf_to_revenue"] = ocf / rev0 * 100 if (ocf and rev0) else None
    return out, None


def _print_ind(period, d):
    line = f"    {str(period):10s} "
    for k in ["revenue_yoy", "np_yoy", "gross_margin", "net_margin", "roe", "debt_ratio", "current_ratio", "ocf_to_revenue"]:
        v = d.get(k)
        unit = _IND_UNITS.get(k, "")
        line += f"{k}={('—' if v is None else f'{v:.2f}{unit}')}  "
    print(line)


def cmd_financial(args):
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    period = args.period
    limit = args.limit
    statements = ["income", "balance", "cashflow", "indicators"] if args.statement == "all" else [args.statement]
    out = []
    for code in codes:
        if _is_hk(code):
            # 港股财务：hithink/miniQMT/TDX 均无 → 自动走 akshare 东财 F10
            f10out, f10err = ak_f10(code, limit)
            if f10out is None:
                print(f"{code:12s} FAIL: 港股财务不可用: {f10err}")
                out.append({"code": code, "status": "fail", "source": "akshare东财(f10)", "error": f10err})
                continue
            print(f"{code:12s} akshare东财(f10) 港股财务：")
            iv = f10out.get("指标估值")
            if isinstance(iv, dict):
                for k, v in iv.items():
                    if v is not None:
                        print(f"    {k} = {v}")
            stmts = f10out.get("三大报表")
            if isinstance(stmts, dict):
                for k, v in stmts.items():
                    print(f"    {k}: {v}")
            out.append({"code": code, "statement": "hk-financial", "status": "ok", "source": "akshare东财(f10)",
                        "rows": {"指标估值": iv, "三大报表": stmts}})
            continue
        for stmt in statements:
            source = args.source
            if stmt == "indicators":
                report = args.report
                if not report:
                    fy = _latest_fy(code)
                    if not fy:
                        print(f"{code:12s} [indicators] FAIL: 无法确定最新报告期")
                        out.append({"code": code, "statement": stmt, "status": "fail", "source": source, "error": "no report"})
                        continue
                    report = f"{fy}-4"
                rows, err = None, None
                if source == "auto":
                    rows, err = hithink_indicators(code, report)
                    if rows is None:
                        source = "miniqmt(fallback:" + (err or "?")[:40] + ")"
                        fy = int(report[:4])
                        rows, err = miniqmt_indicators(code, fy)
                elif source == "hithink":
                    rows, err = hithink_indicators(code, report)
                else:
                    rows, err = miniqmt_indicators(code, int(report[:4]))
                if rows is None:
                    print(f"{code:12s} [indicators] FAIL ({source}): {err}")
                    out.append({"code": code, "statement": stmt, "status": "fail", "source": source, "error": err})
                    continue
                print(f"{code:12s} [indicators] {source:22s} 报告期 {report}（营收同比/归母同比/毛利率/净利率/ROE/负债率/流动比率/经营现金占营收）:")
                _print_ind(rows.get("period"), rows)
                out.append({"code": code, "statement": stmt, "status": "ok", "source": source, "report": report, "rows": rows})
                continue

            if source == "auto":
                rows, err = hithink_financial(code, stmt, period, limit)
                if rows is None:
                    source = "miniqmt(fallback:" + (err or "?")[:40] + ")"
                    rows, err = miniqmt_financial(code, stmt, period, limit)
            elif source == "hithink":
                rows, err = hithink_financial(code, stmt, period, limit)
            else:
                rows, err = miniqmt_financial(code, stmt, period, limit)
            if rows is None:
                print(f"{code:12s} [{stmt:8s}] FAIL ({source}): {err}")
                out.append({"code": code, "statement": stmt, "status": "fail", "source": source, "error": err})
                continue
            print(f"{code:12s} [{stmt:8s}] {source:22s} {period} {len(rows)} 期 ({_STMT_LABELS[stmt]}):")
            for r in rows[-limit:]:
                parts = []
                for k, v in r.items():
                    if k == "period":
                        continue
                    parts.append(f"{k}=" + ("—" if v is None else f"{v / 1e8:.2f}亿"))
                print(f"    {str(r['period']):10s} " + "  ".join(parts))
            out.append({"code": code, "statement": stmt, "status": "ok", "source": source, "rows": rows[-limit:]})
    if args.json:
        with open(os.path.abspath(args.json), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("summary ->", os.path.abspath(args.json))
    return 0


def hithink_valuation(codes):
    """hithink 估值快照（PE/PB/PS/PCF，A 股）。批量一次请求。"""
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


def miniqmt_valuation(code):
    """miniQMT 无估值接口，用 最新价×总股本 / TTM财报 自算 PE/PB/PS/PCF。
    PE/PS/PCF 用 TTM（最近年报 + 最新报告期 - 上年同期）；PB 用【归母净资产】
    tot_shrhldr_eqy_excl_min_int（剔除少数股东权益，取最新报告期，缺则年报兜底）。
    已验证：茅台/五粮液 PE/PS/PCF 与 hithink 逐位一致；平安 PB 0.955 vs 0.967（~1%）；
    银行 PB 仍有永续债/其他权益工具口径差（miniQMT 无剔除字段）。pe_mrq 按最近年报口径，
    hithink 的 MRQ 定义不透明，跨源以 pe_ttm 为准。"""
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
    Y = f"{LY - 1 if LM < 12 else LY}1231"           # 最近完整年报
    L1 = f"{LY - 1}{LM:02d}{LD:02d}"                 # 上年同期
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
    # PB 分母：归母净资产（剔除少数股东权益），最新报告期优先，缺则最近年报兜底
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


def cmd_valuation(args):
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    out = []
    hk = [c for c in codes if _is_hk(c)]
    acodes = [c for c in codes if not _is_hk(c)]
    hh_map, hh_err = None, None
    if acodes and args.source in ("auto", "hithink"):
        hh_map, hh_err = hithink_valuation(acodes)
    if hk:
        for c in hk:
            # 港股估值：自动走 akshare 东财 F10 指标估值（PE/PB）
            f10out, f10err = ak_f10(c, 3)
            iv = f10out.get("指标估值") if f10out else None
            if isinstance(iv, dict) and iv.get("PE") is not None:
                print(f"{c:12s} akshare东财  PE={iv.get('PE')}  PB={iv.get('PB')}  "
                      f"净利={iv.get('净利润')} 营收={iv.get('营业收入')} ROE={iv.get('ROE%')}%")
                out.append({"code": c, "status": "ok", "source": "akshare东财",
                            "name": None, "pe_ttm": iv.get("PE"), "pe_mrq": None,
                            "pb_mrq": iv.get("PB"), "ps_ttm": None, "pcf_ttm": None})
            else:
                print(f"{c:12s} FAIL: 港股估值不可用: {f10err}")
                out.append({"code": c, "status": "fail", "source": "akshare东财", "error": f10err})
    for c in acodes:
        source = args.source
        if source == "auto":
            row = (hh_map or {}).get(c)
            if row:
                source = "hithink"
            else:
                source = "miniqmt(fallback:" + (hh_err or "?")[:40] + ")"
                row, err = miniqmt_valuation(c)
                if row is None:
                    print(f"{c:12s} FAIL ({source}): {err}")
                    out.append({"code": c, "status": "fail", "source": source, "error": err})
                    continue
        elif source == "hithink":
            row = (hh_map or {}).get(c)
            if row is None:
                print(f"{c:12s} FAIL (hithink): {hh_err}")
                out.append({"code": c, "status": "fail", "source": source, "error": hh_err})
                continue
        elif source == "miniqmt":
            row, err = miniqmt_valuation(c)
            if row is None:
                print(f"{c:12s} FAIL (miniqmt): {err}")
                out.append({"code": c, "status": "fail", "source": source, "error": err})
                continue
        elif source == "tdx":
            row, err = tdx_valuation(c)
            if row is None:
                print(f"{c:12s} FAIL (tdx): {err}")
                out.append({"code": c, "status": "fail", "source": source, "error": err})
                continue
        name = row.get("name") or ""
        print(f"{c:12s} {source:22s} {name}  PE_ttm={row.get('pe_ttm')}  PE_mrq={row.get('pe_mrq')}  "
              f"PB_mrq={row.get('pb_mrq')}  PS_ttm={row.get('ps_ttm')}  PCF_ttm={row.get('pcf_ttm')}")
        out.append({"code": c, "status": "ok", "source": source, "name": name, **{k: row.get(k) for k in ("pe_ttm", "pe_mrq", "pb_mrq", "ps_ttm", "pcf_ttm")}})
    if args.json:
        with open(os.path.abspath(args.json), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("summary ->", os.path.abspath(args.json))
    return 0


def cmd_crosscheck(args):
    """三方交叉验证：hithink / miniQMT / tdx 的收盘价与 PB 一致性（A 股）。"""
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    acodes = [c for c in codes if not _is_hk(c)]
    hk = [c for c in codes if _is_hk(c)]
    hh_val, _ = hithink_valuation(acodes) if acodes else (None, None)
    results = []
    print(f"{'股票':<8}{'源':<8}{'收盘':>10}{'PB':>8}   判定")
    for code in acodes:
        closes = {}
        for src, fn in (("hh", lambda: hithink_history(code, args.start, args.end, "none")),
                        ("mq", lambda: miniqmt_history(code, args.start, args.end, "1d", "none")),
                        ("tdx", lambda: tdx_history(code, args.start, args.end, "1d", "none"))):
            rows, err = fn()
            closes[src] = {r["date"]: r["close"] for r in rows} if rows else {}
        # 三源都有的最后一个交易日
        common = set(closes["hh"]) & set(closes["mq"]) & set(closes["tdx"])
        last_day = max(common) if common else None
        close_vals = {s: closes[s].get(last_day) for s in ("hh", "mq", "tdx")} if last_day else {}
        pb_hh = (hh_val or {}).get(code, {}).get("pb_mrq")
        pb_mq = (miniqmt_valuation(code)[0] or {}).get("pb_mrq")
        # tdx PB 用共同日期收盘价计算，与 hithink/miniQMT 同日期对齐（easy-tdx 是最新价 8-27，需对齐到共同日）
        pb_tdx = (tdx_valuation(code, asof_close=close_vals.get("tdx"))[0] or {}).get("pb_mrq") if last_day else None
        pb_vals = {"hh": pb_hh, "mq": pb_mq, "tdx": pb_tdx}
        close_ok = last_day is not None and max(abs(close_vals["hh"] - close_vals["mq"]),
                                                abs(close_vals["mq"] - close_vals["tdx"]),
                                                abs(close_vals["hh"] - close_vals["tdx"])) < 0.02
        pb_present = all(v is not None for v in pb_vals.values())
        # PB 用相对容差 5%：茅台 0.95% 日期差(放行)、招行 11.8% 真实口径错(拦)
        pb_ok = pb_present and max(
            abs(pb_vals["hh"] - pb_vals["mq"]) / max(pb_vals["hh"], pb_vals["mq"], 1e-9),
            abs(pb_vals["mq"] - pb_vals["tdx"]) / max(pb_vals["mq"], pb_vals["tdx"], 1e-9),
            abs(pb_vals["hh"] - pb_vals["tdx"]) / max(pb_vals["hh"], pb_vals["tdx"], 1e-9)) < 0.05
        for s in ("hh", "mq", "tdx"):
            d = last_day or "—"
            print(f"{code:<8}{s:<8}{close_vals.get(s, 0):>10.2f}{pb_vals.get(s) if pb_vals.get(s) else 0:>8.3f}"
                  f"   {d}")
        print(f"{'':<8}{'':<8}{'':>10}{'':>8}   close {'OK' if close_ok else 'DIFF'} | PB {'OK' if pb_ok else 'DIFF'}")
        results.append({"code": code, "last_day": last_day, "close": close_vals,
                        "pb": pb_vals, "close_ok": close_ok, "pb_ok": pb_ok})
    for code in hk:
        rows, err = miniqmt_history(code, args.start, args.end, "1d", "none")
        last = rows[-1]["close"] if rows else None
        print(f"{code:<8}miniQMT {last if last else 0:>10.2f}   （港股仅 miniQMT，无 hithink/tdx）")
        results.append({"code": code, "close": {"mq": last}, "note": "HK 仅 miniQMT"})
    n_c = sum(r["close_ok"] for r in results if "close_ok" in r)
    n_p = sum(r["pb_ok"] for r in results if "pb_ok" in r)
    n_all = len([r for r in results if "close_ok" in r])
    print(f"\n汇总: 收盘三方一致 {n_c}/{n_all} | PB 三方一致(容差0.05) {n_p}/{n_all}")
    if args.json:
        with open(os.path.abspath(args.json), "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("summary ->", os.path.abspath(args.json))
    return 0


# ---- akshare 公开源（新浪/东财，补港股行情双源 + F10 财务）----
def ak_hk_history(code, start, end):
    """新浪港股日线（ak.stock_hk_daily），与 miniQMT 港股逐日一致（已实测 10/10 天精确匹配）。"""
    if not _is_hk(code):
        return None, "ak 港股行情仅支持 .HK 代码"
    try:
        import akshare as ak
    except ImportError:
        return None, "akshare 未安装"
    try:
        df = ak.stock_hk_daily(symbol=code[:5])
    except Exception as e:
        return None, f"新浪港股调用异常: {e!r}"
    if df is None or len(df) == 0:
        return None, "新浪港股无数据"
    d0 = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
    d1 = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
    rows = []
    for _, r in df.iterrows():
        date = str(r["date"])[:10]
        if date < d0 or date > d1:
            continue
        rows.append({
            "date": date, "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
            "volume": float(r["volume"]), "amount": float(r["amount"]),
        })
    if not rows:
        return None, "新浪港股该区间无数据"
    return rows, None


def ak_us_history(code, start, end):
    """akshare 新浪美股日线（stock_us_daily）。美股第二行情源。"""
    sym = code[:-3] if code.upper().endswith(".US") else code
    try:
        import akshare as ak
    except ImportError:
        return None, "akshare 未安装"
    try:
        df = ak.stock_us_daily(symbol=sym)
    except Exception as e:
        return None, f"akshare 美股调用异常: {e!r}"
    if df is None or len(df) == 0:
        return None, "akshare 美股无数据"
    d0 = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
    d1 = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
    rows = []
    for _, r in df.iterrows():
        date = str(r["date"])[:10]
        if date < d0 or date > d1:
            continue
        rows.append({
            "date": date, "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
            "volume": float(r["volume"]), "amount": 0.0,
        })
    if not rows:
        return None, "akshare 美股该区间无数据"
    return rows, None


def ak_f10(code, limit):
    """F10 类基本面：港股(东财) 财务指标/估值/公司资料/分红；A股(同花顺) 财务摘要。
    港股财务由此补上（hithink/miniQMT/TDX 三源均无港股财务）。"""
    u = code.upper()
    try:
        import akshare as ak
    except ImportError:
        return None, "akshare 未安装"
    out = {"code": code}
    if u.endswith(".HK"):
        sym = u[:5]
        try:
            ind = ak.stock_hk_financial_indicator_em(symbol=sym)
            if ind is not None and len(ind):
                r = ind.iloc[-1]
                def g(*keys):
                    for k in keys:
                        if k in ind.columns:
                            return r[k]
                    for col in ind.columns:
                        for k in keys:
                            if k in col:
                                return r[col]
                    return None
                out["指标估值"] = {
                    "每股收益": g("每股收益"), "每股净资产": g("每股净资产"),
                    "营业收入": g("营业总收入"), "净利润": g("净利润"), "净利率%": g("销售净利率"),
                    "ROE%": g("股东权益回报率"), "PE": g("市盈率"), "PB": g("市净率"),
                    "总市值": g("总市值"), "股息率%": g("股息率"),
                }
        except Exception as e:
            out["指标估值"] = f"ERR {e!r}"
        try:
            cp = ak.stock_hk_company_profile_em(symbol=sym)
            if cp is not None and len(cp):
                r = cp.iloc[0]
                out["公司资料"] = {
                    "公司名称": r.get("公司名称"), "英文名称": r.get("英文名称"),
                    "注册地": r.get("注册地"), "所属行业": r.get("所属行业"),
                    "董事长": r.get("董事长"), "员工数量": r.get("员工数量"),
                    "公司简介": str(r.get("公司简介"))[:200],
                }
        except Exception as e:
            out["公司资料"] = f"ERR {e!r}"
        try:
            dd = ak.stock_hk_dividend_payout_em(symbol=sym)
            if dd is not None and len(dd):
                # 东财港股分红 df 为倒序（最新在前），取最新 limit 条
                out["分红历史"] = dd.head(limit).to_dict("records")
        except Exception as e:
            out["分红历史"] = f"ERR {e!r}"
        try:
            # 东财港股三大报表（正确签名：stock=代码, symbol=报表类型, indicator=年度）
            stmts = {}
            for stmt, keys in (("利润表", ["营业额", "毛利", "除税前利润", "股东应占溢利", "税项"]),
                               ("资产负债表", ["总资产", "总负债", "股东权益", "少数股东权益"]),
                               ("现金流量表", ["经营业务现金净额", "投资业务现金净额", "融资业务现金净额", "回购股份", "末现金"])):
                df = ak.stock_financial_hk_report_em(stock=sym, symbol=stmt, indicator="年度")
                if df is not None and len(df):
                    year = df["REPORT_DATE"].astype(str).str[:4].max()
                    sub = df[df["REPORT_DATE"].astype(str).str.startswith(year)]
                    stmts[f"{stmt}({year})"] = {
                        n: round(float(sub[sub["STD_ITEM_NAME"] == n]["AMOUNT"].iloc[0]) / 1e8, 1)
                        for n in keys if len(sub[sub["STD_ITEM_NAME"] == n])
                    }
            out["三大报表"] = stmts
        except Exception as e:
            out["三大报表"] = f"ERR {e!r}"
    elif u.endswith((".SH", ".SZ")):
        sym = u[:6]
        try:
            df = ak.stock_financial_abstract_ths(symbol=sym, indicator="按报告期")
            if df is not None and len(df):
                out["财务摘要"] = df.tail(limit).to_dict("records")
        except Exception as e:
            out["财务摘要"] = f"ERR {e!r}"
    else:
        return None, f"f10 暂只支持 A 股(.SH/.SZ) 与港股(.HK)：{code}"
    return out, None


def cmd_f10(args):
    for code in [c.strip() for c in args.codes.split(",") if c.strip()]:
        out, err = ak_f10(code, args.limit)
        if out is None:
            print(f"{code:12s} FAIL: {err}")
            continue
        print(f"\n===== F10: {code} =====")
        for sec, val in out.items():
            if sec == "code":
                continue
            print(f"[{sec}]")
            if isinstance(val, dict):
                for k, v in val.items():
                    print(f"   {k} = {v}")
            elif isinstance(val, list):
                for row in val[-args.limit:]:
                    print("   ", row)
            else:
                print("   ", val)
    return 0


# ---- Yahoo Finance 美股源（历史行情免费开放；v7/v10 实时/财务已鉴权 401）----
def yahoo_history(code, start, end):
    sym = code[:-3] if code.upper().endswith(".US") else code
    if not re.match(r"^[A-Za-z.\-]+$", sym):
        return None, f"yahoo 源需要美股代码（如 AAPL 或 AAPL.US）：{code}"
    d0 = int(dt.datetime(int(start[:4]), int(start[4:6]), int(start[6:8])).timestamp())
    d1 = int(dt.datetime(int(end[:4]), int(end[4:6]), int(end[6:8])).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={d0}&period2={d1}&interval=1d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return None, f"yahoo 网络/解析异常: {e!r}"
    res = (j.get("chart") or {}).get("result") or []
    if not res:
        return None, "yahoo 无数据"
    ts = res[0].get("timestamp") or []
    q = ((res[0].get("indicators") or {}).get("quote") or [{}])[0]
    rows = []
    for i, t in enumerate(ts):
        rows.append({
            "date": dt.datetime.utcfromtimestamp(int(t)).strftime("%Y-%m-%d"),
            "open": float(q["open"][i] or 0), "high": float(q["high"][i] or 0),
            "low": float(q["low"][i] or 0), "close": float(q["close"][i] or 0),
            "volume": float(q["volume"][i] or 0), "amount": 0.0,
        })
    if not rows:
        return None, "yahoo 该区间无数据"
    return rows, None


def cmd_extra(args):
    """量化辅助数据：沪深港通资金流 / 行业板块行情 / 概念板块行情 / 两融余额（akshare）+ 通达信个股资金流（easy-tdx）。"""
    try:
        import akshare as ak
    except ImportError:
        print("akshare 未安装")
        return 1
    types = ["hsgt", "industry", "concept", "margin", "fundflow"] if args.type == "all" else [args.type]
    for t in types:
        print(f"\n===== {t} =====")
        try:
            if t == "fundflow":
                if not args.code:
                    print("  fundflow 需要 --code（如 600519.SH）")
                    continue
                df, err = tdx_fundflow(args.code, args.limit or 10)
                if df is None:
                    print(f"  FAIL: {err}")
                else:
                    print(f"  {args.code} 历史资金流向（近 {len(df)} 日，单位=元）:")
                    print(df.to_string(index=False))
            elif t == "hsgt":
                df = ak.stock_hsgt_fund_flow_summary_em()
                print(df.to_string(index=False) if df is not None else "空")
            elif t == "industry":
                df = ak.stock_board_industry_summary_ths()
                if df is not None and len(df):
                    cols = df.columns[:10]
                    print(df[cols].to_string(index=False))
            elif t == "concept":
                df = ak.stock_board_concept_summary_ths()
                if df is not None and len(df):
                    cols = df.columns[:8]
                    print(df[cols].to_string(index=False))
            elif t == "margin":
                sse = ak.stock_margin_sse(start_date=args.start, end_date=args.end)
                print("上交所两融（区间）:")
                print(sse.to_string(index=False) if sse is not None else "空")
                try:
                    szse = ak.stock_margin_szse(date=args.end)
                    print("深交所两融（最新日 %s）:" % args.end)
                    print(szse.to_string(index=False) if szse is not None and len(szse) else "该日无数据")
                except Exception as e2:
                    print(f"  深交所两融失败（不影响上交所）: {e2!r}")
        except Exception as e:
            print(f"  FAIL: {e!r}")
    return 0


def cmd_history(args):
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    period = args.period
    outdir = os.path.abspath(args.outdir) if args.outdir else None
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    summary = []
    for code in codes:
        source = args.source
        rows, err = None, None
        if source == "auto":
            if code.upper().endswith(".US"):
                # 美股：yahoo 直连 → 新浪兜底（仅日线）
                source = "yahoo"
                rows, err = yahoo_history(code, args.start, args.end)
                if rows is None:
                    source = "sina(fallback:" + (err or "?")[:40] + ")"
                    rows, err2 = ak_us_history(code, args.start, args.end)
                    if rows is None:
                        err = err2
            elif _is_hk(code):
                # 港股：miniQMT → 新浪兜底（新浪仅日线）
                source = "miniqmt"
                rows, err = miniqmt_history(code, args.start, args.end, period, args.adjust)
                if rows is None and period == "1d":
                    source = "sina(fallback:" + (err or "?")[:40] + ")"
                    rows, err2 = ak_hk_history(code, args.start, args.end)
                    if rows is None:
                        err = err2
            elif period != "1d":
                # A股分钟线：miniQMT → TDX（双源）
                source = "miniqmt"
                rows, err = miniqmt_history(code, args.start, args.end, period, args.adjust)
                if rows is None:
                    source = "tdx(fallback:" + (err or "?")[:40] + ")"
                    rows, err2 = tdx_history(code, args.start, args.end, period, args.adjust)
                    if rows is None:
                        err = err2
            else:
                # A股日线：hithink → miniQMT → TDX
                rows, err = hithink_history(code, args.start, args.end, args.adjust)
                if rows is None:
                    source = "miniqmt(fallback:" + (err or "?")[:40] + ")"
                    rows, err2 = miniqmt_history(code, args.start, args.end, period, args.adjust)
                    if rows is None:
                        err = err2
                        source = "tdx(fallback:" + (err or "?")[:40] + ")"
                        rows, err3 = tdx_history(code, args.start, args.end, "1d", args.adjust)
                        if rows is None:
                            err = err3
        elif source == "hithink":
            rows, err = hithink_history(code, args.start, args.end, args.adjust)
        elif source == "miniqmt":
            rows, err = miniqmt_history(code, args.start, args.end, period, args.adjust)
        elif source == "tdx":
            rows, err = tdx_history(code, args.start, args.end, period, args.adjust)
        elif source == "sina":
            rows, err = ak_hk_history(code, args.start, args.end)
        elif source == "yahoo":
            rows, err = yahoo_history(code, args.start, args.end)

        if rows is None:
            print(f"{code:12s} FAIL ({source}): {err}")
            summary.append({"code": code, "source": source, "rows": 0, "file": None})
            continue
        path = None
        if outdir:
            fname = f"{code.replace('.', '_')}_{period}_{args.adjust}.csv"
            path = os.path.join(outdir, fname)
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
        first, last = rows[0], rows[-1]
        print(
            f"{code:12s} {source:18s} {len(rows):5d} 根  [{first['date']} .. {last['date']}]  "
            f"首收{first['close']:.2f} 末收{last['close']:.2f}" + (f"  -> {path}" if path else "")
        )
        summary.append({"code": code, "source": source, "rows": len(rows), "file": path})
    if args.json:
        with open(os.path.abspath(args.json), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print("summary ->", os.path.abspath(args.json))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="mktdata", description="hithink 优先、miniQMT 兜底的行情入口")
    sub = p.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("history", help="历史 K 线（统一输出）")
    h.add_argument("--codes", required=True, help="逗号分隔，如 00700.HK,600519.SH")
    h.add_argument("--start", required=True, help="YYYYMMDD")
    h.add_argument("--end", required=True, help="YYYYMMDD")
    h.add_argument("--period", default="1d", help="1d/5m/1m")
    h.add_argument("--adjust", default="none", choices=["none", "front", "back"], help="复权（none/front/back）")
    h.add_argument("--source", default="auto", choices=["auto", "hithink", "miniqmt", "tdx", "sina", "yahoo"], help="来源策略")
    h.add_argument("--outdir", default=None, help="每代码写一个 CSV 到此目录")
    h.add_argument("--json", default=None, help="写入汇总 JSON")
    h.set_defaults(fn=cmd_history)

    f = sub.add_parser("financial", help="财务报表（hithink 优先，miniQMT 兜底；仅 A 股，港股不支持）")
    f.add_argument("--codes", required=True, help="逗号分隔，如 600519.SH,601318.SH")
    f.add_argument("--statement", default="income", choices=["income", "balance", "cashflow", "indicators", "all"])
    f.add_argument("--period", default="annual", choices=["annual", "quarterly"])
    f.add_argument("--report", default=None, help="仅 indicators 用，形如 2025-4；缺省自动取最新年报")
    f.add_argument("--limit", type=int, default=4, help="返回最近 N 期")
    f.add_argument("--source", default="auto", choices=["auto", "hithink", "miniqmt"])
    f.add_argument("--json", default=None)
    f.set_defaults(fn=cmd_financial)

    v = sub.add_parser("valuation", help="估值快照 PE/PB/PS/PCF（hithink 优先，miniQMT 自算兜底；仅 A 股）")
    v.add_argument("--codes", required=True, help="逗号分隔，如 600519.SH,601318.SH")
    v.add_argument("--source", default="auto", choices=["auto", "hithink", "miniqmt", "tdx"])
    v.add_argument("--json", default=None)
    v.set_defaults(fn=cmd_valuation)

    x = sub.add_parser("crosscheck", help="三方交叉验证：hithink/miniQMT/tdx 的收盘与 PB 一致性（A 股）")
    x.add_argument("--codes", required=True, help="逗号分隔，如 600519.SH,000858.SZ")
    x.add_argument("--start", required=True, help="YYYYMMDD（取该区间末日的收盘对比）")
    x.add_argument("--end", required=True, help="YYYYMMDD")
    x.add_argument("--json", default=None)
    x.set_defaults(fn=cmd_crosscheck)

    f10 = sub.add_parser("f10", help="F10 基本面：港股(东财)财务/估值/资料/分红；A股(同花顺)财务摘要")
    f10.add_argument("--codes", required=True, help="逗号分隔，如 00700.HK,600519.SH")
    f10.add_argument("--limit", type=int, default=5, help="分红/财务摘要返回条数")
    f10.set_defaults(fn=cmd_f10)

    x = sub.add_parser("extra", help="量化辅助数据：hsgt(沪深港通资金)/industry(行业板块行情)/concept(概念板块行情)/margin(两融)/fundflow(个股资金流,easy-tdx)")
    x.add_argument("--type", default="all", choices=["hsgt", "industry", "concept", "margin", "fundflow", "all"])
    x.add_argument("--start", default="20260801", help="margin 区间起始 YYYYMMDD")
    x.add_argument("--end", default="20260824", help="margin 区间/最新日 YYYYMMDD")
    x.add_argument("--code", default=None, help="fundflow 用：个股代码，如 600519.SH")
    x.add_argument("--limit", type=int, default=10, help="fundflow 返回最近 N 日")
    x.set_defaults(fn=cmd_extra)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
