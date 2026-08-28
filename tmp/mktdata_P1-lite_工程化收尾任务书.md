# mktdata P1-lite 工程化收尾任务书

> 仓库：`smhe00/mktdata`
>
> 基线分支：`main`
>
> P0 基线 HEAD：`7a4c8ba439389a73f8e5a8c785e6ba414050e51e`
>
> 当前 Gate：`P0 = PASS`
>
> 本任务目标：在**不改变 P0 核心架构和数据语义**的前提下，补齐最必要的工程化能力，让 `mktdata` 更适合作为其他项目的稳定公共依赖。
>
> 本任务不是 V1.2 大重构，不进入 P2，不增加任何 Qlib 专用逻辑。

---

# 1. P1-lite 总目标

P0 已经完成：

```text
MarketData
  ↓
Router
  ↓
Providers
```

并具备：

```text
canonical history schema
structured error
fallback
provenance
volume=shares
missing=None
crosscheck
multi-market
```

P1-lite 只补以下 4 类能力：

1. GitHub offline CI
2. 统一参数 validation
3. README / API contract 文档更新
4. 轻量 Provider Capability 描述

最终目标：

> **让其他项目可以放心 `pip install -e .` / import `mktdata`，并在错误输入、provider 能力判断和持续回归方面有稳定 contract。**

---

# 2. 范围总览

## 必做

```text
P1L-1  GitHub offline CI
P1L-2  统一参数 validation
P1L-3  README / API contract 更新
P1L-4  Provider capability contract（轻量）
P1L-5  相应 offline tests
```

## 禁止

```text
缓存
SQLite
DuckDB
数据库
异步下载框架
并发调度框架
复杂 retry/backoff
Provider 插件系统
动态 entrypoint
QlibProvider
QlibExporter
dump_bin
Alpha158
Alpha360
因子框架
回测
策略
组合
RL
交易
QMT 下单
MCP server
PIT database
feature store
大规模目录重构
```

---

# 3. P1L-1：GitHub offline CI

## 目标

当前本地已经有完整 pytest，但 GitHub commit 没有远端 CI status。

本任务增加：

```text
GitHub Actions
  ↓
offline pytest
```

## 要求

新增：

```text
.github/workflows/test.yml
```

或等价命名。

CI 至少：

```text
checkout
setup-python
pip install -e .
pip install pytest
pytest -q
```

## Python 版本

至少测试：

```text
Python 3.10
Python 3.12
```

如依赖兼容性有问题，可以先只保留：

```text
Python 3.12
```

但 Agent 必须在报告中说明原因。

## 重要限制

CI **禁止**执行真实网络 integration：

```text
scripts/test_all.py
miniQMT
hithink API
TDX
Yahoo
AkShare 网络调用
```

原因：

```text
miniQMT 依赖本机终端
hithink 依赖本地 credentials
公网 provider 不稳定
```

CI 只跑：

```text
offline pytest
```

## 验收

GitHub Actions workflow 必须能够：

```text
push / pull_request
```

触发。

---

# 4. P1L-2：统一参数 validation

## 当前问题

部分输入已经由：

```text
normalize_symbol
router
provider
```

间接校验。

但对：

```text
date
period
adjust
source
statement
```

仍可能由不同 provider 各自报错。

这会导致：

```text
同一个非法输入
→ 不同 source
→ 不同异常行为
```

不利于 library contract。

## 目标

在进入 provider 前统一校验。

推荐新增：

```text
mktdata/validation.py
```

---

# 5. Validation Contract

至少实现：

```python
validate_date(value, name="start")
validate_date_range(start, end)
validate_period(period)
validate_adjust(adjust)
validate_source(source, allowed)
validate_statement(statement)
```

可以按当前 API 需要适当合并。

---

# 6. 日期规则

接受：

```text
YYYYMMDD
YYYY-MM-DD
```

非法示例：

```text
20261301
20260230
abc
2026/01/01
```

必须抛：

```python
InvalidParameter
```

如果：

```text
start > end
```

必须在调用 provider 前：

```python
raise InvalidParameter(...)
```

---

# 7. Period 规则

当前 history 至少支持：

```text
1d
1m
5m
15m
30m
60m
```

统一 validation 必须只接受当前 library 明确支持的值。

非法：

```text
13m
2d
daily
foo
```

应：

```python
raise InvalidParameter(...)
```

注意：

> 如果某个 period 在 library 总体合法，但某 provider 不支持，应该由 provider 抛 `ProviderUnsupported`，不能在全局 validation 阶段误判为非法。

---

# 8. Adjust 规则

统一允许：

```text
none
front
back
```

非法：

```text
qfq
hfq
forward
backward
foo
```

在 public API 层应：

```python
InvalidParameter
```

provider 内部可继续做 source-specific 映射。

---

# 9. Source 规则

Public API 的 `source` 必须显式校验。

### history

允许至少：

```text
auto
hithink
miniqmt
tdx
sina
yahoo
```

