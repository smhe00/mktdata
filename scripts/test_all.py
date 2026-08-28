"""mktdata 全量集成回归（V1.1 P0 契约）：6 子命令 × 全部源 + 跨源一致性 + P0 契约。

provider 契约（V1.1 P0-3）：成功直接返回 rows/dict；失败抛 MktDataError（case 包装成 EXC fail）。
"""
import sys, subprocess, json, datetime, os, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))  # 仓库根：import mktdata 解析到包
import mktdata

PY = sys.executable  # 用当前解释器，避免硬编码本机路径（P1-2）
MKT = os.path.join(HERE, 'mktdata.py')
results = []


def case(name, fn):
    try:
        out = fn()
        ok = out.get("ok", False)
        detail = out.get("detail", "")
        results.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    except Exception as e:
        results.append((name, False, f"EXC {e!r}"))
        print(f"  [FAIL] {name}  EXC {e!r}")


def ok_rows(rows, min_n=1):
    return rows is not None and (isinstance(rows, (list, dict)) and len(rows) >= min_n)


print("========== A. 行情（history 各源） ==========")
case("A股日线 auto(后复权)", lambda: {"ok": ok_rows(mktdata.hithink_history("600519.SH","20260801","20260824","back"))})
case("A股日线 miniqmt(后复权)", lambda: {"ok": ok_rows(mktdata.miniqmt_history("600519.SH","20260801","20260824","1d","back"))})
case("A股日线 tdx(原始)", lambda: {"ok": ok_rows(mktdata.tdx_history("600519.SH","20260801","20260824","1d","none"))})
case("A股日线 hithink(原始)", lambda: {"ok": ok_rows(mktdata.hithink_history("000858.SZ","20260801","20260824","none"))})
case("A股5m miniqmt", lambda: {"ok": ok_rows(mktdata.miniqmt_history("600519.SH","20260820","20260820","5m","none"))})
case("A股5m tdx", lambda: {"ok": ok_rows(mktdata.tdx_history("600519.SH","20260820","20260820","5m","none"))})
case("港股日线 miniqmt", lambda: {"ok": ok_rows(mktdata.miniqmt_history("00700.HK","20260801","20260824","1d","none"))})
case("港股日线 sina", lambda: {"ok": ok_rows(mktdata.ak_hk_history("00700.HK","20260801","20260824"))})
case("美股日线 yahoo", lambda: {"ok": ok_rows(mktdata.yahoo_history("AAPL.US","20260801","20260821"))})
case("美股日线 akshare-sina", lambda: {"ok": ok_rows(mktdata.ak_us_history("AAPL.US","20260801","20260821"))})

print("\n========== B. 跨源一致性（P0-1/P0-2） ==========")
def tdx_vs_mq_1d():
    tdx = mktdata.tdx_history("600519.SH","20260814","20260824","1d","none")
    mq = mktdata.miniqmt_history("600519.SH","20260814","20260824","1d","none")
    tm = {r['date']: r['close'] for r in tdx}; mm = {r['date']: r['close'] for r in mq}
    common = set(tm) & set(mm)
    bad = [d for d in common if abs(tm[d]-mm[d]) > 0.02]
    return {"ok": len(common) > 0 and len(bad) == 0, "detail": f"共同{len(common)}天 差异{len(bad)}"}
case("A股日线 tdx vs miniqmt(收盘)", tdx_vs_mq_1d)

def tdx_vs_mq_vol():
    # P0-2: volume 统一 shares（miniQMT 手×100 vs tdx 原始股）同日期应在容差内一致
    tdx = mktdata.tdx_history("600519.SH","20260818","20260824","1d","none")
    mq = mktdata.miniqmt_history("600519.SH","20260818","20260824","1d","none")
    tm = {r['date']: r['volume'] for r in tdx}; mm = {r['date']: r['volume'] for r in mq}
    common = set(tm) & set(mm)
    bad = [d for d in common if abs(tm[d]-mm[d])/max(tm[d], 1) > 0.05]
    return {"ok": len(common) > 0 and len(bad) == 0, "detail": f"共同{len(common)}天 量差>5%的{len(bad)}"}
case("A股日线 volume(shares) tdx vs miniqmt", tdx_vs_mq_vol)

def tdx_vs_mq_5m():
    tdx = mktdata.tdx_history("600519.SH","20260820","20260820","5m","none")
    mq = mktdata.miniqmt_history("600519.SH","20260820","20260820","5m","none")
    tm = {r['datetime'] if 'datetime' in r else r['date']: r['close'] for r in tdx}
    mm = {r['datetime'] if 'datetime' in r else r['date']: r['close'] for r in mq}
    common = set(tm) & set(mm)
    bad = [d for d in common if abs(tm[d]-mm[d]) > 0.02]
    return {"ok": len(common) > 0 and len(bad) == 0, "detail": f"共同{len(common)}点 差异{len(bad)}"}
case("A股5m tdx vs miniqmt", tdx_vs_mq_5m)

def sina_vs_mq_hk():
    sn = mktdata.ak_hk_history("00700.HK","20260810","20260824")
    mq = mktdata.miniqmt_history("00700.HK","20260810","20260824","1d","none")
    sm = {r['date']: r['close'] for r in sn}; mm = {r['date']: r['close'] for r in mq}
    common = set(sm) & set(mm)
    bad = [d for d in common if abs(sm[d]-mm[d]) > 0.02]
    return {"ok": len(common) > 0 and len(bad) == 0, "detail": f"共同{len(common)}天 差异{len(bad)}"}
case("港股日线 sina vs miniqmt", sina_vs_mq_hk)

