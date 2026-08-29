"""P0 contract tests（P0-8 + 二/三轮）：canonical schema / missing value / error propagation / requested_source / pb_ok / fiscal year / HK ERR / HK target statement / indicators forced source。"""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata import api, models, normalize, router
from mktdata.errors import (
    MktDataError,
    ProviderAuthError,
    ProviderDataEmpty,
    ProviderRateLimited,
    ProviderUnavailable,
    ProviderUnsupported,
)


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
    assert row["source"] == "miniqmt"  # R9：链首 miniQMT 优先
    assert res.requested_source == "auto"


def test_normalize_history_rows_missing_value():
    """P0-1：缺失值保留 None，禁止 0 顶替。"""
    out = normalize.normalize_history_rows(
        [{"date": "2026-01-02", "open": None, "close": 5.0}], "600519.SH", "miniqmt", "1d")
    assert out[0]["open"] is None
    assert out[0]["close"] == 5.0
    assert out[0]["source"] == "miniqmt"


def test_error_propagation_error_type(monkeypatch):
    """P0-3：provider 抛结构化异常 → router 记录 error_type（R9 miniQMT-first 顺序）。"""
    def fake_call(src, code, start, end, period, adjust):
        if src == "miniqmt":
            raise ProviderUnavailable("miniQMT timeout")
        if src == "hithink":
            raise ProviderDataEmpty("hithink 空")
        return [{"date": "2026-01-02", "close": 1.0}]
    monkeypatch.setattr(router, "_call_history", fake_call)
    res = router.execute_history("600519.SH", "20260101", "20260110")
    assert res.source == "tdx"
    assert res.fallback_chain[0]["source"] == "miniqmt"
    assert res.fallback_chain[0]["error_type"] == "ProviderUnavailable"
    assert res.fallback_chain[1]["source"] == "hithink"
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


# ---- 第二轮（P0 收尾）----

def test_missing_amount_not_zero(monkeypatch):
    """9.1：Yahoo/新浪美股 amount 不可得 → None，不是 0.0。"""
    def fake_call(src, code, start, end, period, adjust):
        return [{"date": "2026-01-02", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 100.0, "amount": None}]
    monkeypatch.setattr(router, "_call_history", fake_call)
    res = router.execute_history("AAPL.US", "20260101", "20260110")
    assert res.data[0]["amount"] is None
    # 再直接验证 normalize 透传 None（不进 normalize 的也不得被转 0）
    out = normalize.normalize_history_rows(
        [{"date": "2026-01-02", "amount": None}], "AAPL.US", "yahoo", "1d")
    assert out[0]["amount"] is None


def test_extract_fiscal_year():
    """9.2：FY 解析统一（hithink FY2025 / miniQMT 20251231 / 2025-4 / 2025）。"""
    assert normalize.extract_fiscal_year("FY2025") == 2025
    assert normalize.extract_fiscal_year("20251231") == 2025
    assert normalize.extract_fiscal_year("2025-4") == 2025
    assert normalize.extract_fiscal_year("2025") == 2025
    assert normalize.extract_fiscal_year(None) is None
    assert normalize.extract_fiscal_year("abc") is None


def test_indicators_fallback_in_router(monkeypatch):
    """9.3：indicators fallback（R9 miniQMT 优先；miniQMT 失败 → hithink）由 router 承担，CLI 不自己 fallback。"""
    def fake_call(src, code, report):
        if src == "miniqmt":
            raise ProviderUnavailable("miniQMT 挂")
        return {"period": "FY2025", "roe": 20.0}
    monkeypatch.setattr(router, "_call_indicators", fake_call)
    row, src, fb = router.execute_indicators("600519.SH", "2025-4")
    assert src == "hithink"
    assert row["roe"] == 20.0
    assert fb[0]["source"] == "miniqmt"
    # MarketData.indicators 走同一 router
    md = api.MarketData()
    monkeypatch.setattr(router, "latest_fiscal_year", lambda code, requested="auto": 2025)
    r = md.indicators("600519.SH")
    assert r.source == "hithink"
    assert r.data["period"] == "FY2025"


@pytest.mark.parametrize("exc_cls", [
    ProviderUnsupported, ProviderUnavailable, ProviderAuthError,
    ProviderDataEmpty, ProviderRateLimited,
])
def test_router_preserves_error_type(monkeypatch, exc_cls):
    """9.4：5 类结构化异常经 router → fallback_chain.error_type 保留类型。"""
    def fake_call(src, code, start, end, period, adjust):
        raise exc_cls(f"{src} 失败")
    monkeypatch.setattr(router, "_call_history", fake_call)
    res = router.execute_history("600519.SH", "20260101", "20260110")
    assert res.fallback_chain[0]["error_type"] == exc_cls.__name__


def test_hk_financial_err_not_success(monkeypatch):
    """9.5：港股 F10 内部 ERR 字符串不能当作成功。"""
    monkeypatch.setattr(api.P, "ak_f10", lambda code, limit: {"code": code, "三大报表": "ERR boom"})
    with pytest.raises(ProviderUnavailable):
        router._call_financial("akshare", "00700.HK", "income", "annual", 4)
    monkeypatch.setattr(api.P, "ak_f10", lambda code, limit: {"code": code})
    with pytest.raises(ProviderDataEmpty):
        router._call_financial("akshare", "00700.HK", "income", "annual", 4)


