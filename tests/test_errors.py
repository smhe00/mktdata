"""errors 纯单元测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata import errors


def test_hierarchy():
    for name in ["ProviderUnavailable", "ProviderUnsupported", "ProviderDataEmpty",
                 "ProviderAuthError", "ProviderRateLimited", "InvalidSymbol", "InvalidParameter"]:
        cls = getattr(errors, name)
        assert issubclass(cls, errors.MktDataError)


def test_errors_are_distinct():
    names = ["ProviderUnavailable", "ProviderUnsupported", "ProviderDataEmpty",
             "ProviderAuthError", "ProviderRateLimited"]
    classes = [getattr(errors, n) for n in names]
    for i, a in enumerate(classes):
        for b in classes[i + 1:]:
            assert a is not b  # 每种失败类型必须可区分（fallback 策略不同）


def test_raise_and_message():
    with pytest.raises(errors.InvalidSymbol, match="无法识别"):
        raise errors.InvalidSymbol("无法识别证券代码: X")
