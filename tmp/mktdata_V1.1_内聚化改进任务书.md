# mktdata 内聚化改进任务书 V1.1

> 目标：在**不引入 Qlib 专用代码、不引入回测/策略/交易逻辑**的前提下，把当前 `mktdata` 从“多源 CLI + 大单文件脚本”整理成一个**职责清晰、接口稳定、数据语义统一、可被其他项目复用的 Market Data Library**。
>
> 当前仓库：`smhe00/mktdata`
>
> 当前基线能力：9 数据源、多源自动路由、history / financial / valuation / crosscheck / f10 / extra，33/33 回归通过。

---

# 1. 本次改造的核心原则

## 1.1 mktdata 只负责“市场数据”

mktdata 的职责应严格限制为：

```text
数据源访问
    ↓
统一证券代码 / 市场识别
    ↓
统一字段和数据语义
    ↓
多源路由 / fallback
    ↓
数据质量检查 / provenance
    ↓
Python API + CLI
```

mktdata **不负责**：

```text
Qlib 专用格式
Qlib dump_bin
Alpha158 / Alpha360
因子计算框架
策略选股
回测
组合优化
下单 / QMT 交易
RL
模型训练
```

这些都应由下游项目适配 mktdata，而不是反过来污染 mktdata。

---

# 2. 当前主要问题

当前项目功能已经很强，但代码形态仍偏“Skill / CLI 工具”。

主要问题：

1. `scripts/mktdata.py` 超过 50KB，provider、路由、schema、CLI、业务逻辑混在一个文件。
2. 多数 provider 直接返回 `list[dict]` 或 `(rows, err)`，错误语义不统一。
3. history 虽然统一成 `date/open/high/low/close/volume/amount`，但不同数据源的：
   - volume 单位
   - 时间格式
   - 缺失值
   - 复权语义
   - market/symbol
   - 实际来源
   仍主要靠函数内部约定。
4. `calendar`、`instrument`、`dividends`、`sector` 等基础市场数据能力目前主要存在于 `qmt.py`，没有被完整纳入 `mktdata` 的统一 Python API。
5. symbol / market 判断散落在多个函数中，例如 `.SH/.SZ/.HK/.US` 判断逻辑。
6. fallback 路由逻辑直接写在 `cmd_history()` 等 CLI handler 内，不利于其他 Python 项目直接调用。
7. `test_all.py` 使用硬编码 Python 路径：
   ```python
   PY = r'D:\gitee\miniQMT\.venv\Scripts\python.exe'
   ```
8. 回归测试更偏“当前机器可运行”，缺少对 schema、错误类型、路由和 normalization 的纯单元测试。
9. 多源输出虽然有 source 描述，但 provenance 不是统一数据结构的一部分。
10. 文档中 `mktdata` 和 `qmt` 的能力边界比较清楚，但代码层还没有形成同等清晰的模块边界。

---

# 3. 本次改造目标

完成后，希望形成如下调用体验。

## 3.1 Python API

例如：

```python
from mktdata import MarketData

md = MarketData()

bars = md.history(
    codes=["600519.SH", "000858.SZ"],
    start="20260101",
    end="20260828",
    period="1d",
    adjust="none",
)

calendar = md.calendar(
    market="SH",
    start="20260101",
    end="20260828",
)

instrument = md.instrument("600519.SH")

actions = md.corporate_actions(
    code="600519.SH",
    start="20200101",
    end="20260828",
)
```

这些 API 是 **mktdata 自己的通用市场数据接口**，不是 Qlib 接口。

---

# 4. 建议目录结构

不要求一次做到完美，但建议至少拆成下面层次：

```text
mktdata/
├── __init__.py
│
├── api.py
│   # 对外统一 Python API：MarketData
│
├── models.py
│   # 通用结果结构 / dataclass / TypedDict
│
├── symbols.py
│   # symbol normalize / market detection
│
├── normalize.py
│   # 日期、数值、volume、字段归一化
│
├── errors.py
│   # 统一异常模型
│
├── router.py
│   # auto source / fallback 路由
│
├── providers/
│   ├── base.py
│   ├── hithink.py
│   ├── miniqmt.py
│   ├── tdx.py
│   ├── akshare.py
│   └── yahoo.py
│
└── cli.py
    # CLI，只做参数解析和打印

scripts/
├── mktdata.py
├── qmt.py
└── test_all.py
```

其中现有：

```text
scripts/mktdata.py
scripts/qmt.py
```

可以先保留为**兼容 wrapper**，避免现有 CLI、skill 和 PATH 配置失效。

---

# 5. P0：必须完成的改进

## P0-1. 抽离统一 Python API

新增：

