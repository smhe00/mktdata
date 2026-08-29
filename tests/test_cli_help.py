"""CLI help miniQMT-first contract 测试（Release 收口）。"""
import contextlib
import io
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _help(args):
    import mktdata.cli as cli
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            cli.main(args)
        except SystemExit:
            pass
    return buf.getvalue()


def test_cli_main_help_miniqmt_first():
    text = _help(["--help"])
    assert "miniQMT" in text
    assert "hithink 优先" not in text
    assert "hithink" in text or "hithink" in text  # hithink 仍是一个 provider，但不作为"优先"表述


def test_cli_financial_help_no_hithink_first():
    text = _help(["financial", "--help"])
    assert "miniQMT" in text
    assert "hithink 优先" not in text


def test_cli_valuation_help_no_hithink_first():
    text = _help(["valuation", "--help"])
    assert "miniQMT" in text
    assert "hithink 优先" not in text
