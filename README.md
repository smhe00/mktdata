# mktdata — 多市场、多数据源、自动 fallback 的只读 Market Data Library + CLI

> `mktdata` 是一个**多市场、多数据源、支持自动 fallback、统一数据语义和 provenance 的只读 Market Data Library + CLI**。
> **Library API 是主入口，CLI 是薄壳。**
>
> 不含：Qlib、因子框架、回测、策略、交易、缓存/数据库平台。

---

## 1. What it is

一个 Market Data Access Layer，向下聚合多个行情/财务数据源，向上提供**统一的数据语义**：

- canonical history schema（`symbol/datetime/open/high/low/close/volume/amount/source`）
- `volume = shares`、缺失值 `None`（不伪造成 0）
- 结构化异常 + `auto` fallback + provenance（谁命中了、fallback 链是什么）
- 多市场：CN(SH/SZ/BJ) / HK / US

**Core MarketData providers**：hithink / miniQMT / TDX / Yahoo / Sina(via AkShare) / AkShare-Eastmoney
**CLI extras**（辅助数据，非行情核心）：AkShare 资金流 / 板块 / 两融等

---

## 2. Install

```bash
git clone https://gitee.com/smhe/mktdata.git   # 或 GitHub 镜像
cd mktdata

python -m venv .venv
# Windows: .venv\Scripts\activate   /  macOS·Linux: source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install .                # core（无强制依赖，全部惰性导入）
```

按需装 provider 依赖：

```bash
python -m pip install ".[public]"      # 公开数据源：akshare(新浪/东财) + easy-tdx + pandas
python -m pip install -e ".[dev]"      # 开发：+ pytest（离线单测）
```

> `xtquant`（miniQMT）依赖官方终端分发的 vendor 包，未写入 pyproject（见 §4 Provider setup）。

安装后可用 console script：

```bash
mktdata --help
```

`scripts/mktdata.py` 为兼容包装（`python scripts/mktdata.py --help` 亦可）。

---

## 3. 30-second first run（仅需 Python + 网络）

无需任何 key / 终端 / 第三方包，用最低依赖的 Yahoo 美股：

```python
from mktdata import MarketData

md = MarketData()
r = md.history("AAPL.US", "20260101", "20260110", source="yahoo")["AAPL.US"]

if not r.ok:
    raise RuntimeError(r.error)

print(r.data[:3])     # canonical rows
print(r.provenance()) # {'source': 'yahoo', 'requested_source': 'yahoo', 'fallback_chain': []}
```

---

## 4. Provider setup

| Provider | 需要什么 | 安装 |
|---|---|---|
| **hithink**（同花顺） | API Key 文件 `%APPDATA%\hithink-finance\credentials.env`，内容 `HITHINK_FINANCE_API_KEY=...`；网络 `fuyao.aicubes.cn` | 无 pip 依赖 |
| **miniQMT**（本机行情） | ① miniQMT 终端正在运行；② Python 可 `import xtquant`；③ xtdata 本地服务 `127.0.0.1:58610` 可连 | vendor `xtquant`（详见 `references/setup.md`） |
| **TDX**（通达信） | 网络可达通达信行情服务器 | `pip install easy-tdx pandas`（即 `.[public]`） |
| **Sina / AkShare-Eastmoney** | 网络可达对应域名 | `pip install akshare`（即 `.[public]`） |
| **Yahoo**（美股） | 网络 `query1.finance.yahoo.com` | 无（stdlib） |

`references/setup.md` 有 miniQMT 环境与连接的完整说明。

---

## 5. Common API examples

```python
from mktdata import MarketData

md = MarketData()

bars = md.history(["600519.SH", "000858.SZ"], "20260101", "20260828", adjust="none")
fin  = md.financial("600519.SH", statement="income", period="annual", limit=4)
inds = md.indicators("600519.SH")                      # report 缺省自动取最新年报
val  = md.valuation("600519.SH")
cal  = md.calendar(market="SH", start="20260801", end="20260828")
inst = md.instrument("600519.SH")
acts = md.corporate_actions("600519.SH", "20260101", "20260828")
sec  = md.sector("沪深300")
chk  = md.crosscheck(["600519.SH", "000858.SZ"], "20260818", "20260824")
```

### 消费 DataResult（R4）

> 即使只查询一个 code，`history()` 也返回 `{code: DataResult}`：

```python
results = md.history("600519.SH", "20260101", "20260201")
r = results["600519.SH"]

if r.ok:
    rows = r.data          # list[dict]，canonical schema
else:
    print(r.error)         # 全部源失败时的错误
    print(r.fallback_chain)  # [{'source': 'hithink', 'error_type': 'ProviderUnavailable', 'reason': '...'}, ...]
```

`DataResult` 字段：`ok` / `data` / `error` / `source`（实际命中的源）/ `requested_source` / `fallback_chain` / `provenance()`。

---

## 6. DataResult / error contract

结构化异常（`mktdata.errors`）：

