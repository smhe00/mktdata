"""统一参数校验（P1L-2）。

非法输入在进入 provider 之前统一抛 InvalidParameter，避免同一种非法输入
在不同 source 上报出不同异常行为。Provider 仍保留必要的 source-specific 防御。

validate_date / validate_date_range 返回规范化 YYYYMMDD（同时接受 YYYY-MM-DD），
保证下游 provider（期望 YYYYMMDD）行为一致。
"""

import datetime as _dt

from .errors import InvalidParameter

VALID_PERIODS = {"1d", "1m", "5m", "15m", "30m", "60m"}
VALID_ADJUSTS = {"none", "front", "back"}
VALID_STATEMENTS = {"income", "balance", "cashflow"}
VALID_FINANCIAL_PERIODS = {"annual", "quarterly"}

VALID_SOURCES = {
    "history": {"auto", "hithink", "miniqmt", "tdx", "sina", "yahoo"},
    "financial": {"auto", "hithink", "miniqmt", "akshare"},
    "valuation": {"auto", "hithink", "miniqmt", "tdx", "akshare"},
    "indicators": {"auto", "hithink", "miniqmt"},
}


def validate_date(value, name="date"):
    """校验日期。接受 YYYYMMDD / YYYY-MM-DD；返回规范化 YYYYMMDD。"""
    if value is None or not isinstance(value, str) or not value.strip():
        raise InvalidParameter(f"{name} 必须是非空字符串，得到 {value!r}")
    s = value.strip()
    if len(s) == 8 and s.isdigit():
        norm = s
        s2 = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    elif len(s) == 10 and s[4] == "-" and s[7] == "-":
        s2 = s
        norm = f"{s[:4]}{s[5:7]}{s[8:10]}"
    else:
        raise InvalidParameter(f"{name} 非法日期格式 {value!r}（需要 YYYYMMDD 或 YYYY-MM-DD）")
    try:
        _dt.datetime.strptime(s2, "%Y-%m-%d")
    except ValueError:
        raise InvalidParameter(f"{name} 非法日期 {value!r}（该日不存在）")
    return norm


def validate_date_range(start, end):
    """校验并规范化 start/end，start > end 抛 InvalidParameter。返回 (norm_start, norm_end)。"""
    ns = validate_date(start, "start")
    ne = validate_date(end, "end")
    if ns > ne:
        raise InvalidParameter(f"start({start}) 不能晚于 end({end})")
    return ns, ne


def validate_period(period):
    if period is None or period not in VALID_PERIODS:
        raise InvalidParameter(f"非法 period {period!r}（支持 {sorted(VALID_PERIODS)}）")
    return period


def validate_adjust(adjust):
    if adjust is None or adjust not in VALID_ADJUSTS:
        raise InvalidParameter(f"非法 adjust {adjust!r}（支持 none/front/back）")
    return adjust


def validate_source(capability, source):
    allowed = VALID_SOURCES.get(capability)
    if allowed is None:
        raise InvalidParameter(f"未知 capability {capability!r}（无法校验 source）")
    if source is None or source not in allowed:
        raise InvalidParameter(f"非法 source {source!r}（{capability} 支持 {sorted(allowed)}）")
    return source


def validate_statement(statement):
    if statement is None or statement not in VALID_STATEMENTS:
        raise InvalidParameter(f"非法 statement {statement!r}（支持 income/balance/cashflow）")
    return statement


def validate_financial_period(period):
    """财务报表报告期校验（B5）：仅 annual / quarterly。不要与 history validate_period 混用。"""
    if period is None or period not in VALID_FINANCIAL_PERIODS:
        raise InvalidParameter(f"非法 financial period {period!r}（支持 annual/quarterly）")
    return period
