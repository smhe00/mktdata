# mktdata P1-lite 最终代码审计 + README/分发收口任务书

> 仓库：`smhe00/mktdata`
>
> 当前 `main` HEAD：`8192f075cf2b14a237dcb70c1be9832418a567a5`
>
> **代码 Gate：P1-lite = PASS**
>
> **README / Distribution Gate：CHANGES_REQUIRED**

## 1. 最终代码审计

上一轮唯一 blocker 已修复：

```python
cap = PROVIDER_CAPABILITIES.get(provider, {}).get(capability, None)
if cap is None:
    return False
```

现在能够正确区分：

```text
capability 不存在 -> False
capability 存在但 metadata={} -> True
```

测试已覆盖：

```python
supports("miniqmt", "instrument") is True
supports("miniqmt", "corporate_actions") is True
supports("miniqmt", "sector") is True
supports("miniqmt", "backtest") is False
supports("unknown", "instrument") is False
```

当前 commit 自报：

```text
71 unit tests
54/54 integration
```

本审计独立确认当前 HEAD 的 GitHub Actions：

```text
pytest (Python 3.10) = PASS
pytest (Python 3.12) = PASS
```

因此：

```text
P1-lite functional code = PASS
```

后续不要再修改 router/provider/validation/capability contract。

---

# 2. README 当前已有优点

应保留：

- Library API 是主入口，CLI 是薄壳
- `MarketData` API 示例
- canonical history schema
- `volume = shares`
- amount / missing semantics
- adjust
- provenance
- validation
- provider capability
- architecture
- offline / integration test 区分

当前问题集中在“一个新用户 clone 后是否真能照 README 使用”。

---

# 3. R1：README 展示 `mktdata ...`，但安装不会生成 CLI

README 当前：

```bash
pip install -e .
mktdata history ...
```

但 `pyproject.toml` 没有：

```toml
[project.scripts]
mktdata = "..."
```

当前 CLI 只是：

```text
scripts/mktdata.py
```

因此 `pip install -e .` 后并不能由 packaging 保证存在：

```bash
mktdata --help
```

## 要求

为“优雅使用”，正式提供 console script。

推荐：

```text
mktdata/cli.py
scripts/mktdata.py   # backward-compatible wrapper
```

`pyproject.toml`：

```toml
[project.scripts]
mktdata = "mktdata.cli:main"
```

`scripts/mktdata.py` 只保留：

```python
from mktdata.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

不要维护两份 CLI logic。

验收：

```bash
python -m pip install .
mktdata --help
```

必须返回 0。

---

# 4. R2：README 没说明 provider 的实际依赖

当前 `pyproject.toml` 无 dependencies / optional-dependencies。

但实际：

| Provider/能力 | 依赖 |
|---|---|
| Yahoo US daily | Python stdlib + network |
| Sina HK/US | `akshare` |
| HK F10 / valuation | `akshare` |
| TDX A-share | `easy-tdx` + `pandas` + network |
| miniQMT | miniQMT terminal + vendor `xtquant` |
| hithink | API key + network |

所以新用户只执行：

```bash
pip install -e .
```

后，README 的 A 股 quick-start 很可能三个 fallback 全失败：

```text
hithink -> no key
miniqmt -> no xtquant/terminal
tdx -> no easy-tdx/pandas
```

## 要求

README 必须明确 Core / Optional Provider setup。

推荐增加：

```toml
[project.optional-dependencies]
public = ["akshare", "easy-tdx", "pandas"]
dev = ["pytest"]
```

README：

```bash
python -m pip install .              # core
python -m pip install ".[public]"   # public providers
python -m pip install -e ".[dev]"   # development
```

`xtquant` 不要在未确认官方 pip 分发方式前写进依赖。

---

# 5. R3：需要一个真正能跑的 30-second first run

当前 quick-start 一次展示 A 股 history/financial/valuation、miniQMT metadata、crosscheck，不适合作为新用户首跑。

建议首例使用最低依赖 Yahoo：

```python
from mktdata import MarketData

md = MarketData()

r = md.history(
    "AAPL.US",
    "20260101",
    "20260110",
    source="yahoo",
)["AAPL.US"]

if not r.ok:
    raise RuntimeError(r.error)

print(r.data[:3])
print(r.provenance())
```

只依赖：

```text
Python + network
```

然后再给“配置 provider 后”的 A/HK 示例。

---

# 6. R4：README 必须展示 DataResult 怎么消费

必须明确：

> 即使只查询一个 code，`history()` 仍返回 `{code: DataResult}`。

建议示例：

```python
results = md.history("600519.SH", "20260101", "20260201")
r = results["600519.SH"]

