#!/usr/bin/env python
"""miniQMT 数据查询 CLI（只读）。

封装 xtquant.xtdata 对本机 miniQMT 数据服务（默认 127.0.0.1:58610）的常用查询，
避免每次重新写脚本。要求 miniQMT 终端（XtMiniQmt/miniquote）正在运行，且当前
Python 已安装 xtquant（本项目用: D:\\gitee\\miniQMT\\.venv\\Scripts\\python.exe）。

用法示例:
  python qmt.py connect
  python qmt.py history --code 00700.HK --period 1d --start 20240101 --end 20260824 --adjust back --csv out.csv
  python qmt.py quote  --code 00700.HK 600519.SH
  python qmt.py dividends --code 00700.HK --start 20200101 --end 20260824
  python qmt.py instrument --code 00700.HK
  python qmt.py calendar --market HK --start 20260801 --end 20260824
"""
from __future__ import annotations

import argparse
import csv
import os
import sys


def _connect():
    try:
        from xtquant import xtdata
    except ImportError:
        sys.exit(
            "ERROR: xtquant 未安装。请用 miniQMT 项目的 venv 运行本脚本，例如:\n"
            "  D:\\gitee\\miniQMT\\.venv\\Scripts\\python.exe qmt.py ..."
        )
    xtdata.enable_hello = False  # 关闭欢迎横幅
    xtdata.connect()
    return xtdata


def _fmt_time(ms: int) -> str:
    from datetime import datetime, timedelta
    # 行情/交易日时间戳为毫秒（北京时间 UTC+8）
    return (datetime(1970, 1, 1) + timedelta(milliseconds=ms + 8 * 3600 * 1000)).strftime("%Y-%m-%d")


def _fmt_ymd(x) -> str:
    # 历史 K 线索引为 YYYYMMDD 整数
    x = int(x)
    return f"{x // 10000:04d}-{(x // 100) % 100:02d}-{x % 100:02d}"


def cmd_connect(xt, args):
    ddir = xt.get_data_dir()
    print("OK 已连接本机 miniQMT 数据服务")
    print(f"   数据目录: {ddir}")
    return 0


def cmd_history(xt, args):
    code = args.code
    period = args.period
    start, end = args.start or "", args.end or ""
    adj = args.adjust or "none"
    if not start or not end:
        sys.exit("ERROR: history 需要 --start 与 --end（YYYYMMDD）")
    xt.download_history_data(code, period=period, start_time=start, end_time=end)
    data = xt.get_market_data_ex(
        [], [code], period=period, start_time=start, end_time=end, dividend_type=adj
    )
    df = data.get(code, None)
    if df is None or len(df) == 0:
        print(f"NO DATA: {code} {period} [{start}..{end}] adjust={adj}")
        return 1
    rows = []
    for t, r in df.iterrows():
        rows.append(
            {
                "date": _fmt_ymd(int(t)),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
                "amount": float(r["amount"]),
            }
        )
    first, last = rows[0], rows[-1]
    print(f"{code} {period} adjust={adj}  共 {len(rows)} 根  [{first['date']} .. {last['date']}]")
    print(f"  首: 开{first['open']:.2f} 收{first['close']:.2f}   末: 开{last['open']:.2f} 收{last['close']:.2f}")
    tail = rows[-args.tail:] if args.tail else rows[-5:]
    for r in tail:
        print(f"  {r['date']}  O{r['open']:.2f} H{r['high']:.2f} L{r['low']:.2f} C{r['close']:.2f} 量{r['volume']:.0f}")
    if args.csv:
        path = os.path.abspath(args.csv)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"  已落盘 CSV: {path}")
    if args.json:
        path = os.path.abspath(args.json)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"code": code, "period": period, "adjust": adj, "rows": rows}, f, ensure_ascii=False)
        print(f"  已落盘 JSON: {path}")
    return 0


def cmd_quote(xt, args):
    codes = args.code
    t = xt.get_full_tick(codes)
    for code in codes:
        d = t.get(code)
        if d is None:
            print(f"{code}: 无行情")
            continue
        print(
            f"{code}  last={d.get('lastPrice')}  prev={d.get('lastClose')}  "
            f"open={d.get('open')}  high={d.get('high')}  low={d.get('low')}  "
            f"volume={d.get('volume')}  amount={d.get('amount')}  time={_fmt_time(d.get('time') or 0)}"
        )
    return 0


