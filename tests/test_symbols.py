"""symbols 纯单元测试（免网络、免终端）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata.symbols import detect_market, is_hk, is_us, normalize_symbol
from mktdata.errors import InvalidSymbol


@pytest.mark.parametrize("raw,code,exchange,market,canonical", [
    ("600519.SH", "600519", "SH", "CN", "600519.SH"),
    ("000858.SZ", "000858", "SZ", "CN", "000858.SZ"),
    ("430047.BJ", "430047", "BJ", "CN", "430047.BJ"),
    ("00700.HK", "00700", "HK", "HK", "00700.HK"),
    ("AAPL.US", "AAPL", "US", "US", "AAPL.US"),
    ("600519.sh", "600519", "SH", "CN", "600519.SH"),  # 大小写
    (" 600519.SH ", "600519", "SH", "CN", "600519.SH"),  # 空白
])
def test_normalize_symbol(raw, code, exchange, market, canonical):
    s = normalize_symbol(raw)
    assert s.code == code
    assert s.exchange == exchange
    assert s.market == market
    assert s.canonical == canonical


@pytest.mark.parametrize("bad", ["", "600519", "0700.HK", "SH", "12345.XX", "600519.HK", None])
def test_invalid_symbol(bad):
    with pytest.raises(InvalidSymbol):
        normalize_symbol(bad)


def test_detect_market():
    assert detect_market("600519.SH") == "CN"
    assert detect_market("00700.HK") == "HK"
    assert detect_market("AAPL.US") == "US"


def test_is_hk_us():
    assert is_hk("00700.HK") is True
    assert is_hk("600519.SH") is False
    assert is_us("AAPL.US") is True
    assert is_us("00700.HK") is False
