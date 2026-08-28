"""akshare provider：新浪港股日线 / 新浪美股日线 / 东财·同花顺 F10（港股财务/估值/资料/分红、A股财务摘要）。"""

from ..errors import (
    ProviderDataEmpty,
    ProviderUnsupported,
    ProviderUnavailable,
)
from ..normalize import norm_num
from ..symbols import is_hk


def _ak():
    try:
        import akshare as ak
    except ImportError:
        raise ProviderUnavailable("akshare 未安装")
    return ak


def ak_hk_history(code, start, end):
    if not is_hk(code):
        raise ProviderUnsupported("ak 港股行情仅支持 .HK 代码")
    ak = _ak()
    try:
        df = ak.stock_hk_daily(symbol=code[:5])
    except Exception as e:
        raise ProviderUnavailable(f"新浪港股调用异常: {e!r}")
    if df is None or len(df) == 0:
        raise ProviderDataEmpty("新浪港股无数据")
    d0 = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
    d1 = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
    rows = []
    for _, r in df.iterrows():
        date = str(r["date"])[:10]
        if date < d0 or date > d1:
            continue
        rows.append({
            "date": date, "open": norm_num(r["open"]), "high": norm_num(r["high"]),
            "low": norm_num(r["low"]), "close": norm_num(r["close"]),
            "volume": norm_num(r["volume"]), "amount": norm_num(r["amount"]),
        })
    if not rows:
        raise ProviderDataEmpty("新浪港股该区间无数据")
    return rows


def ak_us_history(code, start, end):
    sym = code[:-3] if code.upper().endswith(".US") else code
    ak = _ak()
    try:
        df = ak.stock_us_daily(symbol=sym)
    except Exception as e:
        raise ProviderUnavailable(f"akshare 美股调用异常: {e!r}")
    if df is None or len(df) == 0:
        raise ProviderDataEmpty("akshare 美股无数据")
    d0 = f"{start[:4]}-{start[4:6]}-{start[6:8]}"
    d1 = f"{end[:4]}-{end[4:6]}-{end[6:8]}"
    rows = []
    for _, r in df.iterrows():
        date = str(r["date"])[:10]
        if date < d0 or date > d1:
            continue
        rows.append({
            "date": date, "open": norm_num(r["open"]), "high": norm_num(r["high"]),
            "low": norm_num(r["low"]), "close": norm_num(r["close"]),
            "volume": norm_num(r["volume"]), "amount": 0.0,
        })
    if not rows:
        raise ProviderDataEmpty("akshare 美股该区间无数据")
    return rows


def ak_f10(code, limit):
    """F10 类基本面：港股(东财) 财务指标/估值/公司资料/分红；A股(同花顺) 财务摘要。"""
    u = code.upper()
    ak = _ak()
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
                out["分红历史"] = dd.head(limit).to_dict("records")
        except Exception as e:
            out["分红历史"] = f"ERR {e!r}"
        try:
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
        raise ProviderUnsupported(f"f10 暂只支持 A 股(.SH/.SZ) 与港股(.HK)：{code}")
    return out
