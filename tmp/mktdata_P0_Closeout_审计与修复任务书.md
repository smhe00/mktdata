# mktdata P0 Closeout 审计与修复任务书

> 仓库：`smhe00/mktdata`  
> 审计基线：`main`  
> 当前审计 HEAD：`3cb0f4f6ef675332af7c8a923da7ff1b54f96627`  
> Gate：**CHANGES_REQUIRED**
>
> 目标：只完成此前 P0 要求的收口修复。**禁止扩大到 P1/P2，禁止加入任何 Qlib 专用代码。**

---

# 1. 总体结论

当前 V1.1 重构方向正确，`api / router / models / errors / symbols / normalize / providers / tests` 等基础结构已经建立。

但核心问题是：

> **若干 P0 contract 目前只是“定义出来”，尚未真正贯穿运行路径。**

因此 P0 不能 PASS。

本次只修下面 8 项。

---

# 2. P0-1：真正落实 canonical history schema

## 当前问题

`models.py` 已定义：

```python
HISTORY_FIELDS = [
    "symbol", "datetime", "open", "high", "low", "close",
    "volume", "amount", "source",
]
```

但 provider 实际仍主要返回：

```python
{
    "date": ...,
    "open": ...,
    "high": ...,
    "low": ...,
    "close": ...,
    "volume": ...,
    "amount": ...
}
```

缺少：

```text
symbol
datetime
source
```

router 目前只是原样转发 provider rows。

## 修复要求

建立统一 normalization：

```python
normalize_history_rows(
    rows,
    symbol=...,
    source=...,
    period=...,
)
```

最终 `MarketData.history()` 必须返回：

```python
{
    "symbol": "600519.SH",
    "datetime": "2026-08-28",
    "open": 100.0,
    "high": 102.0,
    "low": 99.0,
    "close": 101.0,
    "volume": 1234567.0,
    "amount": 123456789.0,
    "source": "miniqmt",
}
```

规则：

- 日线：`YYYY-MM-DD`
- 分钟：`YYYY-MM-DD HH:MM`
- 缺失值保留 `None` / NaN
- 禁止用 `float(x or 0)` 把缺失静默改为 0

CLI 如需兼容旧 `date` 字段，可在 formatter 层映射：

```python
date = row["datetime"]
```

但 **Python API 必须使用 canonical schema**。

---

# 3. P0-2：修复 volume 单位 contract

## 当前问题

当前 contract 已声明：

```text
volume = shares（股）
```

但 TDX provider 存在：

```python
"volume": float(r["vol"]) / 100.0
```

即把股转换成手，与 canonical contract 冲突。

## 修复要求

统一定义：

```text
volume = shares
```

所有 provider 在边界转换成 shares。

必须确认：

```text
hithink
miniQMT
TDX
新浪
Yahoo
```

各自原始 volume 单位。

如原始为手：

```python
volume_shares = raw_volume * 100
```

如原始已经是股：

```python
volume_shares = raw_volume
```

禁止仅靠注释猜测。

## 测试

增加跨源 volume test，至少验证：

```text
miniQMT vs TDX
```

同股票、同日期 volume 应在合理容差内一致。

---

# 4. P0-3：让结构化 Error Model 真正生效

## 当前问题

已经定义：

```python
ProviderUnavailable
ProviderUnsupported
ProviderDataEmpty
ProviderAuthError
ProviderRateLimited
InvalidSymbol
InvalidParameter
```

但 provider 仍主要：

```python
return None, "错误字符串"
```

因此 router 无法区分不同失败类型。

## 修复要求

provider 层必须真正使用异常类型。

例如：

```python
raise ProviderUnsupported(...)
raise ProviderUnavailable(...)
raise ProviderAuthError(...)
raise ProviderDataEmpty(...)
raise ProviderRateLimited(...)
```

router 应保留 error type：

```python
{
    "source": "hithink",
    "error_type": "ProviderUnavailable",
    "reason": "timeout"
}
```

本次不要求复杂 retry/backoff，只要求：

> **错误类型不能再退化成普通字符串。**

---

# 5. P0-4：MarketData API 不得直接调用 xtdata

## 当前问题

目前：

```python
MarketData.calendar()
MarketData.instrument()
MarketData.corporate_actions()
MarketData.sector()
```

直接 import / 调用 `xtquant.xtdata`。

这违反 API / Provider 分层。

## 修复要求

将实现移入：

```text
mktdata/providers/miniqmt.py
```

至少新增：

```python
miniqmt_calendar(...)
miniqmt_instrument(...)
miniqmt_corporate_actions(...)
miniqmt_sector(...)
```

调用关系应为：

```text
MarketData
    ↓
provider / router
    ↓
xtdata
```

`api.py` 中禁止直接：

```python
from xtquant import xtdata
```

如果这些能力当前只有 miniQMT 一个 source，本次不强制增加复杂 router。

---

# 6. P0-5：CLI 真正变成壳层

## 当前问题

目前 `history` 已通过 `MarketData`，但 `financial / crosscheck` 等仍存在 CLI 直接调用 provider。

## 修复要求

本次至少要求：

```text
history
financial
valuation
crosscheck
```

统一调用：

```python
MarketData
```

CLI 只负责：

