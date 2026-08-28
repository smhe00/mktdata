# mktdata P0 第三轮审计与最终收尾任务书

> 仓库：`smhe00/mktdata`
>
> 审计分支：`main`
>
> 当前 HEAD：`b2f5b616109eb322e4cddebb7a67348d4c2f1325`
>
> 上一审计 HEAD：`fc9e72f10d996c0c5b83ca9b7eb40e513a79fed1`
>
> Gate：**CHANGES_REQUIRED**
>
> 结论：上一轮要求的主修改已经基本完成，但本次源码审计发现 **3 个很窄的 P0 收口问题**。其中第 1 项是实际执行路径问题，必须修复后才能 P0 PASS。禁止借本任务进入 P1/P2 或增加 Qlib 专用代码。

---

# 1. 本轮已经确认通过的修改

当前提交已完成上一轮大部分要求：

- [x] Yahoo 美股 `amount` 不可得时改为 `None`
- [x] AkShare/新浪美股 `amount` 不可得时改为 `None`
- [x] `extract_fiscal_year()` 已支持：
  - `FY2025`
  - `20251231`
  - `2025-4`
  - `2025`
- [x] `indicators` fallback 已从 CLI 主循环移入 router
- [x] 新增 `MarketData.indicators()`
- [x] 新增 `INDICATORS_CHAINS`
- [x] 新增 5 类 provider error propagation 参数化测试
- [x] `fallback_chain.error_type` 可保留结构化错误类型
- [x] 港股 F10 在 router financial 路径增加了 `"ERR ..."` 最小防护
- [x] 当前提交宣称 `52` 个单测和 `34/34` integration 通过

注意：

> GitHub 当前 HEAD 没有关联 CI status/check，因此本审计确认的是**源码与测试设计**。本审计无法把 commit message 中的本地 `52 + 34/34` 运行结果等同于远端 CI 独立证明。

---

# 2. Blocker A：港股 financial CLI 仍绕过 MarketData/router

这是本轮最重要的问题。

## 当前执行路径

`scripts/mktdata.py -> cmd_financial()` 中仍存在港股 early branch：

```python
if is_hk(code):
    f10out = ak_f10(code, limit)
    ...
    continue
```

因此港股：

```text
mktdata financial --codes 00700.HK ...
```

实际路径仍是：

```text
CLI
 ↓
ak_f10()
```

而不是：

```text
CLI
 ↓
MarketData.financial()
 ↓
router.execute_financial()
 ↓
ak_f10()
```

## 为什么这是实际 bug，而不仅是“架构洁癖”

本轮 Agent 已经在：

```text
router._call_financial()
```

加入港股 F10 内部错误防护：

```python
stmts = out.get("三大报表")

if isinstance(stmts, str) and stmts.startswith("ERR "):
    raise ProviderUnavailable(...)
```

但由于港股 CLI 根本没有走 router：

```text
这个防护对 CLI financial 港股路径完全无效。
```

而 `ak_f10()` 本身对于部分内部失败不是抛异常，而是可能返回：

```python
{
    "三大报表": "ERR ..."
}
```

于是当前 CLI 仍可能：

```text
底层报表失败
 ↓
ak_f10 返回 ERR 字符串
 ↓
cmd_financial 不抛异常
 ↓
CLI 把本次查询记为 status=ok
```

这正是 P0 Error Contract 要避免的“失败伪装成成功”。

---

# 3. Blocker A 修复要求

删除 `cmd_financial()` 中港股专用的直接 `ak_f10()` early branch。

所有：

```text
income
balance
cashflow
```

无论：

```text
CN
HK
```

都统一走：

```python
res = md.financial(
    code,
    statement=stmt,
    period=period,
    limit=limit,
    source=args.source,
)
```

CLI 只负责：

```text
参数
↓
MarketData
↓
格式化打印
```

## 允许港股有不同 formatter

可以根据：

```python
res.source == "akshare"
```

或返回结构类型，采用港股专用展示格式。

但：

> **取数、错误判断、fallback 不能再绕过 MarketData/router。**

---

# 4. Blocker B：港股 financial 目标 statement 缺失仍可能被误判成功

## 当前问题

router 当前港股 financial 判断大致为：

```python
if not (
    out.get("指标估值")
    or out.get("三大报表")
    or out.get("财务摘要")
):
    raise ProviderDataEmpty(...)
```

这个判断太宽。

例如用户请求：

```python
MarketData.financial(
    "00700.HK",
    statement="income",
)
```

如果：

```text
指标估值 = 有
三大报表 = {}
```

当前仍会因为：

```text
指标估值存在
```

而把 `income` 请求判定为成功。

这不符合：

```text
requested statement
```

的语义。

---

# 5. Blocker B 修复要求

对于 HK 的：

```text
income
balance
cashflow
```

至少检查对应目标报表是否存在。

`ak_f10()` 当前“三大报表”键类似：

```text
利润表(2025)
资产负债表(2025)
现金流量表(2025)
```

建议映射：

