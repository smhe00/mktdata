#!/usr/bin/env python
"""mktdata CLI（包内模块，R1）：参数解析 → MarketData → 格式化输出。

真实 CLI 实现（console script: mktdata = mktdata.cli:main）。
scripts/mktdata.py 是兼容包装；不要在此与 scripts 各维护一份逻辑。

用法:
  mktdata history --codes 00700.HK,600519.SH,AAPL.US --start 20240101 --end 20260824 --adjust back
  mktdata financial --codes 600519.SH --statement all
  mktdata valuation --codes 600519.SH
  mktdata crosscheck --codes 600519.SH --start ... --end ...
  mktdata f10 --codes 00700.HK
  mktdata extra --type all
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

from mktdata.errors import MktDataError
from mktdata.providers.akshare import ak_f10, ak_hk_history, ak_us_history
from mktdata.providers.hithink import hithink_financial, hithink_history, hithink_indicators, hithink_valuation
from mktdata.providers.miniqmt import miniqmt_financial, miniqmt_history, miniqmt_indicators, miniqmt_valuation
from mktdata.providers.tdx import tdx_fundflow, tdx_history, tdx_valuation
from mktdata.providers.yahoo import yahoo_history
from mktdata.router import execute_financial, execute_history, execute_valuation
from mktdata.symbols import is_hk

_STMT_LABELS = {
    "income": "利润表(营收/归母净利)",
    "balance": "资产负债表(总资产/总负债/净资产)",
    "cashflow": "现金流量表(经营/投资/筹资净额)",
    "indicators": "财务指标(成长/盈利/偿债)",
}
_IND_UNITS = {"current_ratio": "倍", "revenue_yoy": "%", "np_yoy": "%", "gross_margin": "%", "net_margin": "%", "roe": "%", "debt_ratio": "%", "ocf_to_revenue": "%"}


def _print_ind(period, d):
    line = f"    {str(period):10s} "
    for k in ["revenue_yoy", "np_yoy", "gross_margin", "net_margin", "roe", "debt_ratio", "current_ratio", "ocf_to_revenue"]:
        v = d.get(k)
        unit = _IND_UNITS.get(k, "")
        line += f"{k}={('—' if v is None else f'{v:.2f}{unit}')}  "
    print(line)


def cmd_financial(args):
    from mktdata import MarketData
    md = MarketData()
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    period = args.period
    limit = args.limit
    statements = ["income", "balance", "cashflow", "indicators"] if args.statement == "all" else [args.statement]
    out = []
    for code in codes:
        for stmt in statements:
            if stmt == "indicators":
                if is_hk(code):
                    print(f"{code:12s} [indicators] 港股无财务指标（仅东财 F10 三表/估值）")
                    out.append({"code": code, "statement": stmt, "status": "fail", "source": "akshare", "error": "HK 无 indicators"})
                    continue
                # Blocker C：fallback/FY 解析都在 MarketData→router；CLI 只做 参数→打印
                try:
                    res = md.indicators(code, report=args.report, source=args.source)
                    rows, rsrc, fb = res.data, res.source, res.fallback_chain
                except MktDataError as e:
                    print(f"{code:12s} [indicators] FAIL: {e}")
                    out.append({"code": code, "statement": stmt, "status": "fail", "source": "auto", "error": str(e)})
                    continue
                source = rsrc + (f"(fallback:{fb[-1]['reason'][:40]})" if fb else "")
                report = rows.get("period") or args.report
                print(f"{code:12s} [indicators] {source:22s} 报告期 {report}（营收同比/归母同比/毛利率/净利率/ROE/负债率/流动比率/经营现金占营收）:")
                _print_ind(rows.get("period"), rows)
                out.append({"code": code, "statement": stmt, "status": "ok", "source": rsrc, "report": report, "rows": rows})
                continue

            # income/balance/cashflow：CN+HK 统一走 MarketData（Blocker A：删除港股 ak_f10 early branch）
            try:
                res = md.financial(code, stmt, period, limit, source=args.source)
                rows, rsrc, fb = res.data, res.source, res.fallback_chain
            except MktDataError as e:
                print(f"{code:12s} [{stmt:8s}] FAIL: {e}")
                out.append({"code": code, "statement": stmt, "status": "fail", "source": "auto", "error": str(e)})
                continue
            source = rsrc + (f"(fallback:{fb[-1]['reason'][:40]})" if fb else "")
            if rsrc == "akshare":
                # 港股 F10 formatter（按请求 statement 展示对应报表；取数/错误判断已在 MarketData→router）
                print(f"{code:12s} [{stmt:8s}] {source:22s} 港股财务(东财F10)：")
                iv = rows.get("指标估值") if isinstance(rows, dict) else None
                if isinstance(iv, dict):
                    for k, v in iv.items():
                        if v is not None:
                            print(f"    {k} = {v}")
                stmts = rows.get("三大报表") if isinstance(rows, dict) else None
                if isinstance(stmts, dict):
                    prefix = {"income": "利润表", "balance": "资产负债表", "cashflow": "现金流量表"}.get(stmt)
                    for k, v in stmts.items():
                        if prefix and not str(k).startswith(prefix):
                            continue
                        print(f"    {k}: {v}")
                out.append({"code": code, "statement": stmt, "status": "ok", "source": rsrc, "rows": rows})
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


def cmd_valuation(args):
    from mktdata import MarketData
    md = MarketData()
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    out = []
    for c in codes:
        # 统一走 MarketData（P0-5）
        try:
            res = md.valuation(c, source=args.source)
            row, rsrc, fb = res.data, res.source, res.fallback_chain
        except MktDataError as e:
            print(f"{c:12s} FAIL: {e}")
            out.append({"code": c, "status": "fail", "source": "auto", "error": str(e)})
            continue
        source = rsrc + (f"(fallback:{fb[-1]['reason'][:40]})" if fb else "")
        name = row.get("name") or ""
        print(f"{c:12s} {source:22s} {name}  PE_ttm={row.get('pe_ttm')}  PE_mrq={row.get('pe_mrq')}  "
              f"PB_mrq={row.get('pb_mrq')}  PS_ttm={row.get('ps_ttm')}  PCF_ttm={row.get('pcf_ttm')}")
        out.append({"code": c, "status": "ok", "source": rsrc, "name": name, **{k: row.get(k) for k in ("pe_ttm", "pe_mrq", "pb_mrq", "ps_ttm", "pcf_ttm")}})
    if args.json:
        with open(os.path.abspath(args.json), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("summary ->", os.path.abspath(args.json))
    return 0


def cmd_crosscheck(args):
    """三方交叉验证：hithink / miniQMT / tdx 的收盘价与 PB 一致性（A 股，走 MarketData P0-5）。"""
    from mktdata import MarketData
    md = MarketData()
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    acodes = [c for c in codes if not is_hk(c)]
    hk = [c for c in codes if is_hk(c)]
    results = []
    print(f"{'股票':<8}{'源':<8}{'收盘':>10}{'PB':>8}   判定")
    for code, r in md.crosscheck(acodes, args.start, args.end).items():
        d = r["last_day"] or "—"
        for s in ("hh", "mq", "tdx"):
            print(f"{code:<8}{s:<8}{r['closes'].get(s, 0):>10.2f}{r['pb'].get(s) if r['pb'].get(s) else 0:>8.3f}"
                  f"   {d}")
        print(f"{'':<8}{'':<8}{'':>10}{'':>8}   close {'OK' if r['close_ok'] else 'DIFF'} | PB {'OK' if r['pb_ok'] else 'DIFF'}")
        results.append({"code": code, "last_day": r["last_day"], "close": r["closes"],
                        "pb": r["pb"], "close_ok": r["close_ok"], "pb_ok": r["pb_ok"]})
    for code in hk:
        try:
            rows = miniqmt_history(code, args.start, args.end, "1d", "none")
            last = rows[-1]["close"] if rows else None
        except MktDataError:
            last = None
        print(f"{code:<8}miniQMT {last if last else 0:>10.2f}   （港股仅 miniQMT，无 hithink/tdx）")
        results.append({"code": code, "close": {"mq": last}, "note": "HK 仅 miniQMT"})
    n_c = sum(r["close_ok"] for r in results if "close_ok" in r)
    n_p = sum(r["pb_ok"] for r in results if "pb_ok" in r)
    n_all = len([r for r in results if "close_ok" in r])
    print(f"\n汇总: 收盘三方一致 {n_c}/{n_all} | PB 三方一致(容差5%) {n_p}/{n_all}")
    if args.json:
        with open(os.path.abspath(args.json), "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("summary ->", os.path.abspath(args.json))
    return 0


def cmd_f10(args):
    for code in [c.strip() for c in args.codes.split(",") if c.strip()]:
        try:
            out = ak_f10(code, args.limit)
        except Exception as e:
            print(f"{code:12s} FAIL: {e}")
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
                try:
                    df = tdx_fundflow(args.code, args.limit or 10)
                    print(f"  {args.code} 历史资金流向（近 {len(df)} 日，单位=元）:")
                    print(df.to_string(index=False))
                except MktDataError as e:
                    print(f"  FAIL: {e}")
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
    from mktdata import MarketData
    md = MarketData()
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    period = args.period
    outdir = os.path.abspath(args.outdir) if args.outdir else None
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    summary = []
    results = md.history(codes, args.start, args.end, period, args.adjust, source=args.source)
    for code, res in results.items():
        # 路由/fallback 统一由 MarketData→router 负责（P0-1/P0-2）
        source = res.source + (f"(fallback:{res.fallback_chain[-1]['reason'][:40]})" if res.fallback_chain else "")
        rows, err = res.data, res.error
        if not res.ok or rows is None:
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
            f"{code:12s} {source:18s} {len(rows):5d} 根  [{first['datetime']} .. {last['datetime']}]  "
            f"首收{first['close']:.2f} 末收{last['close']:.2f}" + (f"  -> {path}" if path else "")
        )
        summary.append({"code": code, "source": source, "rows": len(rows), "file": path})
    if args.json:
        with open(os.path.abspath(args.json), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print("summary ->", os.path.abspath(args.json))
    return 0


def _configure_stdio():
    """Windows 部分 locale 下 stdout/pipe 非 UTF-8，含中文帮助会 UnicodeEncodeError。
    程序自身处理（不要求用户设 PYTHONUTF8 / PYTHONIOENCODING）。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main(argv=None):
    _configure_stdio()
    p = argparse.ArgumentParser(prog="mktdata", description="本地 miniQMT 可用时优先，多源自动 fallback 的市场数据入口")
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

    f = sub.add_parser("financial", help="财务报表（A股：miniQMT→hithink；港股：Eastmoney F10）",
                       description="财务报表：A股 miniQMT→hithink；港股 Eastmoney F10")
    f.add_argument("--codes", required=True, help="逗号分隔，如 600519.SH,601318.SH")
    f.add_argument("--statement", default="income", choices=["income", "balance", "cashflow", "indicators", "all"])
    f.add_argument("--period", default="annual", choices=["annual", "quarterly"])
    f.add_argument("--report", default=None, help="仅 indicators 用，形如 2025-4；缺省自动取最新年报")
    f.add_argument("--limit", type=int, default=4, help="返回最近 N 期")
    f.add_argument("--source", default="auto", choices=["auto", "hithink", "miniqmt"])
    f.add_argument("--json", default=None)
    f.set_defaults(fn=cmd_financial)

    v = sub.add_parser("valuation", help="估值快照 PE/PB/PS/PCF（A股：miniQMT→hithink→TDX；港股：Eastmoney）",
                       description="估值：A股 miniQMT→hithink→TDX；港股 Eastmoney")
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
    raise SystemExit(main())
