# mktdata P1-lite 第一轮审计与收口修复任务书

> 仓库：`smhe00/mktdata`
>
> 审计分支：`main`
>
> P0 基线：`7a4c8ba439389a73f8e5a8c785e6ba414050e51e`
>
> 当前审计 HEAD：`96ee9a9be57981e5dddc66c53deb654d08c9d012`
>
> Gate：**CHANGES_REQUIRED**

## 结论

P1-lite 主体实现正确：offline CI、基础 validation、README library-first、静态 capability 和新增 offline tests 都已落地。当前只剩两组窄范围 contract 一致性问题，修复后即可 PASS。

## 已确认通过

- `.github/workflows/test.yml` 已加入，仅跑 offline pytest。
- 已独立确认当前 `main` HEAD 的 GitHub Actions：
  - `pytest (3.10) = success`
  - `pytest (3.12) = success`
- `mktdata/validation.py` 已实现日期、区间、history period、adjust、source、statement 校验。
- `MarketData.history()` 已在 router/provider 前校验，测试确认非法输入时 provider 不会被调用。
- README 已明确 `Library API 是主入口 / CLI 是薄壳`，并写清 canonical history schema、`volume=shares`、`amount`、missing、adjust、provenance。
- `mktdata/capabilities.py` 采用静态字典 + `supports()`，没有引入插件系统/ABC/动态注册。
- 当前提交自报 `67 unit tests + 34/34 integration`；其中 integration 未由本审计远程重跑。

---

# Blocker A：Capability 与 public API contract 不一致

## A1. `sina` / `akshare` provider ID 错位

Public history source 当前允许：

```text
auto, hithink, miniqmt, tdx, sina, yahoo
```

Router 的 HK/US history fallback 也使用 `sina`。

但 `capabilities.py` 当前把 HK/US history 放在：

```python
"akshare": {
    "history": {"markets": {"HK", "US"}, "periods": {"1d"}}
}
```

导致：

```python
supports("sina", "history", market="HK", period="1d")   # False
supports("akshare", "history", market="HK", period="1d") # True
```

而 public API 实际恰好相反：`source="sina"` 合法，`source="akshare"` 对 history 会被 validation 拒绝。

### 修复要求

只修 capability 静态表，不要改 Router/source 命名：

```python
"sina": {
    "history": {
        "markets": {"HK", "US"},
        "periods": {"1d"},
        "note": "implemented via akshare Sina endpoints",
    }
},
"akshare": {
    "financial": {"markets": {"HK"}, "note": "Eastmoney F10"},
    "valuation": {"markets": {"HK"}},
},
```

必须新增：

```python
assert supports("sina", "history", market="HK", period="1d") is True
assert supports("sina", "history", market="US", period="1d") is True
assert supports("akshare", "history", market="HK", period="1d") is False
```

## A2. calendar capability market taxonomy 错位

`MarketData.calendar(market=...)` 当前接受：

```text
SH, SZ, HK
```

并拒绝 `CN`。

但 capability 当前写：

```python
"calendar": {"markets": {"CN", "HK"}}
```

于是：

```python
supports("miniqmt", "calendar", market="CN") # True
supports("miniqmt", "calendar", market="SH") # False
```

与 public API 相反。

### 修复要求

改成：

```python
"calendar": {"markets": {"SH", "SZ", "HK"}}
```

测试：

```python
assert supports("miniqmt", "calendar", market="SH") is True
assert supports("miniqmt", "calendar", market="SZ") is True
assert supports("miniqmt", "calendar", market="HK") is True
assert supports("miniqmt", "calendar", market="CN") is False
```

说明：上一份 P1-lite 任务书曾给出 `market="CN"` 的 capability 示例，本次结合实际 public API 复核后确认该示例不严谨。本轮以 **supports 与 public API 一致** 为准。

---

# Blocker B：Validation 尚未完全收口

## B1. calendar 非法 market 应抛 `InvalidParameter`

当前：

```python
raise MktDataError(...)
```

应改为：

```python
raise InvalidParameter(...)
```

## B2. sector 非法 name 应抛 `InvalidParameter`

当前空/非法 name 使用 `MktDataError`，应统一成 `InvalidParameter`。

## B3. calendar 必须检查完整 date range

当前 start/end 分别 `validate_date()`，但未检查 `start > end`。

如果 start/end 同时存在，应：

```python
start, end = validate_date_range(start, end)
```

只有单侧时再单独 `validate_date()`。

## B4. corporate_actions 同样检查 `start > end`

与 calendar 同样处理。

## B5. financial period 需要统一 validation

`MarketData.financial()` 当前实际支持：

```text
annual, quarterly
```

但 `period="foo"` 仍会进入 router/provider。

新增：

```python
validate_financial_period(period)
```

仅允许：

```text
annual, quarterly
```

非法统一抛：

```python
InvalidParameter
```

并在 `MarketData.financial()` 调 router 前调用。

不要与 history `validate_period()` 混用。

---

# 必须新增的测试

```python
with pytest.raises(InvalidParameter):
    md.calendar(market="CN")
```

并确认 `miniqmt_calendar` 未调用。

```python
with pytest.raises(InvalidParameter):
    md.calendar(market="SH", start="20260201", end="20260101")
```

```python
with pytest.raises(InvalidParameter):
    md.corporate_actions("600519.SH", start="20260201", end="20260101")
```

```python
with pytest.raises(InvalidParameter):
    md.sector("")
```

```python
with pytest.raises(InvalidParameter):
    md.financial("600519.SH", period="foo")
```

并确认 `router.execute_financial` 未调用。

---

# 非阻塞观察

- `indicators(report="foo")` 尚无 report validator；原 P1-lite 未定义完整 grammar，本轮不要扩 scope。
- `instrument()` 非法代码抛 `InvalidSymbol` 是合理专用异常，不需要改成 `InvalidParameter`。
- README capability 表同步把：
  - `Sina (via AkShare)` → HK/US history
  - `AkShare/Eastmoney` → HK financial/valuation
  拆清楚即可。

---

# 允许修改范围

预计仅：

```text
mktdata/capabilities.py
mktdata/validation.py
mktdata/api.py
README.md
tests/test_capabilities.py
tests/test_validation.py
tests/test_api.py
```

`.github/workflows/test.yml` 当前正确，不要改。

# 禁止事项

禁止：

```text
router/provider 大改
provider rename 全局重构
插件系统
缓存/数据库
异步/并发框架
retry framework
Qlib
因子/回测/策略/交易
MCP
P2
```

尤其不要为了 `sina/akshare` 命名问题修改 Router/source contract。

---

# Agent 完成后必须回报

1. 新 commit SHA
2. 修改文件列表
3. `pytest` 本地结果
4. `scripts/test_all.py` 本地结果
5. 新 HEAD GitHub Actions：Python 3.10 / 3.12
6. `sina` / `akshare` capability 对齐方式
7. calendar capability 对齐 `SH/SZ/HK`
8. calendar / corporate_actions range validation
9. calendar / sector 是否统一为 `InvalidParameter`
10. financial period validation

# 下一 Gate

若上述 A/B 两组问题全部修复，且新 HEAD：

```text
GitHub offline CI 3.10 = PASS
GitHub offline CI 3.12 = PASS
P0 contract 无 regression
```

则：

```text
P1-lite = PASS
```

随后停止继续工程化扩张，等待真实下游需求。
