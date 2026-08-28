# mktdata — 多市场、多数据源、自动 fallback 的只读 Market Data Library + CLI

> `mktdata` 是一个**多市场、多数据源、支持自动 fallback、统一数据语义和 provenance 的只读 Market Data Library + CLI**。
>
> **Library API 是主入口，CLI 是薄壳。**
>
> 数据源：hithink(同花顺) / miniQMT(本机xtdata) / TDX(easy-tdx) / 新浪 / Yahoo / 东财 / 同花顺 / 雪球 / akshare-宏观。
> 不含：Qlib、因子框架、回测、策略、交易。

## 快速开始

```bash
pip install -e .            # 安装 mktdata 包
```

```python
from mktdata import MarketData

md = MarketData()

bars  = md.history(["600519.SH", "000858.SZ"], "20260101", "20260828", adjust="none")
fin   = md.financial("600519.SH", statement="income", period="annual", limit=4)
inds  = md.indicators("600519.SH")                       # report 缺省自动取最新年报
val   = md.valuation("600519.SH")
cal   = md.calendar(market="SH", start="20260801", end="20260828")
inst  = md.instrument("600519.SH")
acts  = md.corporate_actions("600519.SH", "20260101", "20260828")
sec   = md.sector("沪深300")
chk   = md.crosscheck(["600519.SH", "000858.SZ"], "20260818", "20260824")
```

CLI（薄壳，等价）：

```bash
mktdata history --codes 600519.SH,00700.HK,AAPL.US --start 20260814 --end 20260821 --adjust none
mktdata financial --codes 600519.SH --statement all
mktdata valuation --codes 600519.SH,00700.HK
mktdata crosscheck --codes 600519.SH --start 20260818 --end 20260824
mktdata f10 --codes 00700.HK
mktdata extra --type all
```

---

## 数据契约（Data Contract）

### history canonical schema

`MarketData.history()` 返回 `{code: DataResult}`，`data` 为 `list[dict]`，每行严格为：

```text
symbol, datetime, open, high, low, close, volume, amount, source
```

- `datetime`：日线 `YYYY-MM-DD`；分钟 `YYYY-MM-DD HH:MM`
- **`volume` = shares（股）**：所有 provider 在边界统一转成股（miniQMT 原为"手"×100；TDX 原始即股）
- **`amount` = 成交额（本市场货币）**：provider 不提供时为 `None`，**禁止伪造成 0**
- **缺失值 = `None` / NaN**，禁止用 0 顶替
- `symbol` 为规范代码（如 `600519.SH`）；`source` 为实际命中的数据源

### adjust

```text
none（原始价） / front（前复权） / back（后复权）
```

### provenance

每个 `DataResult` 带 `source`、`requested_source`、`fallback_chain`，可查 `res.provenance()`：

```python
res.provenance()
# {'source': 'miniqmt', 'requested_source': 'auto',
#  'fallback_chain': [{'source': 'hithink', 'error_type': 'ProviderUnavailable', 'reason': '...'}]}
```

### 参数校验（P1L-2）

非法输入（非法日期 / `start > end` / 非法 `period` / `adjust` / `source` / `statement`）
在进入 provider 前统一抛 `InvalidParameter`，保证跨 source 行为一致。

```python
from mktdata.errors import InvalidParameter
md.history("600519.SH", "20260101", "20260201", period="13m")   # → InvalidParameter
md.history("600519.SH", "20260201", "20260101")                 # → InvalidParameter
```

---

## Provider / 市场能力

| Provider | CN history | HK history | US history | financial | valuation |
|---|:---:|:---:|:---:|:---:|:---:|
| hithink | Yes(1d) | No | No | CN | CN |
| miniQMT | Yes | Yes | No/视终端 | CN | CN |
| TDX | Yes(原始) | No | No | No | CN PB |
| Sina (via AkShare) | No/辅助 | Yes | Yes | No | No |
| AkShare/Eastmoney | No | No | No | HK F10 | HK |
| Yahoo | No | No | Yes | No | No |

可编程查询（P1L-4）：

```python
from mktdata import supports
supports("hithink", "history", market="CN", period="1d")   # True
supports("tdx", "history", market="HK")                    # False
```

---

## 架构

```text
CLI (scripts/mktdata.py)  —— 薄壳：参数 → MarketData → 打印
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

## 测试

```bash
python -m pytest -q          # offline 单元测试（免网络/免终端/免 credentials）
python scripts/test_all.py   # 真实集成回归（需 miniQMT 终端 + hithink key + 网络）
```

GitHub Actions（`.github/workflows/test.yml`）只跑 **offline pytest**（Python 3.10 / 3.12），
不访问 miniQMT / hithink / TDX / Yahoo / AkShare 网络。

## 许可证

MIT
