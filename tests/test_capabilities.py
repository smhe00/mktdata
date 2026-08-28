"""capabilities 纯单元测试（P1L-4/P1L-5，offline）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mktdata import PROVIDER_CAPABILITIES, supports


def test_required_cases():
    assert supports("hithink", "history", market="CN", period="1d") is True
    assert supports("hithink", "history", market="US", period="1d") is False
    assert supports("tdx", "history", market="CN", period="5m") is True
    assert supports("tdx", "history", market="HK", period="1d") is False
    assert supports("yahoo", "history", market="US", period="1d") is True
    assert supports("miniqmt", "calendar", market="CN") is True


def test_unknown_returns_false():
    assert supports("qlib", "history") is False
    assert supports("hithink", "backtest") is False
    assert supports("hithink", "history", market="HK") is False
    assert supports("yahoo", "financial", market="US") is False


def test_capabilities_static_dict():
    # 至少覆盖 8 个能力键
    all_caps = {c for prov in PROVIDER_CAPABILITIES.values() for c in prov}
    assert {"history", "financial", "indicators", "valuation",
            "calendar", "instrument", "corporate_actions", "sector"} <= all_caps
