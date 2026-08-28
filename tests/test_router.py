"""router 纯单元测试（免网络：用 monkeypatch mock provider 调用；provider 失败→抛 MktDataError）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata import router
from mktdata.errors import ProviderUnavailable


def test_resolve_history_chains():
    assert router.resolve_history("CN", "1d") == ["hithink", "miniqmt", "tdx"]
    assert router.resolve_history("CN", "5m") == ["miniqmt", "tdx"]
    assert router.resolve_history("CN", "1m") == ["miniqmt", "tdx"]
    assert router.resolve_history("HK", "1d") == ["miniqmt", "sina"]
    assert router.resolve_history("US", "1d") == ["yahoo", "sina"]


def test_resolve_financial_valuation():
    assert router.resolve_financial("CN") == ["hithink", "miniqmt"]
    assert router.resolve_financial("HK") == ["akshare"]
    assert router.resolve_valuation("CN") == ["hithink", "miniqmt", "tdx"]
    assert router.resolve_valuation("HK") == ["akshare"]


def test_resolve_forced_single_source():
    assert router.resolve_history("CN", "1d", requested="tdx") == ["tdx"]
    assert router.resolve_valuation("HK", requested="akshare") == ["akshare"]
    assert router.resolve_history("US", "1d", requested="yahoo") == ["yahoo"]


def test_execute_history_fallback(monkeypatch):
    calls = []

    def fake_call(src, code, start, end, period, adjust):
        calls.append(src)
        if src == "hithink":
            raise ProviderUnavailable("hithink 失败")
        if src == "miniqmt":
            return [{"date": "2026-01-02", "close": 1.0}]
        raise ProviderUnavailable("?")

    monkeypatch.setattr(router, "_call_history", fake_call)
    res = router.execute_history("600519.SH", "20260101", "20260110")
    assert res.ok is True
    assert res.source == "miniqmt"
    assert calls == ["hithink", "miniqmt"]
    assert res.fallback_chain[0]["source"] == "hithink"
    assert res.fallback_chain[0]["error_type"] == "ProviderUnavailable"
    assert res.data[0]["symbol"] == "600519.SH"  # canonical（P0-1）
    assert res.data[0]["source"] == "miniqmt"


def test_execute_history_all_fail(monkeypatch):
    def fake_call(src, code, start, end, period, adjust):
        raise ProviderUnavailable(f"{src} 全挂")

    monkeypatch.setattr(router, "_call_history", fake_call)
    res = router.execute_history("600519.SH", "20260101", "20260110")
    assert res.ok is False
    assert res.data is None
    assert len(res.fallback_chain) == 3  # hithink, miniqmt, tdx
    assert res.fallback_chain[-1]["source"] == "tdx"
    assert all(e["error_type"] == "ProviderUnavailable" for e in res.fallback_chain)


def test_execute_valuation_fallback(monkeypatch):
    calls = []

    def fake_call(src, code):
        calls.append(src)
        if src == "hithink":
            raise ProviderUnavailable("hithink 失败")
        if src == "miniqmt":
            return {"pe_ttm": 20.0, "pb_mrq": 6.0}
        raise ProviderUnavailable("?")

    monkeypatch.setattr(router, "_call_valuation", fake_call)
    row, src, fb = router.execute_valuation("600519.SH")
    assert src == "miniqmt"
    assert row["pe_ttm"] == 20.0
    assert fb[0]["source"] == "hithink"
