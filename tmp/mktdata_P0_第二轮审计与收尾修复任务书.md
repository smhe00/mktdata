# mktdata P0 第二轮审计与收尾修复任务书

> 仓库：`smhe00/mktdata`
>
> 审计分支：`main`
>
> 当前 HEAD：`fc9e72f10d996c0c5b83ca9b7eb40e513a79fed1`
>
> Gate：**CHANGES_REQUIRED**
>
> 结论：P0 已完成约 90%～95%。本轮只允许处理剩余窄缺口，禁止继续扩大重构范围，禁止进入 P1/P2，禁止加入任何 Qlib 专用代码。

---

# 1. 已通过项

以下 P0 项已实质闭环，本轮不要重做：

- [x] canonical history schema 已进入 `MarketData.history()`
- [x] `symbol / datetime / source` 已进入 canonical row
- [x] `volume = shares`
- [x] miniQMT volume 已按当前实测口径 `手 × 100 → 股`
- [x] TDX volume 保持原始 shares，不再 `/100`
- [x] router 已记录结构化 `error_type`
- [x] provider 已普遍由 `(None, "错误字符串")` 改成结构化异常
- [x] `api.py` 已不再直接 import / 调用 `xtdata`
- [x] calendar / instrument / corporate_actions / sector 已下沉到 miniQMT provider
- [x] `crosscheck.pb_ok` 已恢复
- [x] PB 5% relative tolerance 已恢复
- [x] `requested_source` 已进入 `DataResult`
- [x] provenance 不再硬编码 `auto`
- [x] 已新增 canonical / missing / provenance / pb_ok 等 contract tests
- [x] 已新增真实跨源 volume consistency integration test

---

# 2. 必修项 A：未知 amount 不能伪造成 0

## 当前问题

P0 contract 明确要求：

> 缺失值必须保留 `None` / NaN，禁止把“没有数据”伪造成真实的 0。

当前仍有两个明确漏点：

### Yahoo 美股

当前类似：

```python
"amount": 0.0
```

### AkShare / 新浪美股 fallback

当前类似：

```python
"amount": 0.0
```

这两个 source 实际没有提供可靠成交额字段。

因此：

```text
0.0
```

不是“真实成交额为 0”，而是“字段不可得”。

## 修复要求

统一改为：

```python
"amount": None
```

### 禁止

不要新增估算：

```text
close * volume
```

因为这并不等价于真实成交额。

---

# 3. 必修项 B：financial indicators fallback 仍残留在 CLI

## 当前问题

普通：

```text
income
balance
cashflow
```

已经通过：

```text
CLI
 ↓
MarketData.financial()
 ↓
router
 ↓
provider
```

但：

```text
financial --statement indicators
```

仍然在 `scripts/mktdata.py` 中自己维护：

```python
chain = ["hithink", "miniqmt"]

for s in chain:
    ...
```

以及直接调用：

```python
hithink_indicators(...)
miniqmt_indicators(...)
```

这违反 P0 Closeout 的最终分层要求。

## 修复要求

indicator fallback 必须从 CLI 移出。

推荐二选一。

### 方案 1：扩展 MarketData.financial

允许：

```python
MarketData.financial(
    code,
    statement="indicators",
    ...
)
```

由 API / router 处理。

### 方案 2：新增通用 API

例如：

```python
MarketData.indicators(...)
```

由 router 处理。

两种都可以。

### 要求

最终 CLI 不再出现：

```python
chain = ["hithink", "miniqmt"]
```

这类 fallback 业务逻辑。

CLI 只负责：

```text
参数
↓
MarketData
↓
打印
```

---

# 4. 必修项 C：修复 indicators 的 latest FY fallback regression

## 当前问题

CLI 当前 `_latest_fy()` 对 hithink 和 miniQMT 共用类似：

```python
re.match(r"FY(\d{4})", period)
```

但两者 period 格式不同。

### hithink

类似：

```text
FY2025
```

### miniQMT

类似：

```text
20251231
```

因此：

```text
hithink 不可用
→ fallback miniQMT
→ miniQMT 返回 20251231
→ FY 正则匹配失败
→ “无法确定最新报告期”
```

这是本轮重构引入的实际 fallback regression。

## 修复要求

年份解析必须标准化。

建议新增：

```python
extract_fiscal_year(period) -> int | None
```

至少支持：

```text
FY2025
20251231
2025-4
2025
```

### 推荐位置

放入通用 normalize/helper 层，而不是继续留在 CLI。

例如：

```text
mktdata/normalize.py
```

或：

```text
mktdata/models.py
```

不要为此新增大型模块。

---

# 5. 必修项 D：补齐 5 类 error propagation contract test

## 当前问题

