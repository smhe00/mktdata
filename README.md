# mktdata

一个统一读取 **A股 / 港股 / 美股** 市场数据的 Python 库：行情、财报、估值、指标、交易日历、证券资料、分红送转、板块成分。

默认会根据市场自动选择数据源，并在主数据源不可用时自动切换（fallback）。**通常你不需要关心数据源是谁。**

---

## 能做什么

| 你要的数据 | 可用 |
|---|---|
| 历史行情（日线 / 分钟 1m·5m·15m·30m·60m） | ✅ |
| 财务报表（利润表 / 资产负债表 / 现金流量表） | ✅ |
| 估值（PE / PB / PS / PCF） | ✅ |
| 财务指标（成长 / 盈利 / 偿债） | ✅ |
| 交易日历 | ✅ |
| 证券资料 | ✅ |
| 分红送转 | ✅ |
| 板块成分 | ✅ |

---

## 安装

按你的情况选一种：

**① 大多数人（推荐）——公开数据源全要**

```bash
python -m pip install "mktdata[public]"
```

可用新浪(AkShare)、通达信(TDX) 等公开数据源。本地安装：

```bash
git clone <本仓库地址>
cd mktdata
python -m pip install ".[public]"
```

**② 最小安装——只想先试试**

```bash
python -m pip install .
```

只装核心库。基本可直接用 **Yahoo 美股行情**；A股行情和 hithink 还需要额外配置（见下）。

**③ 想用本机 miniQMT**

装好 mktdata 后，还必须：
1. 启动 miniQMT 终端；
2. 保证当前 Python 能 `import xtquant`（用 miniQMT 自带的 Python 环境即可）。

**④ 开发者**

```bash
python -m pip install -e ".[dev]"
```

---

## 30 秒上手

不需要配置任何东西，直接跑：

```python
from mktdata import MarketData

md = MarketData()
r = md.history("AAPL.US", "20260101", "20260110")["AAPL.US"]

print("数据来自:", r.source)   # 实际命中的数据源
print(r.data[:3])              # 前 3 根 K 线
```

说明：
- 默认 `source="auto"`，**通常不需要手工指定数据源**。
- 美股日线会自动优先用 Yahoo；Yahoo 不可用时切新浪。
- `md.history(...)` 返回 `{"代码": DataResult}`——即使只查一个代码也是这个结构。

---

## 证券代码格式

| 市场 | 例子 |
|---|---|
| 沪市 | `600519.SH` |
| 深市 | `000858.SZ` |
| 北交所 | `xxxxxx.BJ` |
| 港股 | `00700.HK` |
| 美股 | `AAPL.US` |

港股必须 5 位：`00700.HK` ✅；`0700.HK` / `700.HK` ❌（会报 `InvalidSymbol`）。

---

## 常见任务

**获取 A 股行情**

```python
r = md.history("600519.SH", "20260101", "20260828")["600519.SH"]
```

**获取腾讯港股行情**

```python
r = md.history("00700.HK", "20260101", "20260828")["00700.HK"]
```

**获取美股行情**

```python
r = md.history("AAPL.US", "20260101", "20260828")["AAPL.US"]
```

**获取财报**

```python
r = md.financial("600519.SH", statement="income", period="annual", limit=4)
```

**获取估值**

```python
r = md.valuation("600519.SH")
```

**更多 API**（详见代码 docstring / `references/`）：

```python
md.indicators("600519.SH")          # 财务指标
md.calendar(market="SH", ...)       # 交易日历
md.instrument("600519.SH")          # 证券资料
md.corporate_actions("600519.SH")   # 分红送转
md.sector("沪深300")                 # 板块成分
md.crosscheck(["600519.SH"], ...)   # 多源对账（调试用）
```

---

## 我需要配置哪个数据源？

按"我要什么数据"来看：

| 我想获取 | 最简单配置 | auto 时的数据源 |
|---|---|---|
| 美股日线 | 最小安装即可 | Yahoo → Sina |
| 港股日线 | `.[public]` | miniQMT → Sina |
| A股日线 | `.[public]`（可先用 TDX） | hithink → miniQMT → TDX |
| 港股财务 / 估值 | `.[public]` | AkShare/Eastmoney |
| A股财务 / 估值 | hithink 或 miniQMT | hithink → miniQMT |
| 日历 / 证券资料 / 分红 / 板块 | miniQMT | miniQMT |

**hithink**（同花顺，A股行情/财务/估值的主要源）需要 API Key：

在 `%APPDATA%\hithink-finance\credentials.env` 写入：

```
HITHINK_FINANCE_API_KEY=你的key
```

**miniQMT** 详见 `references/setup.md`（需终端运行 + 可 import xtquant）。

---

## 返回结果与错误处理

`DataResult` 最常见就三个字段：

```python
if r.ok:
    print(r.data)            # 数据本体
    print("数据来自:", r.source)
else:
    print("获取失败:", r.error)
```

**不同接口失败时的行为不一样**，请按真实行为处理：

