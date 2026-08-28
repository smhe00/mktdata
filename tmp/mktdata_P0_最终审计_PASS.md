# mktdata P0 最终审计报告

> 仓库：`smhe00/mktdata`
>
> 审计分支：`main`
>
> 当前 HEAD：`7a4c8ba439389a73f8e5a8c785e6ba414050e51e`
>
> 上一审计 HEAD：`b2f5b616109eb322e4cddebb7a67348d4c2f1325`
>
> Gate：**PASS**
>
> 结论：上一轮要求的 3 个 P0 final closeout blocker 已全部闭环。当前 P0 可以正式结束。**不要继续修改 P0，也不要自动进入 P1/P2。**

---

# 1. 本轮审计范围

本轮严格按上一份：

```text
mktdata P0 第三轮审计与最终收尾任务书
```

检查以下三个 blocker：

1. 港股 `financial` CLI 是否仍绕过 `MarketData/router`
2. 港股 financial 是否按请求的目标 statement 验证对应报表
3. `indicators(source=...)` 自动确定 fiscal year 时是否尊重 forced source

同时检查本次 diff 是否引入新的 P0 regression。

---

# 2. 变更范围审计

相对上一审计 HEAD：

```text
b2f5b616109eb322e4cddebb7a67348d4c2f1325
```

当前 HEAD：

```text
7a4c8ba439389a73f8e5a8c785e6ba414050e51e
```

为单一前向提交：

```text
ahead_by = 1
behind_by = 0
```

本次修改主要集中在：

```text
mktdata/api.py
mktdata/router.py
scripts/mktdata.py
tests/test_contract.py
```

符合上一轮“窄范围 final closeout”的要求，没有继续扩大架构重构。

---

# 3. Blocker A：港股 financial CLI 绕过 MarketData

## 上一轮问题

旧路径：

```text
cmd_financial()
 ↓
if is_hk(code)
 ↓
ak_f10()
```

导致：

```text
CLI
```

绕过：

```text
MarketData
router
```

从而 router 中的结构化错误判断无法保护 CLI。

## 当前实现

港股 early branch 已删除。

当前：

```python
res = md.financial(
    code,
    stmt,
    period,
    limit,
    source=args.source,
)
```

对：

```text
CN
HK
```

的：

```text
income
balance
cashflow
```

统一生效。

当前路径已经变成：

```text
CLI
 ↓
MarketData.financial()
 ↓
router.execute_financial()
 ↓
provider
```

港股仅保留 formatter 差异，不再自己取数或维护 fallback。

## 测试

新增：

```text
test_hk_financial_cli_uses_marketdata
```

通过 mock `MarketData.financial()` 验证：

```text
00700.HK
```

CLI 确实进入统一 API。

## 审计结论

```text
PASS
```

---

# 4. Blocker B：港股按目标 statement 验证

## 上一轮问题

旧逻辑只判断：

```text
指标估值
或
三大报表
或
财务摘要
```

任一存在即可。

因此用户请求：

```text
statement=income
```

即使只有：

```text
资产负债表
```

也可能被误判为成功。

## 当前实现

已新增：

```python
HK_STATEMENT_PREFIX = {
    "income": "利润表(",
    "balance": "资产负债表(",
    "cashflow": "现金流量表(",
}
```

并在 `router._call_financial()` 中按请求目标检查：

```python
if not isinstance(stmts, dict):
    raise ProviderDataEmpty(...)

if not any(str(k).startswith(prefix) for k in stmts):
    raise ProviderDataEmpty(...)
```

同时：

```text
三大报表 = "ERR ..."
```

继续映射为：

```text
ProviderUnavailable
```

因此现在可以区分：

```text
目标报表真实存在     → success
目标报表不存在       → ProviderDataEmpty
provider 内部失败    → ProviderUnavailable
```

## 测试

新增：

```text
test_hk_target_statement_validation
```

覆盖：

### Case 1

```text
income + 利润表存在
→ PASS
```

### Case 2

```text
income + 只有资产负债表
→ ProviderDataEmpty
```

### Case 3

```text
三大报表 = ERR boom
→ ProviderUnavailable
```

## 审计结论

```text
PASS
```

---

# 5. Blocker C：indicators forced source 在 FY 阶段生效

