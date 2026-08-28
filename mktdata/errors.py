"""mktdata 统一异常模型。

fallback 策略按错误类型区分，因此禁止把不同失败混成普通字符串。
"""


class MktDataError(Exception):
    """所有 mktdata 异常的基类。"""


class ProviderUnavailable(MktDataError):
    """数据源不可达（网络 / 服务端失败 / 超时）。应尝试 fallback 或重试。"""


class ProviderUnsupported(MktDataError):
    """数据源不支持该请求（如 TDX 不支持 HK、Yahoo 只支持 US）。不应重试。"""


class ProviderDataEmpty(MktDataError):
    """数据源返回空数据（非交易日 / 该区间无数据 / 无该标的）。"""


class ProviderAuthError(MktDataError):
    """认证失败（API key 缺失 / 无效）。"""


class ProviderRateLimited(MktDataError):
    """限流。应退避重试或换源。"""


class InvalidSymbol(MktDataError):
    """证券代码非法 / 无法识别市场。"""


class InvalidParameter(MktDataError):
    """参数非法（如 start > end、非法 period）。"""
