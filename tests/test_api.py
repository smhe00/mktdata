"""api（MarketData）纯单元测试（mock router；免网络）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata import MarketData
from mktdata import api, router
from mktdata.api import _as_list
from mktdata.errors import InvalidParameter
from mktdata.models import DataResult


def test_as_list():
    assert _as_list("600519.SH") == ["600519.SH"]
    assert _as_list(["a", "b"]) == ["a", "b"]


def test_history_returns_dict(monkeypatch):
    md = MarketData()

    def fake_execute(code, start, end, period, adjust, requested):
        return DataResult(data=[{"date": "2026-01-02", "close": 1.0}], source="hithink", ok=True)

    monkeypatch.setattr(router, "execute_history", fake_execute)
    res = md.history(["600519.SH", "000858.SZ"], "20260101", "20260110")
    assert set(res.keys()) == {"600519.SH", "000858.SZ"}
    assert res["600519.SH"].source == "hithink"
    assert res["600519.SH"].data[0]["close"] == 1.0


def test_financial_ok_and_raises(monkeypatch):
    md = MarketData()
    ok = {"ok": True}

    def fake_ok(code, statement, period, limit, requested):
        return [{"period": "FY2025", "revenue": 1.0}], "hithink", None

    monkeypatch.setattr(router, "execute_financial", fake_ok)
    r = md.financial("600519.SH")
    assert r.ok is True
    assert r.source == "hithink"
    assert r.data[0]["period"] == "FY2025"

    def fake_fail(code, statement, period, limit, requested):
        return None, "hithink", [{"source": "hithink", "reason": "fail"}]

    monkeypatch.setattr(router, "execute_financial", fake_fail)
    with pytest.raises(Exception):
        md.financial("600519.SH")


def test_valuation_ok(monkeypatch):
    md = MarketData()

    def fake_execute(code, requested):
        return {"pe_ttm": 20.0, "pb_mrq": 6.0}, "miniqmt", None

    monkeypatch.setattr(router, "execute_valuation", fake_execute)
    r = md.valuation("600519.SH")
    assert r.data["pe_ttm"] == 20.0
    assert r.source == "miniqmt"


def test_api_validation_before_provider(monkeypatch):
    """P1L-5：非法输入在 provider 之前抛 InvalidParameter，provider 不被调用。"""
    md = MarketData()
    called = {"n": 0}

    def fake_execute(code, start, end, period, adjust, requested):
        called["n"] += 1
        return DataResult(data=[], source="hithink", ok=True)

    monkeypatch.setattr(router, "execute_history", fake_execute)
    with pytest.raises(InvalidParameter):
        md.history("600519.SH", "20260101", "20260201", period="13m")
    with pytest.raises(InvalidParameter):
        md.history("600519.SH", "20260201", "20260101")  # start > end
    with pytest.raises(InvalidParameter):
        md.history("600519.SH", "20260101", "20260201", source="foo")
    assert called["n"] == 0  # provider 从未被调用


def test_api_validation_extra(monkeypatch):
    """P1-lite 第一轮 B 组：calendar/sector/corporate_actions/financial period 非法输入统一 InvalidParameter，provider 不调用。"""
    md = MarketData()
    calls = {"n": 0}

    def fake(*a, **k):
        calls["n"] += 1
        return []

    monkeypatch.setattr(api.P, "miniqmt_calendar", fake)
    monkeypatch.setattr(api.P, "miniqmt_corporate_actions", fake)
    monkeypatch.setattr(api.P, "miniqmt_sector", fake)
    with pytest.raises(InvalidParameter):
        md.calendar(market="CN")                                  # B1
    with pytest.raises(InvalidParameter):
        md.calendar(market="SH", start="20260201", end="20260101")  # B3
    with pytest.raises(InvalidParameter):
        md.corporate_actions("600519.SH", start="20260201", end="20260101")  # B4
    with pytest.raises(InvalidParameter):
        md.sector("")                                             # B2
    assert calls["n"] == 0  # provider 均未被调用

    def fake_fin(*a, **k):
        calls["n"] += 1
        return [{"period": "FY2025"}], "hithink", None

    monkeypatch.setattr(router, "execute_financial", fake_fin)
    with pytest.raises(InvalidParameter):
        md.financial("600519.SH", period="foo")                   # B5
    assert calls["n"] == 0  # router.execute_financial 未被调用
