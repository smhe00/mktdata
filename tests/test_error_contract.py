"""README「返回结果与错误处理」契约回归（小白改版 §6 所指的真实行为）。

锁定契约：
  - history() 全部源失败 -> 返回 DataResult(ok=False, error, fallback_chain)，不抛异常
  - financial()/indicators()/valuation() 无可用源 -> 抛 MktDataError
  - 参数非法 -> InvalidParameter
  - 证券代码非法 -> InvalidSymbol
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata import MarketData
from mktdata import router
from mktdata.errors import InvalidParameter, InvalidSymbol, MktDataError
from mktdata.models import DataResult


def test_history_all_fail_returns_ok_false_not_raise(monkeypatch):
    """history 全源失败 -> ok=False + fallback_chain，不抛异常。"""
    md = MarketData()

    def fake_execute(code, start, end, period, adjust, requested):
        return DataResult(
            data=None, source="tdx", ok=False, error="all failed", requested_source="auto",
            fallback_chain=[
                {"source": "hithink", "error_type": "ProviderUnavailable", "reason": "x"},
                {"source": "miniqmt", "error_type": "ProviderDataEmpty", "reason": "x"},
                {"source": "tdx", "error_type": "ProviderUnavailable", "reason": "x"},
            ])

    monkeypatch.setattr(router, "execute_history", fake_execute)
    r = md.history("600519.SH", "20260101", "20260110")["600519.SH"]
    assert r.ok is False
    assert r.error is not None
    assert len(r.fallback_chain) == 3
    # 不抛异常：到此即为证明（若抛，测试会在此前失败）


def test_financial_no_source_raises(monkeypatch):
    md = MarketData()

    def fake_fin(*a, **k):
        return None, "hithink", [{"source": "hithink", "error_type": "ProviderUnavailable", "reason": "x"}]

    monkeypatch.setattr(router, "execute_financial", fake_fin)
    with pytest.raises(MktDataError):
        md.financial("600519.SH", "income")


def test_indicators_no_source_raises(monkeypatch):
    md = MarketData()
    monkeypatch.setattr(router, "latest_fiscal_year", lambda code, requested="auto": 2025)

    def fake_ind(*a, **k):
        return None, "hithink", [{"source": "hithink", "error_type": "ProviderUnavailable", "reason": "x"}]

    monkeypatch.setattr(router, "execute_indicators", fake_ind)
    with pytest.raises(MktDataError):
        md.indicators("600519.SH")


def test_valuation_no_source_raises(monkeypatch):
    md = MarketData()

    def fake_val(*a, **k):
        return None, "hithink", [{"source": "hithink", "error_type": "ProviderUnavailable", "reason": "x"}]

    monkeypatch.setattr(router, "execute_valuation", fake_val)
    with pytest.raises(MktDataError):
        md.valuation("600519.SH")


def test_invalid_param_raises():
    md = MarketData()
    with pytest.raises(InvalidParameter):
        md.history("600519.SH", "20261301", "20260110")   # 非法日期
    with pytest.raises(InvalidParameter):
        md.history("600519.SH", "20260101", "20260201", period="13m")
    with pytest.raises(InvalidParameter):
        md.financial("600519.SH", period="foo")


def test_invalid_symbol_raises():
    md = MarketData()
    with pytest.raises(InvalidSymbol):
        md.history("700.HK", "20260101", "20260110")      # 港股必须 5 位
    with pytest.raises(InvalidSymbol):
        md.history("ABC", "20260101", "20260110")