### financial

允许至少：

```text
auto
hithink
miniqmt
akshare
```

### valuation

允许至少：

```text
auto
hithink
miniqmt
tdx
akshare
```

### indicators

允许：

```text
auto
hithink
miniqmt
```

非法 source：

```text
foo
qlib
eastmoney-direct
```

必须：

```python
InvalidParameter
```

---

# 10. Statement 规则

`MarketData.financial()`：

```text
income
balance
cashflow
```

允许。

`indicators` 已有独立：

```python
MarketData.indicators()
```

非法：

```text
profit
assets
foo
```

必须：

```python
InvalidParameter
```

---

# 11. Validation 接入位置

推荐统一在：

```text
MarketData public API
```

最外层接入。

例如：

```python
def history(...):
    validate_date_range(start, end)
    validate_period(period)
    validate_adjust(adjust)
    validate_source(source, ...)
    ...
```

同理：

```text
financial
indicators
valuation
calendar
corporate_actions
```

按需要接入。

## 重要边界

不要重复在：

```text
CLI
Router
Provider
```

各自再造一套 validation。

推荐：

```text
CLI
 ↓
MarketData validation
 ↓
Router
 ↓
Provider
```

Provider 仍保留必要 source-specific defensive validation。

---

# 12. P1L-3：README / API Contract 更新

README 必须升级为：

> **library-first 使用说明**

至少包含：

```python
from mktdata import MarketData

md = MarketData()

md.history(...)
md.financial(...)
md.indicators(...)
md.valuation(...)
md.calendar(...)
md.instrument(...)
md.corporate_actions(...)
md.sector(...)
md.crosscheck(...)
```

---

# 13. README 必须明确的数据 contract

## history canonical schema

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

## volume

```text
volume = shares
```

## amount

```text
amount = turnover in market currency
```

provider 不提供时：

```text
None
```

禁止伪造：

```text
0
```

## missing

```text
None / NaN
```

## adjust

```text
none
front
back
```

## provenance

示例：

```python
res.provenance()
```

返回：

```python
{
    "source": "miniqmt",
    "requested_source": "auto",
    "fallback_chain": [
        {
            "source": "hithink",
            "error_type": "ProviderUnavailable",
            "reason": "..."
        }
    ]
}
```

---

# 14. README 必须说明 provider / market 能力

建议增加简洁表格：

| Provider | CN history | HK history | US history | financial | valuation |
|---|---:|---:|---:|---:|---:|
| hithink | Yes | No | No | CN | CN |
| miniQMT | Yes | Yes | No/视终端 | CN | CN |
| TDX | Yes | No | No | No | CN PB |
| AkShare/Sina | No/辅助 | Yes | Yes | HK F10 | HK |
| Yahoo | No | No | Yes | No | No |

表格允许按实际代码修正，不要过度承诺。

---

# 15. P1L-4：轻量 Provider Capability Contract

## 目标

P1-lite 不要求重写 router。

只要求建立一个**统一、可查询、静态的能力描述**。

推荐新增：

```text
mktdata/capabilities.py
```

例如：

```python
PROVIDER_CAPABILITIES = {
    "hithink": {
        "history": {"markets": {"CN"}, "periods": {"1d"}},
        "financial": {"markets": {"CN"}},
        "indicators": {"markets": {"CN"}},
        "valuation": {"markets": {"CN"}},
    },
    "miniqmt": {
        ...
    },
}
```

并提供：

```python
def supports(
    provider: str,
    capability: str,
    market: str | None = None,
    period: str | None = None,
) -> bool:
    ...
```

---

# 16. Capability Contract 边界

本任务只要求：

```text
静态 capability 描述
supports()
测试
README 可引用
```

**不要求**：

```text
router 全面改写为 capability-driven
动态注册 provider
插件机制
entry points
反射扫描
Provider ABC
大型 Protocol hierarchy
```

如果 Agent 为实现 `supports()` 引入复杂插件系统，视为超范围。

---

# 17. 至少覆盖的 capability

至少：

```text
history
financial
indicators
valuation
calendar
instrument
corporate_actions
sector
```

对于：

```text
f10
extra
fundflow
```

可以不纳入。

---

# 18. Capability Tests

至少测试：

```python
supports("hithink", "history", market="CN", period="1d") is True
supports("hithink", "history", market="US", period="1d") is False
supports("tdx", "history", market="CN", period="5m") is True
supports("tdx", "history", market="HK", period="1d") is False
supports("yahoo", "history", market="US", period="1d") is True
supports("miniqmt", "calendar", market="CN") is True
```

未知 provider / capability 推荐返回：

```python
False
```

---

# 19. P1L-5：Offline Tests

新增测试建议：

```text
tests/test_validation.py
tests/test_capabilities.py
```

---

# 20. Validation Tests 必须覆盖

## 日期

```text
20260101        PASS
2026-01-01      PASS
20260230        FAIL
abc             FAIL
start > end     FAIL
```

