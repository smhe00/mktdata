"""P0 contract tests（P0-8）：canonical schema / missing value / error propagation / requested_source / pb_ok。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata import api, models, normalize, router
from mktdata.errors import ProviderDataEmpty, ProviderUnavailable


def test_history_canonical_schema(monkeypatch):
    """P0-1：MarketData.history 返回 canonical HISTORY_FIELDS。"""
    def fake_call(src, code, start, end, period, adjust):
        return [{"date": "2026-08-20", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100.0, "amount": 150.0}]
    monkeypatch.setattr(router, "_call_history", fake_call)
    res = router.execute_history("600519.SH", "20260801", "20260824")
    row = res.data[0]
    assert set(row.keys()) == set(models.HISTORY_FIELDS)
    assert row["symbol"] == "600519.SH"
    assert row["datetime"] == "2026-08-20"
    assert row["source"] == "hithink"
    assert res.requested_source == "auto"


def test_normalize_history_rows_missing_value():
    """P0-1：缺失值保留 None，禁止 0 顶替。"""
    out = normalize.normalize_history_rows(
        [{"date": "2026-01-02", "open": None, "close": 5.0}], "600519.SH", "miniqmt", "1d")
    assert out[0]["open"] is None
    assert out[0]["close"] == 5.0
    assert out[0]["source"] == "miniqmt"


def test_error_propagation_error_type(monkeypatch):
    """P0-3：provider 抛结构化异常 → router 记录 error_type。"""
    def fake_call(src, code, start, end, period, adjust):
        if src == "hithink":
            raise ProviderUnavailable("hithink timeout")
        if src == "miniqmt":
            raise ProviderDataEmpty("miniQMT 空")
        return [{"date": "2026-01-02", "close": 1.0}]
    monkeypatch.setattr(router, "_call_history", fake_call)
    res = router.execute_history("600519.SH", "20260101", "20260110")
    assert res.source == "tdx"
    assert res.fallback_chain[0]["error_type"] == "ProviderUnavailable"
    assert res.fallback_chain[1]["error_type"] == "ProviderDataEmpty"


def test_requested_source_provenance(monkeypatch):
    """P0-7：requested_source 不再硬编码 auto。"""
    def fake_call(src, code, start, end, period, adjust):
        return [{"date": "2026-01-02", "close": 1.0}]
    monkeypatch.setattr(router, "_call_history", fake_call)
    res = router.execute_history("600519.SH", "20260101", "20260110", requested="tdx")
    assert res.requested_source == "tdx"
    assert res.provenance()["requested_source"] == "tdx"


def test_crosscheck_pb_ok(monkeypatch):
    """P0-6：crosscheck 恢复 pb_ok（5% 相对容差）。"""
    md = api.MarketData()

    def fake_hist(*args, **kw):
        return [{"date": "2026-08-20", "close": 1.0}]

    monkeypatch.setattr(api.P, "hithink_history", fake_hist)
    monkeypatch.setattr(api.P, "miniqmt_history", fake_hist)
    monkeypatch.setattr(api.P, "tdx_history", fake_hist)
    # PB：hh=6.0, mq=6.0, tdx=6.0 → pb_ok=True；再试 tdx=7.0（>5%）→ False
    monkeypatch.setattr(api.P, "hithink_valuation", lambda codes: {codes[0]: {"pb_mrq": 6.0}})
    monkeypatch.setattr(api.P, "miniqmt_valuation", lambda code: {"pb_mrq": 6.0})
    monkeypatch.setattr(api.P, "tdx_valuation", lambda code, **kw: {"pb_mrq": 6.0})
    r = md.crosscheck(["600519.SH"], "20260801", "20260824")["600519.SH"]
    assert r["close_ok"] is True
    assert r["pb_ok"] is True

    monkeypatch.setattr(api.P, "tdx_valuation", lambda code, **kw: {"pb_mrq": 7.0})
    r2 = md.crosscheck(["600519.SH"], "20260801", "20260824")["600519.SH"]
    assert r2["pb_ok"] is False