```python
HK_STATEMENT_PREFIX = {
    "income": "利润表(",
    "balance": "资产负债表(",
    "cashflow": "现金流量表(",
}
```

然后检查：

```python
stmts = out.get("三大报表")

if not isinstance(stmts, dict):
    raise ProviderDataEmpty(...)

prefix = HK_STATEMENT_PREFIX[statement]

if not any(str(k).startswith(prefix) for k in stmts):
    raise ProviderDataEmpty(...)
```

如果：

```python
stmts == "ERR ..."
```

继续保持：

```python
ProviderUnavailable
```

即可。

## 不要求

本轮不要求重构整个 F10 schema。

不要求把港股三表转换成与 A 股完全相同的字段模型。

只要求：

> **请求哪张表，至少确认哪张表真实存在。**

---

# 6. Blocker C：`indicators(source=...)` 在自动确定 FY 时未尊重 forced source

## 当前问题

当前：

```python
MarketData.indicators(
    code,
    report=None,
    source="miniqmt",
)
```

会先执行：

```python
router.latest_fiscal_year(code)
```

而 `latest_fiscal_year()` 固定：

```python
for src in ("hithink", "miniqmt"):
```

因此即使用户明确：

```text
source="miniqmt"
```

系统仍会先访问：

```text
hithink
```

来确定最新 FY。

这与 forced source 的语义不一致。

同理：

```python
source="hithink"
```

也不应在确定 report 时自动访问 miniQMT。

---

# 7. Blocker C 修复要求

将：

```python
latest_fiscal_year(code)
```

改为类似：

```python
latest_fiscal_year(
    code,
    requested="auto",
)
```

并复用 source resolution 逻辑。

建议：

```python
chain = resolve_indicators(
    market,
    requested=requested,
)
```

或定义相同语义的 FY source chain。

### 行为要求

```python
source="auto"
```

允许：

```text
hithink -> miniqmt
```

```python
source="hithink"
```

只能：

```text
hithink
```

```python
source="miniqmt"
```

只能：

```text
miniqmt
```

然后：

```python
MarketData.indicators(...)
```

必须调用：

```python
router.latest_fiscal_year(
    code,
    requested=source,
)
```

---

# 8. 必须新增的测试

## 8.1 港股 CLI financial 不得绕过 MarketData

至少做一个 unit/mock test，确认：

```text
00700.HK
```

的 financial CLI 核心路径使用：

```text
MarketData.financial
```

而不是直接：

```text
ak_f10
```

不强制做真实网络 CLI test。

---

## 8.2 港股 target statement validation

至少覆盖：

### Case 1

```python
statement="income"

三大报表 = {
    "利润表(2025)": {...}
}
```

应：

```text
PASS
```

### Case 2

```python
statement="income"

三大报表 = {
    "资产负债表(2025)": {...}
}
```

应：

```text
ProviderDataEmpty
```

### Case 3

```python
三大报表 = "ERR boom"
```

应：

```text
ProviderUnavailable
```

---

## 8.3 indicators forced source

用 mock 记录 provider 调用：

### Case 1

```python
md.indicators(
    "600519.SH",
    report=None,
    source="miniqmt",
)
```

必须确认：

```text
hithink_financial 未被调用
miniqmt_financial 被调用
```

### Case 2

```python
source="hithink"
```

必须确认：

```text
miniqmt_financial 未被调用
```

### Case 3

```python
source="auto"
```

允许：

```text
hithink fail -> miniqmt
```

---

# 9. 本轮不要再修改的内容

以下已经通过，不要重做：

```text
canonical history schema
volume shares contract
requested_source
pb_ok
calendar/instrument/corporate_actions 下沉
Yahoo amount=None
新浪美股 amount=None
5 类 error propagation
extract_fiscal_year
```

---

# 10. 禁止范围

禁止进入：

```text
P1
P2
Qlib
QlibExporter
dump_bin
策略
回测
因子框架
RL
交易
MCP
缓存框架
异步任务框架
目录二次大改
F10 全面重写
```

本轮只允许做上述三个 P0 final closeout。

---

# 11. 建议修改文件

预计只需要：

```text
mktdata/router.py
mktdata/api.py
scripts/mktdata.py
tests/test_contract.py
```

必要时可以增加一个 CLI mock test 文件。

不应该产生大规模 diff。

---

# 12. 回归要求

完成后必须继续通过：

```text
pytest
scripts/test_all.py
```

当前提交宣称基线：

```text
52 unit tests
34/34 integration
```

新提交有效测试数量不得减少。

---

# 13. Agent 完成后必须回报

1. 最新 commit SHA
2. `pytest` 完整结果
3. `scripts/test_all.py` 完整结果
4. 明确说明：
   - HK financial CLI 是否已全部走 MarketData
   - HK statement 是否按目标表验证
   - indicators forced source 是否在 FY 查询阶段也严格生效

---

# 14. 下一 Gate

如果以上 3 项全部满足：

```text
P0 = PASS
```

届时停止继续修 P0，不自动进入 P1/P2，等待下一独立任务。