```python
class MarketData:
    ...
```

至少提供：

```python
history(...)
financial(...)
valuation(...)
instrument(...)
calendar(...)
corporate_actions(...)
sector(...)
crosscheck(...)
```

### 要求

CLI handler 不再直接实现路由和 provider 调用，而是调用：

```python
MarketData(...)
```

例如：

```python
def cmd_history(args):
    md = MarketData()
    result = md.history(...)
```

### 验收

- 其他 Python 项目不需要 subprocess 即可调用 mktdata。
- CLI 输出结果与当前版本一致。
- 当前 33 项回归不退化。

---

## P0-2. Provider 与 Router 解耦

每个数据源都放入独立 provider 模块。

例如：

```python
class MiniQMTProvider:
    def history(...)
    def calendar(...)
    def instrument(...)
    def corporate_actions(...)
```

```python
class TDXProvider:
    def history(...)
    def valuation(...)
```

路由单独由：

```python
router.py
```

负责。

不要再在：

```python
cmd_history()
```

里面直接写：

```python
if source == "auto":
    if hk:
        ...
    elif us:
        ...
```

### 推荐结构

```python
router.history_sources(
    market="CN",
    period="1d",
    adjust="none",
)
```

返回：

```python
["hithink", "miniqmt", "tdx"]
```

然后统一执行 fallback。

### 验收

修改 fallback 顺序时，不需要修改 CLI。

---

## P0-3. 统一 Result / Error 模型

当前大量函数使用：

```python
return rows, None
return None, "错误字符串"
```

建议统一成结构化结果。

例如：

```python
@dataclass
class DataResult:
    data: object
    source: str
    ok: bool
    error: str | None = None
    fallback_chain: list[str] | None = None
```

或者直接异常化：

```python
class MktDataError(Exception):
    ...

class ProviderUnavailable(MktDataError):
    ...

class ProviderUnsupported(MktDataError):
    ...

class ProviderDataEmpty(MktDataError):
    ...

class ProviderAuthError(MktDataError):
    ...
```

自动路由层负责：

```text
unsupported
auth
timeout
empty
provider error
```

的区别。

### 重点

以下几种错误不能再都只是普通字符串：

```text
该源本身不支持
数据为空
网络失败
认证失败
限流
代码非法
参数非法
```

因为 fallback 策略不同。

### 验收

单元测试至少覆盖 6 类错误。

---

## P0-4. 统一 symbol / market 处理

新增：

```python
normalize_symbol()
detect_market()
```

统一支持：

```text
600519.SH
000858.SZ
430xxx.BJ / 8xxxxx.BJ
00700.HK
AAPL.US
```

禁止 provider 自己散落处理：

```python
endswith(".SH")
endswith(".SZ")
endswith(".HK")
```

### 建议模型

```python
@dataclass(frozen=True)
class Symbol:
    code: str
    exchange: str
    market: str
    canonical: str
```

例如：

```text
600519.SH
→ code=600519
→ exchange=SH
→ market=CN
```

### 验收

测试覆盖：

```text
SH
SZ
BJ
HK
US
非法代码
```

---

## P0-5. history 统一 schema

统一 history 的标准输出。

建议至少：

```text
symbol
datetime
open
high
low
close
volume
amount
source
```

可以继续允许 CLI 输出旧字段，但 Python API 内部统一。

### 规则必须明确

- `datetime`：
  - 日线统一 `YYYY-MM-DD`
  - 分钟统一 `YYYY-MM-DD HH:MM`
- `open/high/low/close/amount/volume`：
  - 数值类型统一为 float
- 缺失值：
  - 使用 `None` / NaN，不允许用 `0` 替代缺失行情
- 每条结果必须能够追溯 `source`

### 注意

不要为了 Qlib 引入：

```text
$open
$close
bin
instruments/all.txt
```

这些都不是 mktdata 的职责。

---

## P0-6. 统一 volume 单位

这是必须显式处理的语义。

当前 TDX 代码中已经存在：

```python
float(r["vol"]) / 100.0
```

说明不同数据源 volume 原始单位并不一致。

必须在 mktdata 中定义唯一标准。

建议优先：

```text
volume = shares
amount = 成交额（本市场货币）
```

因为这是跨市场更自然的定义。

### 要求

每个 provider 在边界处转换成 canonical volume。

禁止把单位转换留给下游项目猜。

### 验收

加入跨源测试：

```text
miniQMT vs TDX
```

不只比较 close，还比较 volume。

---

## P0-7. 复权语义统一

保留现有：

```text
none
front
back
```

但在 core 层统一定义语义。

例如：