| Error | 含义 |
|---|---|
| `InvalidParameter` | API 参数非法 |
| `InvalidSymbol` | 证券代码非法 |
| `ProviderUnavailable` | 依赖/网络/终端不可用 |
| `ProviderUnsupported` | source 不支持该市场/周期 |
| `ProviderDataEmpty` | provider 正常但无数据 |
| `ProviderAuthError` | credential 缺失/失效 |
| `ProviderRateLimited` | provider 限流 |

`auto` fallback 时，上述错误通常进入 `fallback_chain`（带 `error_type`），而不是直接抛出；全部源失败时才抛 `MktDataError`。

---

## 7. Symbol / period / adjust

### 规范代码（R6）

| Market | Example |
|---|---|
| SH | `600519.SH` |
| SZ | `000858.SZ` |
| BJ | `xxxxxx.BJ` |
| HK | `00700.HK` |
| US | `AAPL.US` |

港股必须 5 位：`00700.HK` 合法；`0700.HK`、`700.HK` 非法（`InvalidSymbol`）。

### history period

`1d / 1m / 5m / 15m / 30m / 60m`

### adjust

`none`（原始价）/ `front`（前复权）/ `back`（后复权）

### history canonical schema

每行严格为 `symbol, datetime, open, high, low, close, volume, amount, source`：
- `datetime`：日线 `YYYY-MM-DD`；分钟 `YYYY-MM-DD HH:MM`
- `volume` = shares（股）；`amount` = 成交额（本市场货币），provider 不提供时为 `None`（禁止伪造 0）
- 缺失值 = `None` / `NaN`

---

## 8. Auto fallback（R7）

`source="auto"` 时的源链：

| Request | auto chain |
|---|---|
| CN daily | `hithink → miniqmt → tdx` |
| CN minute | `miniqmt → tdx` |
| HK daily | `miniqmt → sina` |
| US daily | `yahoo → sina` |
| CN financial | `hithink → miniqmt` |
| HK financial | `akshare` |
| CN valuation | `hithink → miniqmt → tdx` |
| HK valuation | `akshare` |
| CN indicators | `hithink → miniqmt` |

指定 `source="miniqmt"`（forced source）则只走该源，不再 fallback；forced source 在自动确定报告期等阶段同样严格生效。

### 参数校验（P1L-2）

非法日期 / `start>end` / 非法 `period` / `adjust` / `source` / `statement` / `financial period` 在进入 provider 前统一抛 `InvalidParameter`。

---

## 9. Provider capability（R10）

| Provider | CN history | HK history | US history | financial | valuation |
|---|:---:|:---:|:---:|:---:|:---:|
| hithink | Yes(1d) | No | No | CN | CN |
| miniQMT | Yes | Yes | No/视终端 | CN | CN |
| TDX | Yes(原始) | No | No | No | CN PB |
| Sina (via AkShare) | No/辅助 | Yes | Yes | No | No |
| AkShare/Eastmoney | No | No | No | HK F10 | HK |
| Yahoo | No | No | Yes | No | No |

可编程查询（`mktdata.capabilities`）：

```python
from mktdata import supports
supports("hithink", "history", market="CN", period="1d")  # True
supports("sina", "history", market="HK")                  # True
supports("tdx", "history", market="HK")                   # False
supports("miniqmt", "sector")                             # True（存在但无额外过滤元数据）
```

---

## 10. CLI

```bash
mktdata history --codes 600519.SH,00700.HK,AAPL.US --start 20260814 --end 20260821 --adjust none
mktdata financial --codes 600519.SH --statement all
mktdata valuation --codes 600519.SH,00700.HK
mktdata crosscheck --codes 600519.SH --start 20260818 --end 20260824
mktdata f10 --codes 00700.HK
mktdata extra --type all
```

---

## 11. Architecture

```text
CLI (mktdata/cli.py, console script: mktdata)  —— 薄壳：参数 → MarketData → 打印
  ↓
MarketData (mktdata/api.py)  —— 统一 Python API + 参数校验
  ↓
Router (mktdata/router.py)  —— 源链 / fallback / provenance / error_type
  ↓
Providers (mktdata/providers/)  —— hithink / miniqmt / tdx / yahoo / akshare
```

辅助模块：`models`（DataResult/Symbol/枚举）、`errors`（结构化异常）、
`symbols`（代码/市场识别）、`normalize`（日期/数值/FY 归一化）、
`validation`（参数校验）、`capabilities`（静态能力描述）。

---

## 12. Tests

```bash
python -m pytest -q          # offline 单元测试（免网络/免终端/免 credentials）
python scripts/test_all.py   # 真实集成回归（需 miniQMT 终端 + hithink key + 网络）
```

GitHub Actions（`.github/workflows/test.yml`）在 Python 3.10 / 3.12 上只跑 **offline pytest + `mktdata --help` smoke**，不访问 miniQMT / hithink / TDX / Yahoo / AkShare 网络。

## License

MIT