| 情况 | 行为 |
|---|---|
| `history()` 全部数据源不可用 | **返回 `ok=False`**（不抛异常），`error` 里有原因 |
| `financial()` / `indicators()` / `valuation()` 无可用源 | **抛 `MktDataError`** |
| 参数非法（日期 / period / source / statement…） | 抛 `InvalidParameter` |
| 证券代码非法 | 抛 `InvalidSymbol` |

异常类都在 `mktdata.errors`：

| Error | 含义 |
|---|---|
| `InvalidParameter` | 参数非法 |
| `InvalidSymbol` | 证券代码非法 |
| `ProviderUnavailable` | 依赖 / 网络 / 终端不可用 |
| `ProviderUnsupported` | 该数据源不支持此市场 / 周期 |
| `ProviderDataEmpty` | 数据源正常但无数据 |
| `ProviderAuthError` | key 缺失 / 失效 |
| `ProviderRateLimited` | 数据源限流 |

> 想深挖"到底试了哪些源、为什么失败"？见下面的「高级用法」里的 `fallback_chain`。

---

## 自动 fallback

`source="auto"`（默认）时的切换顺序：

| 请求 | auto 顺序 |
|---|---|
| A股日线 | hithink → miniQMT → TDX |
| A股分钟 | miniQMT → TDX |
| 港股日线 | miniQMT → Sina |
| 美股日线 | Yahoo → Sina |
| A股财务 | hithink → miniQMT |
| 港股财务 | AkShare/Eastmoney |
| A股估值 | hithink → miniQMT → TDX |
| 港股估值 | AkShare/Eastmoney |

---

## 常见问题

**A 股为什么取不到数据？**

auto 会依次尝试 hithink → miniQMT → TDX。三者都不可用时 `history()` 返回 `ok=False`（不会崩）。检查：hithink key 是否配置、miniQMT 是否运行、是否装了 `.[public]`。

**miniQMT 为什么不工作？**

必须①启动 miniQMT 终端、②当前 Python 能 `import xtquant`（用 miniQMT 自带环境）。

**腾讯为什么报 InvalidSymbol？**

用 `00700.HK`，不是 `700.HK` / `0700.HK`。

**港股财报为什么和 A 股字段不一样？**

港股财务当前来自 AkShare/Eastmoney F10，入口是统一的，但**返回字段尚未与 A 股完全统一**——别把"统一 API"误解成"所有市场返回字段完全一致"。

---

## CLI

```bash
mktdata history --codes 600519.SH,00700.HK,AAPL.US --start 20260814 --end 20260821 --adjust none
mktdata financial --codes 600519.SH --statement all
mktdata valuation --codes 600519.SH,00700.HK
mktdata crosscheck --codes 600519.SH --start 20260818 --end 20260824
mktdata f10 --codes 00700.HK
mktdata extra --type all
```

`mktdata --help` 可看所有参数。

---

## 数据契约

`history()` 每行 K 线的统一字段：

```
symbol, datetime, open, high, low, close, volume, amount, source
```

- `datetime`：日线 `YYYY-MM-DD`；分钟 `YYYY-MM-DD HH:MM`
- `volume`：单位 = 股（shares）
- `amount`：成交额（本市场货币）；数据源不提供时为 `None`（不伪造 0）
- 缺失值：`None` / `NaN`
- `adjust`：`none`（原始价）/ `front`（前复权）/ `back`（后复权）
- 周期：`1d / 1m / 5m / 15m / 30m / 60m`

---

## 高级用法

**强制指定数据源**

```python
r = md.history("600519.SH", "20260101", "20260828", source="miniqmt")["600519.SH"]
```

指定后不再 fallback；在自动确定报告期等阶段同样严格生效。

**查看 fallback 链 / 来源追溯**

```python
r = md.history("600519.SH", "20260101", "20260110")["600519.SH"]
print(r.provenance())
# {'source': 'miniqmt', 'requested_source': 'auto',
#  'fallback_chain': [{'source': 'hithink', 'error_type': 'ProviderUnavailable', 'reason': '...'}]}
```

**查询某数据源支持什么**

```python
from mktdata import supports
supports("hithink", "history", market="CN", period="1d")  # True
supports("sina", "history", market="HK")                  # True
supports("tdx", "history", market="HK")                   # False
```

---

## 开发与测试

```bash
python -m pytest -q          # 离线单测（无需网络 / 终端 / key）
python scripts/test_all.py   # 真实集成回归（需 miniQMT + hithink key + 网络）
```

架构：

```text
CLI (mktdata/cli.py, console script: mktdata)
  ↓
MarketData (mktdata/api.py)   —— 统一 Python API + 参数校验
  ↓
Router (mktdata/router.py)    —— 数据源切换 / fallback / 错误归类
  ↓
Providers (mktdata/providers/) —— hithink / miniQMT / tdx / yahoo / akshare
```

GitHub Actions（`.github/workflows/test.yml`）在 Python 3.10 / 3.12 上跑离线单测 + `mktdata --help` smoke。

## License

MIT