```python
class AdjustMode(str, Enum):
    NONE = "none"
    FRONT = "front"
    BACK = "back"
```

各 provider 自己做映射：

```text
hithink:
front -> forward
back  -> backward

miniQMT:
front -> front
back  -> back
```

### 要求

provider 返回结果中应记录：

```text
adjust=none/front/back
```

禁止同一个 API 中不同 provider 对 adjust 有不同解释。

### 本次不要求

不要求为了 Qlib 生成专用 `factor` 字段。

但：

```text
corporate_actions / adjustment data
```

应保留为通用市场数据能力。

---

## P0-8. 把 calendar / instrument / corporate_actions 纳入统一入口

这些能力目前主要存在于 `qmt.py`。

它们本质上不是 “QMT 专用功能”，而是标准 Market Data。

因此应进入：

```python
MarketData.calendar()
MarketData.instrument()
MarketData.corporate_actions()
```

provider 可以仍然主要使用 miniQMT。

### calendar

统一返回：

```text
date
market
source
```

### instrument

至少：

```text
symbol
name
exchange
security_type
open_date
lot_size
source
```

如果 provider 能提供：

```text
close_date / delist_date
```

则保留，但本次不强制要求补齐历史退市库。

### corporate_actions

至少保留：

```text
symbol
date
cash_dividend
stock_bonus
stock_gift
allot_num
allot_price
adjustment_factor
source
```

### 验收

以下不再需要直接依赖 `qmt.py`：

```python
calendar
instrument
dividends
```

---

# 6. P1：强烈建议完成

## P1-1. CLI 变成纯壳层

目标：

```text
CLI 参数解析
    ↓
MarketData API
    ↓
结果格式化 / print / csv / json
```

CLI 内不得再维护 provider 业务逻辑。

### 保持兼容

以下命令必须继续工作：

```powershell
mktdata history ...
mktdata financial ...
mktdata valuation ...
mktdata crosscheck ...
mktdata f10 ...
mktdata extra ...
```

现有 `qmt` CLI 也不要立刻删。

---

## P1-2. 去除本机硬编码路径

至少清理：

```python
PY = r'D:\gitee\miniQMT\.venv\Scripts\python.exe'
```

测试应该使用：

```python
sys.executable
```

CLI wrapper 如果需要外部 Python 路径，则通过：

```text
环境变量
配置文件
当前 interpreter
```

解决。

仓库中不能继续依赖某台机器的绝对路径。

---

## P1-3. 增加 pytest 单元测试

现有 `test_all.py` 可保留作为：

```text
integration / environment regression
```

但增加：

```text
tests/
```

例如：

```text
tests/
├── test_symbols.py
├── test_normalize.py
├── test_router.py
├── test_errors.py
├── test_history_schema.py
└── test_provider_contract.py
```

这些测试必须：

- 不依赖 miniQMT 终端
- 不访问网络
- 使用 mock / fixture
- 可在 GitHub CI 中运行

### 保留

当前 33 项实际数据回归仍保留，标记：

```text
integration
```

---

## P1-4. Provider Contract

为 provider 定义最小 contract。

例如：

```python
class HistoryProvider(Protocol):
    def history(...) -> DataResult:
        ...
```

不同 provider 不要求实现所有能力。

例如：

```text
Yahoo:
history ✅
financial ❌
calendar ❌

TDX:
history ✅
valuation部分 ✅

miniQMT:
history ✅
calendar ✅
instrument ✅
corporate_actions ✅
```

明确：

```python
supports("history")
supports("calendar")
```

不要通过“调用失败”来判断能力。

---

## P1-5. Provenance 标准化

所有查询结果都应能回答：

```text
数据来自哪个 source？
是否发生 fallback？
之前哪个 source 为什么失败？
```

建议请求级 metadata：

```python
{
    "source": "miniqmt",
    "requested_source": "auto",
    "fallback_chain": [
        {
            "source": "hithink",
            "reason": "timeout"
        }
    ]
}
```

这样：

- CLI 可以打印简化来源
- 下游项目可以记录数据 lineage
- crosscheck 不需要重新发明来源说明

---

## P1-6. 参数校验前置

统一检查：

```text
code
market
start/end
period
adjust
source
```

而不是把非法参数传进 provider。

例如：

```python
start <= end
```

以及：

```text
TDX 不支持 HK
Yahoo 只支持 US
```

如果用户强制：

```text
--source tdx --codes 00700.HK
```

应返回结构化 `ProviderUnsupported`。

---

# 7. P2：可选增强

这些不是 V1.1 的阻塞项。

## P2-1. 批量 history API

当前主要逐 code 查询。

可以提供：

```python
history(
    codes=[...],
    ...
)
```