def cmd_dividends(xt, args):
    df = xt.get_divid_factors(args.code, args.start or "", args.end or "")
    if df is None or len(df) == 0:
        print(f"{args.code}: 无分红除权记录")
        return 1
    print(f"{args.code} 分红/送转/除权记录 {len(df)} 条:")
    for t, r in df.iterrows():
        print(
            f"  {_fmt_time(int(t))} 每股现金={r.get('interest')} 送股={r.get('stockBonus')} "
            f"转增={r.get('stockGift')} 配股={r.get('allotNum')} 复权因子dr={r.get('dr')}"
        )
    return 0


def cmd_instrument(xt, args):
    d = xt.get_instrument_detail(args.code)
    if not d:
        print(f"{args.code}: 未找到（检查代码格式，如 600519.SH / 00700.HK）")
        return 1
    keep = [
        "InstrumentID", "ExchangeID", "InstrumentName", "SecType", "OpenDate",
        "PreClose", "LastPrice", "ContractMultiplierUnit", "LotSize",
    ]
    print(f"{args.code}:")
    for k in keep:
        if k in d:
            print(f"  {k} = {d[k]}")
    return 0


def cmd_calendar(xt, args):
    ds = xt.get_trading_dates(args.market, args.start or "", args.end or "")
    if not ds:
        print(f"{args.market}: 无交易日数据")
        return 1
    days = [_fmt_time(int(x)) for x in ds]
    print(f"{args.market} 交易日 {len(days)} 天: {', '.join(days[:10])}{' ...' if len(days) > 10 else ''}")
    return 0


def cmd_sector(xt, args):
    codes = xt.get_stock_list_in_sector(args.name)
    if not codes:
        print(f"板块 '{args.name}' 无成分（可用名称如 '上证50'、'沪深300'、'HK'）")
        return 1
    print(f"板块 '{args.name}' 成分 {len(codes)} 个: {', '.join(codes[:20])}{' ...' if len(codes) > 20 else ''}")
    return 0


def main(argv=None):
    xt = _connect()
    p = argparse.ArgumentParser(prog="qmt", description="miniQMT 只读数据查询")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("connect", help="测试连接并显示数据目录")
    c.set_defaults(fn=cmd_connect)

    h = sub.add_parser("history", help="历史 K 线")
    h.add_argument("--code", required=True)
    h.add_argument("--period", default="1d", help="1d/5m/1m 等")
    h.add_argument("--start", required=True, help="YYYYMMDD")
    h.add_argument("--end", required=True, help="YYYYMMDD")
    h.add_argument("--adjust", default="none", choices=["none", "front", "back"], help="复权: none=不复权 front=前复权 back=后复权(含分红)")
    h.add_argument("--tail", type=int, default=5, help="打印末尾行数")
    h.add_argument("--csv", default=None)
    h.add_argument("--json", default=None)
    h.set_defaults(fn=cmd_history)

    q = sub.add_parser("quote", help="最新快照")
    q.add_argument("--code", nargs="+", required=True)
    q.set_defaults(fn=cmd_quote)

    d = sub.add_parser("dividends", help="分红/除权因子")
    d.add_argument("--code", required=True)
    d.add_argument("--start", default="")
    d.add_argument("--end", default="")
    d.set_defaults(fn=cmd_dividends)

    i = sub.add_parser("instrument", help="证券基础资料")
    i.add_argument("--code", required=True)
    i.set_defaults(fn=cmd_instrument)

    c = sub.add_parser("calendar", help="交易日历")
    c.add_argument("--market", required=True, help="SH/SZ/HK 等")
    c.add_argument("--start", default="")
    c.add_argument("--end", default="")
    c.set_defaults(fn=cmd_calendar)

    s = sub.add_parser("sector", help="板块成分")
    s.add_argument("--name", required=True)
    s.set_defaults(fn=cmd_sector)

    args = p.parse_args(argv)
    return args.fn(xt, args)


if __name__ == "__main__":
    sys.exit(main())
