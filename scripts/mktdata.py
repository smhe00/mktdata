#!/usr/bin/env python
"""mktdata CLI 兼容包装（R1）。

真实实现见 mktdata/cli.py；console script: mktdata = mktdata.cli:main。
本文件仅保留：可直接运行 `python scripts/mktdata.py ...`（无需先 pip install）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mktdata.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
