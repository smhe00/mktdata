# miniQMT 环境与连接（setup）

## 环境事实（本机已验证）

| 项 | 值 |
| --- | --- |
| miniQMT 终端 | 实盘端 `D:\国金证券QMT交易端`（进程 `XtMiniQmt` + `miniquote`）；模拟端 `D:\国金QMT交易端模拟` |
| 数据服务地址 | `127.0.0.1:58610`（由终端自动提供，无需手动启动） |
| xtquant 版本 | `xtquant_250516`（venv 内） |
| Python（带 xtquant） | `D:\gitee\miniQMT\.venv\Scripts\python.exe`（3.12） |
| 技能脚本 | `D:\gitee\miniqmt-skill\scripts\qmt.py` |
| 数据目录 | `D:\国金证券QMT交易端\userdata_mini\datadir` |

## 连接

`xtdata.connect()` 即自动连接本机数据服务；可在 `connect` 前设 `xtdata.enable_hello = False` 关闭欢迎横幅。连接失败时先确认终端进程存在、端口 `58610` 在监听（`netstat -ano | findstr 58610`）。

## 代码格式（关键）

- A 股：`600519.SH`、`000858.SZ`（6 位 + 交易所后缀）。
- **港股：必须 5 位补零**，如腾讯 `00700.HK`（`0700.HK`、`700.HK` 均无效）。
- 无法确认时用 `qmt.py instrument --code <代码>` 验证；返回空即代码格式不对。

## 常用 API（本版本签名）

```
connect(ip='', port=None)
get_instrument_detail(stock_code, iscomplete=False)
get_divid_factors(stock_code, start_time='', end_time='')
get_trading_dates(market, start_time='', end_time='', count=-1)   # market: SH/SZ/HK
get_trading_calendar(market, start_time='', end_time='')
get_full_tick(code_list)                                           # 最新快照 dict
get_stock_list_in_sector(sector_name, real_timetag=-1)
download_history_data(stock_code, period, start_time, end_time, incrementally=None)
get_market_data_ex(field_list=[], stock_list=[], period='1d', start_time='', end_time='',
                   count=-1, dividend_type='none', fill_data=True)
```

## 时间戳口径（易错）

- `get_market_data_ex` 返回 DataFrame 的**索引是 `YYYYMMDD` 整数**（如 `20260824`），不是毫秒。
- `get_full_tick` 的 `time`、`get_trading_dates` 返回值是**毫秒**（北京时间 UTC+8）。
- 传给 API 的时间参数一律用 `YYYYMMDD` 字符串。

## 复权

- `dividend_type='none'`：真实成交价；`'front'`：前复权；`'back'`：后复权。
- 后复权已含**现金分红 + 拆股送转**（如腾讯 2020 年 1:5 拆股），适合算总回报 CAGR。
- **回购注销没有复权因子**，任何复权都不含回购；不要把回购收益率硬加进历史价格回报（详见 SKILL.md）。

## 边界

- 只读取数，无下单/交易接口。
- 港股/ETF 是否可取取决于账户授权；`get_authorized_market_list()` 在本版本客户端不支持（返回 ErrorID 300000）。
- 分钟级 `5m/1m` 可用但窗口/数据量受限，日线最稳。
- 跨市场（A 股人民币 + 港股港币）组合需注明未做汇率折算。
