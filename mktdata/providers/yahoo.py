"""Yahoo Finance provider：美股日线（chart 端点免费开放；v7/v10 实时/财务已鉴权 401）。"""

import datetime as dt
import json
import re
import urllib.error
import urllib.request

from ..errors import (
    InvalidSymbol,
    ProviderDataEmpty,
    ProviderUnavailable,
)
from ..normalize import norm_num


def yahoo_history(code, start, end):
    sym = code[:-3] if code.upper().endswith(".US") else code
    if not re.match(r"^[A-Za-z.\-]+$", sym):
        raise InvalidSymbol(f"yahoo 源需要美股代码（如 AAPL 或 AAPL.US）：{code}")
    d0 = int(dt.datetime(int(start[:4]), int(start[4:6]), int(start[6:8])).timestamp())
    d1 = int(dt.datetime(int(end[:4]), int(end[4:6]), int(end[6:8])).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={d0}&period2={d1}&interval=1d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ProviderUnavailable("yahoo HTTP 401（实时/财务端点已鉴权，chart 应可用）")
        raise ProviderUnavailable(f"yahoo HTTP {e.code}: {e.reason}")
    except Exception as e:
        raise ProviderUnavailable(f"yahoo 网络/解析异常: {e!r}")
    res = (j.get("chart") or {}).get("result") or []
    if not res:
        raise ProviderDataEmpty("yahoo 无数据")
    ts = res[0].get("timestamp") or []
    q = ((res[0].get("indicators") or {}).get("quote") or [{}])[0]
    rows = []
    for i, t in enumerate(ts):
        rows.append({
            "date": dt.datetime.utcfromtimestamp(int(t)).strftime("%Y-%m-%d"),
            "open": norm_num(q["open"][i]), "high": norm_num(q["high"][i]),
            "low": norm_num(q["low"][i]), "close": norm_num(q["close"][i]),
            "volume": norm_num(q["volume"][i]),  # Yahoo volume 原始=股（shares）
            "amount": None,  # Yahoo chart 无可靠成交额字段 → None（不得伪造成 0，A 项）
        })
    if not rows:
        raise ProviderDataEmpty("yahoo 该区间无数据")
    return rows