## period

```text
1d   PASS
1m   PASS
5m   PASS
13m  FAIL
```

## adjust

```text
none   PASS
front  PASS
back   PASS
qfq    FAIL
```

## source

至少对：

```text
history
financial
valuation
indicators
```

各测一个非法 source。

## statement

```text
income      PASS
balance     PASS
cashflow    PASS
foo         FAIL
```

---

# 21. Public API Validation Test

至少做一个真正经过：

```text
MarketData
```

的测试，例如：

```python
with pytest.raises(InvalidParameter):
    md.history(
        "600519.SH",
        "20260101",
        "20260201",
        period="13m",
    )
```

并确认 provider mock：

```text
未被调用
```

也就是说：

> Validation 必须发生在 provider 之前。

---

# 22. CI 验收

CI 必须只依赖：

```text
repository source
pytest
package install
```

不得依赖：

```text
本机 credentials
QMT terminal
Windows-specific path
网络
```

---

# 23. P1-lite 允许修改文件

建议：

```text
.github/workflows/test.yml
mktdata/api.py
mktdata/validation.py
mktdata/capabilities.py
mktdata/__init__.py
README.md
tests/test_validation.py
tests/test_capabilities.py
tests/test_api.py
```

必要时：

```text
pyproject.toml
```

可做最小调整。

---

# 24. 不建议修改的文件

除非确有必要，本轮不要大改：

```text
mktdata/router.py
mktdata/providers/*
scripts/mktdata.py
scripts/qmt.py
scripts/test_all.py
```

原则：

> **不触碰已经 PASS 的 P0 核心运行路径。**

---

# 25. 回归要求

完成后必须：

```text
pytest 全部通过
scripts/test_all.py 继续 34/34
GitHub Actions offline pytest PASS
```

如果真实 integration 因外部网络波动失败，必须区分：

```text
代码 regression
vs
外部 provider 暂时不可用
```

不能通过修改测试掩盖失败。

---

# 26. GitHub CI 要求

提交后必须确认 GitHub 上出现：

```text
Actions / Checks
```

并报告：

```text
workflow run URL 或 status
```

如果当前环境无法触发/查看，必须明确写：

```text
workflow 已提交，但未能独立确认远端执行结果
```

禁止声称 CI PASS。

---

# 27. README 定位

README 开头建议明确：

> `mktdata` 是一个多市场、多数据源、支持自动 fallback、统一数据语义和 provenance 的只读 Market Data Library + CLI。

并明确：

```text
Library API 是主入口
CLI 是薄壳
```

---

# 28. 完成后的目标结构

```text
mktdata/
├── api.py
├── router.py
├── validation.py
├── capabilities.py
├── models.py
├── errors.py
├── symbols.py
├── normalize.py
└── providers/
```

---

# 29. P1-lite 验收清单

## CI

- [ ] `.github/workflows/...` 已加入
- [ ] CI 只跑 offline pytest
- [ ] CI 不访问 miniQMT / hithink / TDX / Yahoo / AkShare 网络
- [ ] GitHub 能显示 workflow/check

## Validation

- [ ] date 校验
- [ ] date range 校验
- [ ] period 校验
- [ ] adjust 校验
- [ ] source 校验
- [ ] statement 校验
- [ ] 非法输入统一抛 `InvalidParameter`
- [ ] provider 在非法输入时不会被调用

## Capability

- [ ] 有静态 provider capability 描述
- [ ] 有 `supports()`
- [ ] 未引入插件系统/复杂 ABC
- [ ] 有 capability tests

## README

- [ ] library-first
- [ ] `MarketData` 示例完整
- [ ] canonical history schema 写清
- [ ] volume=shares
- [ ] amount 语义
- [ ] missing=None
- [ ] adjust 语义
- [ ] provenance 示例
- [ ] provider capability 表

## Regression

- [ ] pytest PASS
- [ ] `scripts/test_all.py` 保持通过
- [ ] P0 contract 未被改变

---

# 30. Agent 完成后必须回报

必须提交：

1. 最新 commit SHA
2. 修改文件列表
3. `pytest` 完整结果
4. `scripts/test_all.py` 结果
5. GitHub Actions 状态
6. Validation 规则摘要
7. Provider capability 表摘要
8. README 更新摘要

---

# 31. Gate 规则

如果全部完成：

```text
P1-lite = PASS
```

如果出现：

```text
P0 contract regression
大规模 router/provider 重构
Qlib 代码进入核心库
新增缓存/数据库/异步框架
CI 依赖本机环境或外部网络
```

则：

```text
CHANGES_REQUIRED
```

---

# 32. 最终边界

本任务的定位不是“继续开发更多功能”，而是：

> **把已经通过 P0 的 mktdata 固化成一个稳定、可测试、可复用、可被其他项目依赖的公共 Market Data Library。**

完成 P1-lite 后停止继续工程化扩张，等待真实下游需求再决定后续任务。
