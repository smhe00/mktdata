"""models 纯单元测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata.models import Adjust, DataResult, Market, Period, SecurityType, Symbol


def test_enums():
    assert Adjust.NONE.value == "none"
    assert Adjust.BACK.value == "back"
    assert Market.HK.value == "HK"
    assert Period.DAY.value == "1d"
    assert Period.MIN_5.value == "5m"
    assert SecurityType.STOCK.value == "stock"


def test_symbol_frozen():
    s = Symbol(code="600519", exchange="SH", market="CN", canonical="600519.SH")
    assert s.canonical == "600519.SH"
    with pytest.raises(Exception):
        s.canonical = "x"  # frozen


def test_data_result_provenance():
    r = DataResult(data=[1], source="miniqmt", ok=True, fallback_chain=[{"source": "hithink", "reason": "timeout"}])
    p = r.provenance()
    assert p["source"] == "miniqmt"
    assert p["requested_source"] == "auto"
    assert p["fallback_chain"][0]["reason"] == "timeout"


def test_data_result_defaults():
    r = DataResult(data=None, source="tdx")
    assert r.ok is True
    assert r.error is None
    assert r.fallback_chain is None