## 上一轮问题

旧：

```python
MarketData.indicators(
    source="miniqmt",
    report=None,
)
```

仍先调用：

```text
hithink
```

确定最新财年。

这违反：

```text
forced source
```

语义。

## 当前实现

`MarketData.indicators()` 已改为：

```python
fy = router.latest_fiscal_year(
    code,
    requested=source,
)
```

`latest_fiscal_year()` 当前通过：

```python
resolve_indicators(
    market,
    requested,
)
```

决定 source chain。

因此：

```text
source=auto
→ hithink → miniqmt
```

```text
source=hithink
→ hithink only
```

```text
source=miniqmt
→ miniqmt only
```

CLI `financial --source` 当前允许：

```text
auto
hithink
miniqmt
```

与该实现一致。

## 测试

新增：

```text
test_indicators_forced_source_fy_phase
```

覆盖：

### miniQMT forced

```text
hithink_financial 调用次数 = 0
miniqmt_financial 调用次数 = 1
```

### hithink forced

```text
miniqmt_financial 调用次数 = 0
hithink_financial 调用次数 = 1
```

### auto

```text
hithink fail
→ miniqMT fallback
```

## 审计结论

```text
PASS
```

---

# 6. P0 总体验收结果

| P0 Contract | 最终结果 |
|---|---|
| 统一 `MarketData` Python API | PASS |
| Provider / Router 分层 | PASS |
| Structured Error Model | PASS |
| Symbol / Market normalization | PASS |
| Canonical history schema | PASS |
| Missing value 不伪造成 0 | PASS |
| Volume 统一 shares | PASS |
| Adjust 基础语义 | PASS |
| calendar / instrument / corporate_actions / sector 下沉 provider | PASS |
| CLI 核心路径 → MarketData | PASS |
| `crosscheck.pb_ok` | PASS |
| `requested_source` provenance | PASS |
| 5 类 provider error propagation | PASS |
| indicators fallback / FY source contract | PASS |
| HK financial target statement validation | PASS |

---

# 7. 测试状态

当前 commit message 报告：

```text
55 unit tests
34/34 integration
```

本轮新增测试与代码实现是一致的，覆盖了上一审计提出的三个 blocker。

但需要记录一个审计事实：

```text
GitHub commit combined status 当前无远端 CI status/check。
```

因此：

> `55 + 34/34` 是仓库提交者报告的本地测试结果，不是 GitHub Actions 独立执行证明。

这不阻塞当前 P0 Gate，因为源码与测试设计已完成验收；后续如希望提高仓库工程可信度，可在独立 P1/工程化任务中增加 CI。

---

# 8. 非阻塞观察项

以下内容本轮**不构成 P0 blocker**，不要继续用 P0 名义修改：

## 8.1 CLI 仍保留部分 provider 直接 import

例如：

```text
f10
extra
crosscheck 的部分辅助路径
```

仍直接依赖 provider。

此前 P0 已明确：

```text
f10 / extra
```

不要求为本次 Closeout 扩大 API。

因此留待未来独立任务处理。

## 8.2 CLI 顶部说明仍有旧措辞

例如：

```text
部分已内联在各 cmd_*
```

与当前实际结构已有一定滞后。

这是文档/清理问题，不阻塞 P0。

## 8.3 港股 financial 返回仍是 F10 聚合 dict

目前：

```python
MarketData.financial("00700.HK", statement="income")
```

会验证利润表存在，但返回值仍是 F10 聚合结构，而不是与 A 股完全相同的统一三表 row schema。

此前 P0 没有要求统一 HK/CN 财报 schema，因此当前接受。

如后续要提高跨市场财务数据一致性，应另立任务，而不是继续扩大 P0。

---

# 9. 最终 Gate

```text
P0 = PASS
```

当前 HEAD：

```text
7a4c8ba439389a73f8e5a8c785e6ba414050e51e
```

可作为：

```text
mktdata V1.1 P0 baseline
```

---

# 10. 对 Agent 的指令

**不要再提交 P0 修复 commit。**

本阶段完成。

禁止自动开始：

```text
P1
P2
Qlib adapter
策略
回测
因子框架
交易
缓存
MCP
异步系统
```

等待下一份明确任务书。
