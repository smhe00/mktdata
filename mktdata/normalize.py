"""日期 / 数值归一化工具。"""

import datetime as _dt

_EPOCH = _dt.datetime(1970, 1, 1)


def norm_date_ymd(x) -> str:
    """YYYYMMDD 整数/字符串 → 'YYYY-MM-DD'；已是 'YYYY-MM-DD' 则幂等返回。"""
    s = str(x).strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s  # 已格式化
    s = str(int(x))
    if len(s) >= 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def norm_dt_ymd(x) -> str:
    """14 位 YYYYMMDDHHMMSS → 'YYYY-MM-DD HH:MM'；8 位则退回日期。"""
    s = str(int(x))
    if len(s) >= 14:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"
    return norm_date_ymd(s)


def norm_num(v):
    """安全转 float；失败或 NaN → None。"""
    try:
        v = float(v)
        return None if v != v else v
    except Exception:
        return None


def norm_date_ms(ms: int) -> str:
    """毫秒时间戳（北京时间 UTC+8）→ 'YYYY-MM-DD'。"""
    return (_EPOCH + _dt.timedelta(milliseconds=int(ms) + 8 * 3600 * 1000)).strftime("%Y-%m-%d")


def to_ms_utc(s: str) -> int:
    """'YYYYMMDD' → 毫秒（UTC）。"""
    return int(
        _dt.datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), tzinfo=_dt.timezone.utc).timestamp() * 1000
    )


def normalize_history_rows(rows, symbol, source, period="1d"):
    """provider 原始行 → canonical history schema（P0-1）。

    输入行含 date/datetime、open/high/low/close/volume/amount（缺失保留 None）；
    输出 {symbol, datetime, open, high, low, close, volume, amount, source}。
    datetime：日线 YYYY-MM-DD；分钟 YYYY-MM-DD HH:MM。
    """
    out = []
    for r in rows or []:
        out.append({
            "symbol": symbol,
            "datetime": r.get("datetime", r.get("date")),
            "open": norm_num(r.get("open")),
            "high": norm_num(r.get("high")),
            "low": norm_num(r.get("low")),
            "close": norm_num(r.get("close")),
            "volume": norm_num(r.get("volume")),
            "amount": norm_num(r.get("amount")),
            "source": source,
        })
    return out
