"""normalize 纯单元测试。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from mktdata.normalize import norm_date_ymd, norm_dt_ymd, norm_num, norm_date_ms, to_ms_utc


def test_norm_date_ymd():
    assert norm_date_ymd(20260824) == "2026-08-24"
    assert norm_date_ymd("20260824") == "2026-08-24"
    assert norm_date_ymd("2026-08-24") == "2026-08-24"


def test_norm_dt_ymd():
    assert norm_dt_ymd(20260820103500) == "2026-08-20 10:35"
    assert norm_dt_ymd(20260824) == "2026-08-24"


def test_norm_num():
    assert norm_num("12.5") == 12.5
    assert norm_num(3) == 3.0
    assert norm_num(float("nan")) is None
    assert norm_num("abc") is None
    assert norm_num(None) is None


def test_norm_date_ms():
    assert norm_date_ms(1735689600000) == "2025-01-01"  # 北京 2025-01-01 00:00


def test_to_ms_utc():
    assert to_ms_utc("20250101") == 1735689600000