统一返回：

```python
dict[str, DataResult]
```

或者统一 DataFrame。

重点是：

- 并行策略由 provider / router 控制
- 上层不需要自己循环

但不要过早加入复杂 scheduler。

---

## P2-2. Source health

可以增加：

```python
md.health()
```

输出：

```text
hithink     OK
miniqmt     OK
tdx         OK
akshare     PARTIAL
yahoo       OK
```

这对 mktdata 本身很内聚。

但不要变成监控平台。

---

## P2-3. 数据质量验证器

提供通用的：

```python
validate_bars(...)
```

检查：

```text
high >= max(open, close)
low <= min(open, close)
volume >= 0
amount >= 0
datetime strictly increasing
duplicate datetime
```

这些是 Market Data 本身的质量规则。

这类能力值得放在 mktdata。

---

# 8. 明确不做的内容

本任务禁止加入以下内容：

```text
QlibProvider
QlibExporter
dump_bin
Alpha158
Alpha360
feature expression
factor library
backtest
portfolio
signal
strategy
model training
RL
QMT order / trade
数据库研究框架
```

即使未来下游需要，也应由：

```text
qlib_adapter
sequoia_adapter
research_adapter
```

等外部项目实现。

mktdata 只提供稳定、干净的 Market Data API。

---

# 9. 推荐实施顺序

建议 Agent 按下面顺序做，不要一次大爆炸式重写。

## Step 1

先抽出：

```text
symbols.py
models.py
errors.py
normalize.py
```

不改变任何 CLI 行为。

## Step 2

抽出：

```text
providers/miniqmt.py
providers/hithink.py
providers/tdx.py
providers/yahoo.py
providers/akshare.py
```

保持原函数行为。

## Step 3

实现：

```text
router.py
```

把 `cmd_history()` 中的 fallback 逻辑搬进去。

## Step 4

实现：

```text
api.py → MarketData
```

CLI 改成调用 API。

## Step 5

把：

```text
calendar
instrument
corporate_actions
sector
```

纳入统一 API。

## Step 6

增加：

```text
tests/
```

纯单元测试。

现有：

```text
scripts/test_all.py
```

保留做 integration test。

## Step 7

清理：

```text
硬编码本机路径
重复 market 判断
重复 date 转换
重复 numeric 转换
重复 source/fallback 打印
```

---

# 10. 兼容性要求

这是本次重构最重要的约束之一。

## 必须保持

现有 CLI：

```powershell
mktdata history
mktdata financial
mktdata valuation
mktdata crosscheck
mktdata f10
mktdata extra
```

参数兼容。

现有：

```powershell
qmt connect
qmt history
qmt quote
qmt dividends
qmt instrument
qmt calendar
qmt sector
```

本次不要删除。

## 可以变化

内部模块和实现可以重构。

---

# 11. 验收标准

只有以下全部满足，任务才算完成。

## 功能

- [ ] 新增稳定 `MarketData` Python API
- [ ] history 支持现有 auto fallback
- [ ] financial / valuation / crosscheck 功能不退化
- [ ] calendar 纳入统一 API
- [ ] instrument 纳入统一 API
- [ ] corporate_actions 纳入统一 API
- [ ] symbol / market 统一处理
- [ ] history schema 统一
- [ ] volume 单位统一并文档化
- [ ] adjust 语义统一并文档化
- [ ] source / fallback provenance 可查询

## 架构

- [ ] CLI 不直接承担 provider 路由
- [ ] provider 分模块
- [ ] router 独立
- [ ] normalization 独立
- [ ] error model 结构化
- [ ] 无 Qlib 专用代码
- [ ] 无交易代码

## 测试

- [ ] 当前 33/33 integration regression 保持通过
- [ ] 新增无需网络的 pytest 单元测试
- [ ] symbol 测试覆盖 SH/SZ/BJ/HK/US
- [ ] router fallback 有 mock 测试
- [ ] schema normalization 有测试
- [ ] provider unsupported / timeout / empty / auth 有错误类型测试

## 环境

- [ ] 不再硬编码本机 Python 绝对路径
- [ ] 测试使用 `sys.executable`
- [ ] 新机器可按 README 配置后运行

---

# 12. 完成后的合理定位

完成本次任务后，mktdata 应定位为：

> **一个多市场、多数据源、支持自动 fallback、统一数据语义和 provenance 的只读 Market Data Library + CLI。**

它不是：

```text
量化研究平台
Qlib 插件
策略平台
数据库平台
交易平台
```

而是这些系统共同依赖的：

```text
Market Data Access Layer
```

保持这个边界，后续项目才不会继续把各种特定业务逻辑塞回 mktdata。