print("\n========== C. 财务（financial） ==========")
case("A股利润表 auto(hithink)", lambda: {"ok": ok_rows(mktdata.hithink_financial("600519.SH","income","annual",2))})
case("A股利润表 miniqmt", lambda: {"ok": ok_rows(mktdata.miniqmt_financial("600519.SH","income","annual",2))})
case("A股资产负债表 miniqmt", lambda: {"ok": ok_rows(mktdata.miniqmt_financial("600519.SH","balance","annual",2))})
case("A股现金流 miniqmt", lambda: {"ok": ok_rows(mktdata.miniqmt_financial("600519.SH","cashflow","annual",2))})
case("A股指标 auto(hithink)", lambda: {"ok": ok_rows(mktdata.hithink_indicators("600519.SH","2025-4"))})
case("A股指标 miniqmt自算", lambda: {"ok": ok_rows(mktdata.miniqmt_indicators("600519.SH",2025))})
def hk_fin():
    out = mktdata.ak_f10("00700.HK", 3)
    return {"ok": isinstance(out.get("指标估值"), dict) and out["指标估值"].get("PE") is not None,
            "detail": f"PE={out['指标估值'].get('PE') if out else '?'}"}
case("港股财务 auto(东财F10)", hk_fin)

print("\n========== D. 估值（valuation） ==========")
case("A股估值 auto(hithink)", lambda: {"ok": ok_rows(mktdata.hithink_valuation(["600519.SH"]))})
def mq_val():
    r = mktdata.miniqmt_valuation("600519.SH")
    return {"ok": isinstance(r, dict) and r.get("pb_mrq") is not None, "detail": f"PB={r.get('pb_mrq')}"}
case("A股估值 miniqmt自算", mq_val)
def tdx_val():
    r = mktdata.tdx_valuation("600519.SH")
    return {"ok": isinstance(r, dict) and r.get("pb_mrq") is not None, "detail": f"PB={r.get('pb_mrq')}"}
case("A股估值 tdx(每股净资产)", tdx_val)
def pb_3way():
    hh = mktdata.hithink_valuation(["600519.SH"])
    mq = mktdata.miniqmt_valuation("600519.SH")
    tx = mktdata.tdx_valuation("600519.SH")
    a, b, c = hh["600519.SH"]["pb_mrq"], mq["pb_mrq"], tx["pb_mrq"]
    return {"ok": all((a, b, c)) and max(abs(a-b)/max(a,b,1e-9), abs(b-c)/max(b,c,1e-9), abs(a-c)/max(a,c,1e-9)) < 0.05, "detail": f"hh={a:.3f} mq={b:.3f} tdx={c:.3f}"}
case("A股PB 三源一致(茅台)", pb_3way)

print("\n========== E. F10 / extra ==========")
def f10_a():
    out = mktdata.ak_f10("600519.SH", 2)
    return {"ok": isinstance(out, dict) and "财务摘要" in out, "detail": "A股同花顺财务摘要"}
case("f10 A股(同花顺摘要)", f10_a)
def f10_hk():
    out = mktdata.ak_f10("00700.HK", 2)
    return {"ok": isinstance(out, dict) and "三大报表" in out and "分红历史" in out, "detail": "港股东财F10"}
case("f10 港股(东财: 指标/报表/分红)", f10_hk)
def extra_hsgt():
    import akshare as ak
    df = ak.stock_hsgt_fund_flow_summary_em()
    return {"ok": df is not None and len(df) > 0, "detail": f"{len(df)}行"}
case("extra 沪深港通资金", extra_hsgt)
def extra_industry():
    import akshare as ak
    df = ak.stock_board_industry_summary_ths()
    return {"ok": df is not None and len(df) > 0, "detail": f"{len(df)}板块"}
case("extra 行业板块行情", extra_industry)
def extra_margin():
    import akshare as ak
    df = ak.stock_margin_sse(start_date="20260820", end_date="20260824")
    return {"ok": df is not None and len(df) > 0, "detail": f"{len(df)}天"}
case("extra 上交所两融", extra_margin)

print("\n========== F. CLI 端到端（subprocess） ==========")
def cli(args):
    r = subprocess.run([PY, MKT] + args, capture_output=True, text=True, encoding='utf-8', timeout=120)
    return r.returncode == 0
case("CLI history auto(三市场)", lambda: {"ok": cli(["history","--codes","600519.SH,00700.HK,AAPL.US","--start","20260814","--end","20260821","--adjust","none"]), "detail": "6子命令路由"})
case("CLI crosscheck", lambda: {"ok": cli(["crosscheck","--codes","600519.SH,000858.SZ","--start","20260818","--end","20260824"]), "detail": "三方对账"})
case("CLI f10 港股", lambda: {"ok": cli(["f10","--codes","00700.HK","--limit","1"]), "detail": "F10港股"})
case("CLI extra all", lambda: {"ok": cli(["extra","--type","all","--start","20260818","--end","20260824"]), "detail": "量化辅助"})

print("\n========== 汇总 ==========")
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"通过 {passed}/{total}")
for n, ok, d in results:
    if not ok:
        print(f"  FAILED: {n} -> {d}")
with open(os.path.join(tempfile.gettempdir(), "mktdata_full_test.json"), "w", encoding="utf-8") as f:
    json.dump({"asof": str(datetime.date.today()), "passed": passed, "total": total, "results": results}, f, ensure_ascii=False, indent=2)
print(f"-> {os.path.join(tempfile.gettempdir(), 'mktdata_full_test.json')}")
sys.exit(0 if passed == total else 1)
