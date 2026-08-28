"""validation 纯单元测试（P1L-5，offline）。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata import validation
from mktdata.errors import InvalidParameter


def test_validate_date_ok():
    assert validation.validate_date("20260101") == "20260101"
    assert validation.validate_date("2026-01-01") == "20260101"
    assert validation.validate_date("20260824") == "20260824"


def test_validate_date_bad():
    for bad in ("20261301", "20260230", "abc", "2026/01/01", "2026-13-01", "", None, 20260101):
        with pytest.raises(InvalidParameter):
            validation.validate_date(bad)


def test_validate_date_range():
    assert validation.validate_date_range("20260101", "20260201") == ("20260101", "20260201")
    assert validation.validate_date_range("2026-01-01", "20260201") == ("20260101", "20260201")
    with pytest.raises(InvalidParameter):
        validation.validate_date_range("20260201", "20260101")


def test_validate_period():
    for ok in ("1d", "1m", "5m", "15m", "30m", "60m"):
        assert validation.validate_period(ok) == ok
    for bad in ("13m", "2d", "daily", "foo", None):
        with pytest.raises(InvalidParameter):
            validation.validate_period(bad)


def test_validate_adjust():
    for ok in ("none", "front", "back"):
        assert validation.validate_adjust(ok) == ok
    for bad in ("qfq", "hfq", "forward", "backward", "foo", None):
        with pytest.raises(InvalidParameter):
            validation.validate_adjust(bad)


def test_validate_source_history():
    for ok in ("auto", "hithink", "miniqmt", "tdx", "sina", "yahoo"):
        assert validation.validate_source("history", ok) == ok
    for bad in ("foo", "qlib", "eastmoney-direct", None):
        with pytest.raises(InvalidParameter):
            validation.validate_source("history", bad)


def test_validate_source_other_capabilities():
    # 各能力各测一个非法 source
    for cap, bad in (("financial", "tdx"), ("valuation", "sina"), ("indicators", "akshare")):
        with pytest.raises(InvalidParameter):
            validation.validate_source(cap, bad)
    for cap, ok in (("financial", "akshare"), ("valuation", "akshare")):
        assert validation.validate_source(cap, ok) == ok


def test_validate_statement():
    for ok in ("income", "balance", "cashflow"):
        assert validation.validate_statement(ok) == ok
    for bad in ("profit", "assets", "foo", None):
        with pytest.raises(InvalidParameter):
            validation.validate_statement(bad)


def test_validate_financial_period():
    for ok in ("annual", "quarterly"):
        assert validation.validate_financial_period(ok) == ok
    for bad in ("foo", "1d", "yearly", None):
        with pytest.raises(InvalidParameter):
            validation.validate_financial_period(bad)
