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
    # calendar 与 public API (SH/SZ/HK) 一致
    assert supports("miniqmt", "calendar", market="SH") is True
    assert supports("miniqmt", "calendar", market="SZ") is True
    assert supports("miniqmt", "calendar", market="HK") is True
    assert supports("miniqmt", "calendar", market="CN") is False


def test_sina_vs_akshare_history():
    """A1：sina 承担 HK/US history；akshare 不再承担 history。"""
    assert supports("sina", "history", market="HK", period="1d") is True
    assert supports("sina", "history", market="US", period="1d") is True
    assert supports("akshare", "history", market="HK", period="1d") is False
    # akshare 保留 HK financial/valuation
    assert supports("akshare", "financial", market="HK") is True
    assert supports("akshare", "valuation", market="HK") is True


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


def test_empty_metadata_capability():
    """第二轮 blocker：capability 存在但 metadata={} 必须为 True；不存在才 False。"""
    assert supports("miniqmt", "instrument") is True
    assert supports("miniqmt", "corporate_actions") is True
    assert supports("miniqmt", "sector") is True
    assert supports("miniqmt", "backtest") is False
    assert supports("unknown", "instrument") is False
    # 空 metadata 能力带 market 过滤不应误伤
    assert supports("miniqmt", "sector", market="CN") is True
