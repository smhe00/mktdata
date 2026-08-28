"""Yahoo Finance provider：美股日线（chart 端点免费开放；v7/v10 实时/财务已鉴权 401）。"""

import datetime as dt
import json
import re
import urllib.request


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