# ---- 第三轮（P0 最终收口）----

def _load_cli():
    import mktdata.cli as cli  # R1：CLI 逻辑已移入包内模块
    return cli


def test_hk_financial_cli_uses_marketdata(monkeypatch):
    """8.1：港股 financial CLI 核心路径走 MarketData.financial，不再直接 ak_f10。"""
    cli = _load_cli()
    calls = []

    class FakeRes:
        source = "akshare"
        data = {"指标估值": {"PE": 15.0}, "三大报表": {"利润表(2025)": {"营业额": 100}}}
        fallback_chain = None

    def fake_financial(self, code, statement, period="annual", limit=4, source="auto"):
        calls.append((code, statement))
        return FakeRes()

    monkeypatch.setattr(api.MarketData, "financial", fake_financial)
    args = types.SimpleNamespace(codes="00700.HK", statement="income", period="annual",
                                 limit=2, source="auto", json=None, report=None)
    cli.cmd_financial(args)
    assert calls == [("00700.HK", "income")]


def test_hk_target_statement_validation(monkeypatch):
    """8.2：港股按请求的目标 statement 验证对应报表存在。"""
    def mk(stmts):
        return {"code": "00700.HK", "三大报表": stmts}
    # Case 1: income 存在 → 不抛
    monkeypatch.setattr(api.P, "ak_f10", lambda code, limit: mk({"利润表(2025)": {"营业额": 100}}))
    out = router._call_financial("akshare", "00700.HK", "income", "annual", 4)
    assert out["三大报表"]["利润表(2025)"]["营业额"] == 100
    # Case 2: income 不存在（只有资产负债表）→ ProviderDataEmpty
    monkeypatch.setattr(api.P, "ak_f10", lambda code, limit: mk({"资产负债表(2025)": {"总资产": 1}}))
    with pytest.raises(ProviderDataEmpty):
        router._call_financial("akshare", "00700.HK", "income", "annual", 4)
    # Case 3: 三大报表 = "ERR boom" → ProviderUnavailable
    monkeypatch.setattr(api.P, "ak_f10", lambda code, limit: {"code": "00700.HK", "三大报表": "ERR boom"})
    with pytest.raises(ProviderUnavailable):
        router._call_financial("akshare", "00700.HK", "income", "annual", 4)


def test_indicators_forced_source_fy_phase(monkeypatch):
    """8.3：indicators 强制源在自动确定 FY 阶段也严格生效。"""
    calls = {"hh_fin": 0, "mq_fin": 0}

    def fake_hh_fin(code, statement, period, limit):
        calls["hh_fin"] += 1
        return [{"period": "FY2025", "revenue": 1}]

    def fake_mq_fin(code, statement, period, limit):
        calls["mq_fin"] += 1
        return [{"period": "20251231", "revenue": 1}]

    monkeypatch.setattr(router.P, "hithink_financial", fake_hh_fin)
    monkeypatch.setattr(router.P, "miniqmt_financial", fake_mq_fin)
    md = api.MarketData()

    # Case 1: source=miniqmt → FY 阶段只碰 miniQMT
    def fake_call_miniqmt(src, code, report):
        assert src == "miniqmt"
        return {"period": "FY2025", "roe": 20.0}
    monkeypatch.setattr(router, "_call_indicators", fake_call_miniqmt)
    calls["hh_fin"] = 0; calls["mq_fin"] = 0
    r = md.indicators("600519.SH", report=None, source="miniqmt")
    assert calls["hh_fin"] == 0
    assert calls["mq_fin"] == 1
    assert r.source == "miniqmt"

    # Case 2: source=hithink → FY 阶段不碰 miniQMT
    def fake_call_hithink(src, code, report):
        assert src == "hithink"
        return {"period": "FY2025", "roe": 20.0}
    monkeypatch.setattr(router, "_call_indicators", fake_call_hithink)
    calls["hh_fin"] = 0; calls["mq_fin"] = 0
    r2 = md.indicators("600519.SH", report=None, source="hithink")
    assert calls["mq_fin"] == 0
    assert calls["hh_fin"] == 1
    assert r2.source == "hithink"

    # Case 3: source=auto → miniQMT 优先；miniQMT 失败 → hithink（R9）
    def fake_mq_fail(code, statement, period, limit):
        calls["mq_fin"] += 1
        raise ProviderUnavailable("miniQMT 挂")
    monkeypatch.setattr(router.P, "miniqmt_financial", fake_mq_fail)

    def fake_call_auto(src, code, report):
        if src == "miniqmt":
            raise ProviderUnavailable("miniQMT 挂")
        return {"period": "FY2025", "roe": 20.0}
    monkeypatch.setattr(router, "_call_indicators", fake_call_auto)
    calls["hh_fin"] = 0; calls["mq_fin"] = 0
    r3 = md.indicators("600519.SH", report=None, source="auto")
    assert calls["mq_fin"] >= 1 and calls["hh_fin"] >= 1  # FY 阶段 miniQMT 失败 → hithink
    assert r3.source == "hithink"
