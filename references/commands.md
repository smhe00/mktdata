# miniQMT 命令参考（commands）

统一运行方式：

```powershell
& '<venv-python>' '<repo>\scripts\qmt.py' <子命令> ...
```

若中文在 PowerShell 控制台显示乱码，属控制台编码（GBK）显示问题，数据本身正确；落盘的 CSV/JSON 均为 UTF-8。可在脚本内已加 `enable_hello=False` 关闭欢迎横幅。

## connect

自检连接并显示数据目录。

```powershell
... qmt.py connect
# OK 已连接本机 miniQMT 数据服务
#    数据目录: <qmt-real-terminal>\userdata_mini\datadir
```

## history — 历史 K 线

```
--code <代码>  --period <1d|5m|1m>  --start <YYYYMMDD>  --end <YYYYMMDD>
--adjust <none|front|back>  默认 none
--tail <N>   打印末尾 N 行（默认 5；0 不打印明细）
--csv <路径> / --json <路径>  落盘可选
```

示例（腾讯近 1 月后复权日线）：

```powershell
... qmt.py history --code 00700.HK --period 1d --start 20260720 --end 20260824 --adjust back --tail 3
# 00700.HK 1d adjust=back  共 26 根  [2026-07-20 .. 2026-08-24]
#   首: 开2449.03 收2510.03   末: 开2371.03 收2321.03
#   2026-08-20  O2394.03 H2408.03 L2365.03 C2378.03 ...
#   2026-08-24  O2371.03 H2378.03 L2313.03 C2321.03 ...
```

导出示例：

```powershell
... qmt.py history --code 600519.SH --period 1d --start 20260801 --end 20260824 --adjust back --csv out.csv
```

CSV 列：`date,open,high,low,close,volume,amount`（后复权时 close 为复权价）。

## quote — 最新快照

```
--code <代码> [<代码> ...]  可多只
```

```powershell
... qmt.py quote --code 00700.HK 600519.SH
# 00700.HK  last=440  prev=457  open=450  high=451.4  low=438.4  volume=29180102  amount=12881851900  time=2026-08-24
```

## dividends — 分红/送转/除权因子

```
--code <代码>  --start <YYYYMMDD>  --end <YYYYMMDD>
```

```powershell
... qmt.py dividends --code 00700.HK --start 20240101 --end 20260824
# 00700.HK 分红/送转/除权记录 3 条:
#   2024-05-17  每股现金=3.4 送股=0.0 转增=0.0 配股=0.0 复权因子dr=1.008638
```

字段：`interest`=每股现金分红、`stockBonus`=送股、`stockGift`=转增、`allotNum/allotPrice`=配股、`dr`=除权除息复权因子。

## instrument — 证券基础资料

```
--code <代码>
```

```powershell
... qmt.py instrument --code 00700.HK
# InstrumentID = 00700
# ExchangeID   = HK
# InstrumentName = 腾讯控股
# OpenDate     = 20040616
# PreClose     = 457.0
```

找不到时返回提示并退出码 1——多半是代码格式不对（港股记得 5 位补零）。

## calendar — 交易日历

```
--market <SH|SZ|HK>  --start <YYYYMMDD>  --end <YYYYMMDD>
```

```powershell
... qmt.py calendar --market HK --start 20260817 --end 20260824
# HK 交易日 6 天: 2026-08-17, 2026-08-18, ..., 2026-08-24
```

## sector — 板块成分

```
--name <板块名>
```

```powershell
... qmt.py sector --name 上证50
# 板块 '上证50' 成分 50 个: ...
```

## 组合计算注意事项（配合本 skill 取数时）

- 港股日线索引为 `YYYYMMDD`，A 股来源（如 hithink）时间戳可能为毫秒且时区不同（hithink 用北京时间 0 点 = 16:00 UTC）。**跨源合并前统一归一化为"北京时间当天"**，否则按毫秒精确匹配会零重合。
- 复权口径要统一：总回报都用后复权（`--adjust back`）。
