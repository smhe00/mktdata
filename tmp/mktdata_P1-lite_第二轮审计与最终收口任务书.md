# mktdata P1-lite 第二轮审计与最终收口任务书

> 仓库：`smhe00/mktdata`  
> 审计分支：`main`  
> 上一审计 HEAD：`96ee9a9be57981e5dddc66c53deb654d08c9d012`  
> 当前 `main` HEAD：`3b5c63a7632e9bfdc223ee1629d38f07a2aca400`  
> Gate：**CHANGES_REQUIRED**

## 审计结论

上一轮要求已全部闭环：

- `sina` / `akshare` capability 已与 public source 对齐；
- calendar capability 已改为 `SH/SZ/HK`；
- calendar / sector 非法参数已统一为 `InvalidParameter`；
- calendar / corporate_actions 已补 `start > end`；
- financial 已新增 `annual/quarterly` validation；
- 当前 HEAD 的 GitHub Actions 已独立确认：
  - Python 3.10：PASS
  - Python 3.12：PASS

中间提交 `b671f092f5175e11c0f14e3282b1deaf09781064` 还修复了一个真实 API 问题：`providers/__init__.py` 原未导出 `miniqmt_calendar / miniqmt_instrument / miniqmt_corporate_actions / miniqmt_sector`，导致相应 `MarketData` 实调用可能 `AttributeError`。该修复接受；`scripts/test_all.py` 扩到 54 项并增加 MarketData real-data 回归，也接受。

当前提交自报：

```text
70 unit tests
54/54 integration
```

其中 integration 为 Agent 本地结果；远端 CI 本审计已独立确认通过。

---

# 唯一剩余 Blocker：`supports()` 对空 metadata capability 返回 False

当前 capability 表：

```python
"miniqmt": {
    ...
    "instrument": {},
    "corporate_actions": {},
    "sector": {},
}
```

这里 `{}` 的语义是：

> 支持该 capability，但没有额外的 market / period 过滤元数据。

但当前 `supports()`：

```python
def supports(provider, capability, market=None, period=None) -> bool:
    cap = PROVIDER_CAPABILITIES.get(provider, {}).get(capability)
    if not cap:
        return False
    ...
    return True
```

由于：

```python
bool({}) == False
```

所以当前错误地得到：

```python
supports("miniqmt", "instrument") is False
supports("miniqmt", "corporate_actions") is False
supports("miniqmt", "sector") is False
```

但这三个能力均已真实实现。

## 最小修复

必须区分：

```text
capability 不存在
```

和：

```text
capability 存在但 metadata={}
```

推荐：

```python
caps = PROVIDER_CAPABILITIES.get(provider)
if caps is None:
    return False
if capability not in caps:
    return False

cap = caps[capability]
```

或等价：

```python
cap = PROVIDER_CAPABILITIES.get(provider, {}).get(capability, None)
if cap is None:
    return False
```

不要引入 Capability class / ABC / Protocol / plugin registry。

## 必须新增测试

```python
assert supports("miniqmt", "instrument") is True
assert supports("miniqmt", "corporate_actions") is True
assert supports("miniqmt", "sector") is True
assert supports("miniqmt", "backtest") is False
assert supports("unknown", "instrument") is False
```

## 允许修改范围

原则上仅：

```text
mktdata/capabilities.py
tests/test_capabilities.py
```

如需同步 README 示例，可做极小修改。除此之外不要继续修改 api/router/providers/validation/test_all/CI，除非发现与本 bug 直接相关的确定错误。

## 回归要求

修复后必须保持：

```text
pytest PASS
GitHub Actions Python 3.10 PASS
GitHub Actions Python 3.12 PASS
scripts/test_all.py 54/54（本地）
```

## 下一 Gate

如果上述唯一 blocker 修复且无回归：

```text
P1-lite = PASS
```

随后停止继续工程化扩张。