if r.ok:
    rows = r.data
else:
    print(r.error)
    print(r.fallback_chain)
```

并简要说明：

```text
DataResult.ok
DataResult.data
DataResult.error
DataResult.source
DataResult.provenance()
```

---

# 7. R5：补齐错误模型

README 至少加短表：

| Error | 含义 |
|---|---|
| `InvalidParameter` | API 参数非法 |
| `InvalidSymbol` | 证券代码非法 |
| `ProviderUnavailable` | 依赖/网络/终端不可用 |
| `ProviderUnsupported` | source 不支持该市场/周期 |
| `ProviderDataEmpty` | provider 正常但无数据 |
| `ProviderAuthError` | credential 缺失/失效 |
| `ProviderRateLimited` | provider 限流 |

说明 auto fallback 时这些错误通常进入 `fallback_chain`。

---

# 8. R6：补 canonical symbol 表

至少写：

| Market | Example |
|---|---|
| SH | `600519.SH` |
| SZ | `000858.SZ` |
| BJ | `xxxxxx.BJ` |
| HK | `00700.HK` |
| US | `AAPL.US` |

港股必须强调：

```text
00700.HK valid
0700.HK invalid
700.HK invalid
```

---

# 9. R7：写明 auto fallback 顺序

建议直接加入：

| Request | auto chain |
|---|---|
| CN daily | `hithink -> miniqmt -> tdx` |
| CN minute | `miniqmt -> tdx` |
| HK daily | `miniqmt -> sina` |
| US daily | `yahoo -> sina` |
| CN financial | `hithink -> miniqmt` |
| HK financial | `akshare` |
| CN valuation | `hithink -> miniqmt -> tdx` |
| HK valuation | `akshare` |
| CN indicators | `hithink -> miniqmt` |

让用户理解 `source="auto"` 与 forced source 的区别。

---

# 10. R8：Provider setup 最低说明

## hithink

当前代码实际读取：

```text
%APPDATA%\hithink-finance\credentials.env
```

文件：

```text
HITHINK_FINANCE_API_KEY=...
```

README 必须明确。

## miniQMT

至少说明：

```text
1. miniQMT terminal 正在运行
2. Python 环境可 import xtquant
3. xtdata 本地服务可连接
```

并链接：

```text
references/setup.md
```

## TDX / AkShare

给 pip 安装命令即可。

---

# 11. R9：安装步骤从下载者视角写完整

当前只有：

```bash
pip install -e .
```

至少改为：

```bash
git clone https://github.com/smhe00/mktdata.git
cd mktdata

python -m venv .venv
# activate venv

python -m pip install --upgrade pip
python -m pip install .
```

开发者再用：

```bash
python -m pip install -e ".[dev]"
```

---

# 12. R10：区分 Core providers 与 CLI extras

README 顶部不要把：

```text
hithink / miniQMT / TDX / 新浪 / Yahoo / 东财 / 同花顺 / 雪球 / akshare-宏观
```

全部混成核心 provider。

建议：

```text
Core MarketData:
hithink / miniQMT / TDX / Yahoo / Sina(via AkShare) / AkShare-Eastmoney

CLI extras:
AkShare 资金流 / 板块 / 两融等辅助数据
```

---

# 13. 推荐 README 顺序

```text
1. What it is
2. Install
3. 30-second first run
4. Provider setup
5. Common API examples
6. DataResult / error contract
7. Symbol / period / adjust
8. Auto fallback
9. Provider capability
10. CLI
11. Architecture
12. Tests
```

---

# 14. 允许修改范围

允许：

```text
README.md
pyproject.toml
mktdata/cli.py
scripts/mktdata.py
tests/...                  # CLI/install smoke
.github/workflows/test.yml # 仅增加 mktdata --help smoke
```

禁止修改：

```text
router.py
provider routing contract
canonical schema
validation semantics
capabilities semantics
MarketData business logic
```

---

# 15. 最终验收

干净环境：

```bash
python -m pip install .
python -c "from mktdata import MarketData, supports; print('ok')"
mktdata --help
```

均成功。

README first-run 在：

```text
无 hithink key
无 miniQMT
无 easy-tdx
无 akshare
```

时，Yahoo 示例仅靠网络可执行。

CI 保持：

```text
Python 3.10 PASS
Python 3.12 PASS
```

最终：

```text
P1-lite code = PASS
README / Distribution = PASS
mktdata V1.1 = RELEASE-READY
```

随后停止继续工程化扩张。
