"""api（MarketData）纯单元测试（mock router；免网络）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata import MarketData
from mktdata import router
from mktdata.api import _as_list
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