```text
argparse
↓
MarketData
↓
format / print / csv / json
```

禁止 CLI 自己维护 provider fallback。

### f10 / extra

如果当前 `MarketData` 尚未统一定义 `f10/extra`，本次可以保留现状。

不要为了这两个命令扩大 API 设计。

---

# 7. P0-6：修复 MarketData.crosscheck() regression

## 当前问题

docstring 声称返回：

```text
closes
pb
close_ok
pb_ok
```

但当前实现缺失：

```text
pb_ok
```

旧 CLI 中已有 PB 相对误差判断。

## 修复要求

恢复：

```python
relative_diff < 0.05
```

最终返回：

```python
{
    "last_day": ...,
    "closes": ...,
    "pb": ...,
    "close_ok": True,
    "pb_ok": True,
}
```

## 单测

必须覆盖：

```text
PB 三源接近 -> pb_ok=True
PB 明显偏离 -> pb_ok=False
```

---

# 8. P0-7：修复 requested_source provenance

## 当前问题

当前：

```python
DataResult.provenance()
```

硬编码：

```python
"requested_source": "auto"
```

因此：

```python
md.history(..., source="tdx")
```

仍会错误报告：

```text
requested_source = auto
```

## 修复要求

`DataResult` 增加：

```python
requested_source: str = "auto"
```

router 构造结果时填真实 requested：

```python
DataResult(
    ...,
    source=actual_source,
    requested_source=requested,
)
```

`provenance()` 返回真实值。

---

# 9. P0-8：补真正的 contract tests

当前测试更多是在验证：

```text
类存在
router chain 存在
基本 fallback 可运行
```

本次必须补以下 contract tests。

## 9.1 History schema

```python
assert set(row.keys()) == set(HISTORY_FIELDS)
```

至少验证：

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

全部存在。

## 9.2 Missing value

输入：

```python
open=None
```

输出必须仍为：

```python
None
```

不能变成：

```python
0.0
```

## 9.3 Volume unit

至少覆盖：

```text
miniQMT
TDX
```

最终 canonical volume 必须是 shares。

## 9.4 Error propagation

必须真正测试：

```text
ProviderUnsupported
ProviderUnavailable
ProviderAuthError
ProviderDataEmpty
ProviderRateLimited
```

经过：

```text
provider -> router
```

而不是只验证异常类继承关系。

## 9.5 requested_source

```python
res.requested_source == "tdx"
res.provenance()["requested_source"] == "tdx"
```

## 9.6 Crosscheck pb_ok

覆盖：

```text
True case
False case
```

---

# 10. 禁止扩大范围

本次禁止加入：

```text
QlibProvider
QlibExporter
dump_bin
Alpha158
Alpha360
factor framework
策略
回测
组合
RL
下单
交易
数据库平台
MCP server
大型缓存系统
异步调度系统
```

禁止把任务升级成：

```text
V1.2
全面重构
架构二次设计
```

本次只做：

> **P0 Closeout**

---

# 11. 兼容性要求

现有 CLI 不得退化。

至少保持：

```powershell
mktdata history
mktdata financial
mktdata valuation
mktdata crosscheck
mktdata f10
mktdata extra
```

以及：

```powershell
qmt connect
qmt history
qmt quote
qmt dividends
qmt instrument
qmt calendar
qmt sector
```

现有 33 项 integration regression 必须继续通过。

---

# 12. 验收标准

只有以下全部满足，P0 才可 PASS。

## Canonical API

- [ ] `MarketData.history()` 返回 canonical `HISTORY_FIELDS`
- [ ] `date` 已统一为 `datetime`
- [ ] 每行包含 `symbol`
- [ ] 每行包含真实 `source`
- [ ] missing 不再转成 0
- [ ] volume 实际统一为 shares

## Error

- [ ] provider 真正抛结构化异常
- [ ] router 能区分至少 5 类 provider error
- [ ] fallback provenance 包含 `error_type`

## 分层

- [ ] `api.py` 不直接 import `xtquant`
- [ ] calendar/instrument/corporate_actions/sector 由 provider 实现
- [ ] history/financial/valuation/crosscheck CLI 调用 `MarketData`
- [ ] fallback 逻辑不回流 CLI

## Provenance

- [ ] `requested_source` 不再硬编码 `auto`
- [ ] forced source provenance 正确

## Crosscheck

- [ ] `pb_ok` 已恢复
- [ ] PB 5% 相对容差规则有测试

## 测试

- [ ] schema contract tests
- [ ] missing-value test
- [ ] volume unit test
- [ ] provider error propagation tests
- [ ] requested_source test
- [ ] pb_ok test
- [ ] 原有 pytest 全部通过
- [ ] 原有 33/33 integration regression 全部通过

---

# 13. Agent 完成后必须提交

1. 修复 commit SHA
2. `pytest` 完整结果
3. `scripts/test_all.py` 33/33 结果
4. 简短实现说明：
   - canonical history schema 如何落实
   - volume 单位如何统一
   - provider error 如何映射
   - 哪些 CLI 已完全切到 `MarketData`
5. 不要只声明完成，必须提交实际代码和测试。

通过上述审查后，Gate 才可以从：

```text
CHANGES_REQUIRED
```

变为：

```text
PASS
```