实际代码已经有结构化异常，但 contract test 目前主要验证：

```text
ProviderUnavailable
ProviderDataEmpty
```

P0 审计要求是至少验证以下 5 类经过：

```text
provider
↓
router
↓
fallback_chain.error_type
```

能够保留类型：

```text
ProviderUnsupported
ProviderUnavailable
ProviderAuthError
ProviderDataEmpty
ProviderRateLimited
```

## 修复要求

建议直接参数化：

```python
@pytest.mark.parametrize("exc_cls", [
    ProviderUnsupported,
    ProviderUnavailable,
    ProviderAuthError,
    ProviderDataEmpty,
    ProviderRateLimited,
])
def test_router_preserves_provider_error_type(monkeypatch, exc_cls):
    ...
```

验证：

```python
assert result.fallback_chain[0]["error_type"] == exc_cls.__name__
```

### 注意

不要求实现复杂 retry/backoff。

本轮只是验证：

> Error type 没有再次退化成普通字符串。

---

# 6. 建议项 E：港股 financial 不应把 F10 内部 ERR 当成功

这一项建议本轮顺手处理，但不要扩展成 F10 全面重构。

## 当前问题

`ak_f10()` 内部部分失败可能返回：

```python
{
    "三大报表": "ERR ..."
}
```

而不是抛异常。

但：

```python
MarketData.financial(HK)
```

会通过 `ak_f10()` 取得港股财务。

因此存在：

```text
provider 内部失败
↓
返回正常 dict
↓
router / API 视为成功
```

的风险。

## 最小修复方式

仅在用于 financial 路径时检查：

```python
out = P.ak_f10(...)

stmts = out.get("三大报表")

if isinstance(stmts, str) and stmts.startswith("ERR "):
    raise ProviderUnavailable(stmts)
```

如目标字段不存在，也应：

```python
raise ProviderDataEmpty(...)
```

### 不要求

- 不要重写整个 `ak_f10`
- 不要重新设计 F10 schema
- 不要把 `f10` 命令全部迁入 `MarketData`
- 不要处理 P1/P2

---

# 7. 本轮允许修改范围

建议控制在：

```text
mktdata/providers/yahoo.py
mktdata/providers/akshare.py
mktdata/api.py
mktdata/router.py
mktdata/normalize.py          # 如加入 fiscal year helper
scripts/mktdata.py
tests/test_contract.py
tests/test_router.py          # 如需要
```

如实现确实不需要某个文件，不必强行修改。

---

# 8. 禁止范围

本轮禁止：

```text
P1
P2
QlibProvider
QlibExporter
dump_bin
Alpha158
Alpha360
策略
回测
因子框架
数据库平台
缓存平台
异步框架
MCP
交易
QMT 下单
RL
目录二次大重构
```

禁止再创建大规模 architecture layer。

---

# 9. 必须新增/更新的测试

## 9.1 missing amount

验证 Yahoo / US fallback 的 canonical 结果：

```python
amount is None
```

不能是：

```python
0.0
```

## 9.2 fiscal year parser

至少：

```python
extract_fiscal_year("FY2025") == 2025
extract_fiscal_year("20251231") == 2025
extract_fiscal_year("2025-4") == 2025
```

## 9.3 indicators fallback

模拟：

```text
hithink failure
miniQMT success
```

确认：

```text
MarketData / router 成功返回 miniQMT indicators
```

且 CLI 不自己 fallback。

## 9.4 5 类结构化异常

必须覆盖：

```text
ProviderUnsupported
ProviderUnavailable
ProviderAuthError
ProviderDataEmpty
ProviderRateLimited
```

## 9.5 港股 financial ERR

如处理建议项 E：

```text
ak_f10 "三大报表" = "ERR ..."
```

必须转成：

```text
MktDataError / ProviderUnavailable
```

而不是正常成功返回。

---

# 10. 回归要求

修复后必须继续通过：

```text
pytest
scripts/test_all.py
```

上一提交宣称：

```text
43 unit tests
34/34 integration
```

本轮测试数量可以增加，但不能减少已有有效覆盖。

---

# 11. Agent 完成后必须回报

Agent 提交后必须提供：

1. 最新 commit SHA
2. `pytest` 完整结果
3. `scripts/test_all.py` 完整通过结果
4. 明确说明：
   - Yahoo / US amount 如何处理
   - indicators fallback 移到了哪里
   - fiscal year 如何统一解析
   - 5 类 error propagation tests 是否都已覆盖
   - 港股 financial ERR 是否做了最小防护

---

# 12. 下一 Gate 判定

如果本任务全部满足：

```text
P0 = PASS
```

届时不要继续自动进入 P1/P2。

等待下一份独立审计任务。
