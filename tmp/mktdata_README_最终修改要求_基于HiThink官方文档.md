# mktdata README 最终修改要求（基于 HiThink 官方文档）

> 仓库：`smhe00/mktdata`
>
> 审计基线：`50f32fce8160cbd935766ba5caba78ce6d026e64`
>
> 本轮目标：**只完成 README / CLI 的 Release 收口，不再扩展功能。**
>
> 当前 Gate：**CHANGES_REQUIRED**

---

# 1. 本轮修改原则

当前 README 的主体结构已经基本可用，不需要再做大规模重写。

本轮只处理以下事项：

1. hithink 说明进一步做减法，以官方仓库作为唯一权威文档；
2. README 中 miniQMT-first 的描述必须与真实 Router 完全一致；
3. CLI help 中残留的 hithink-first 文案必须修正；
4. Windows `mktdata --help` 中文编码问题必须修复；
5. 增加 Windows CLI smoke，防止再次回归。

除此之外，不要再扩展 Router / Provider / API / capability / validation。

---

# 2. hithink：README 不再重复维护官方产品说明

HiThink 官方仓库：

```text
https://github.com/HiThink-Tech/Financial-API
```

官方 REST API 契约：

```text
https://github.com/HiThink-Tech/Financial-API/tree/main/docs/api
```

API Key 管理：

```text
https://fuyao.aicubes.cn/admin/
```

官方仓库已经完整维护：

```text
REST API
API Key
CLI
Python SDK
MCP
Skill
marketdb
能力范围
认证方式
错误码
接口字段
```

因此 mktdata README **不应该复制这些内容**。

mktdata README 只负责回答一个问题：

> “怎么让 mktdata 使用 hithink provider？”

---

# 3. README 中 hithink 最终建议写法

请将当前较长的 hithink 章节收敛为类似下面的短说明：

## hithink（同花顺官方 A 股数据，可选）

mktdata 可直接调用同花顺官方 **Financial API** 获取 A 股行情、财务、指标和估值数据。

**使用 mktdata 不需要另外安装 hithink CLI、Python SDK、MCP 或 Skill。**

如需启用 hithink：

1. 在同花顺官方服务创建 API Key；
2. 设置环境变量：

```text
HITHINK_FINANCE_API_KEY=你的_API_Key
```

mktdata 会自动读取该变量，并通过官方 REST API 访问数据。

官方项目及最新接入说明：

```text
https://github.com/HiThink-Tech/Financial-API
```

REST API 契约：

```text
https://github.com/HiThink-Tech/Financial-API/tree/main/docs/api
```

API Key 管理：

```text
https://fuyao.aicubes.cn/admin/
```

> API Key 不要写入代码、日志、公开配置或 Git 仓库。  
> hithink 的接口、能力范围、认证方式和错误码，以官方仓库最新说明为准。

---

# 4. README 中应删除的 hithink 内容

删除或大幅下沉以下内容：

```text
npm install -g @hithink-tech/hithink-finance-cli
Node.js >= 22.12
hithink-finance auth login
Skill 安装
MCP 安装
Python SDK 安装
marketdb
官方 CLI 的详细用法
各平台 credentials.env 的详细路径
```

这些都不是 mktdata 使用 hithink 的前置条件。

## 保留原则

mktdata 内部可以继续兼容：

```text
credentials.env
```

但 README 推荐的唯一配置方式应是：

```text
HITHINK_FINANCE_API_KEY
```

这样最简单，也最不容易过时。

---

# 5. 不要写“安装 hithink”

README 不应出现模糊表述：

```text
安装 hithink
```

因为官方同时提供：

```text
CLI
Python SDK
MCP
Skill
REST API
```

容易让用户误解。

正确说法应是：

```text
启用 hithink provider
```

对 mktdata 而言，实际要求只有：

```text
API Key + 网络
```

---

# 6. 不要继承 HiThink SDK 的 Python 版本要求

HiThink 官方 Python SDK 有自己的 Python 版本要求，但：

```text
mktdata 当前不是通过官方 Python SDK 接入 hithink
```

而是直接调用：

```text
https://fuyao.aicubes.cn
```

REST API。

因此不要因为官方 SDK 的要求，在 mktdata README 中写：

```text
hithink 需要 Python 3.11+
```

除非未来 mktdata 自己真的改成依赖该 SDK。

---

# 7. miniQMT-first：README 全文必须只有一套真实顺序

当前 Router contract：

```text
A股日线：miniQMT → hithink → TDX
A股分钟：miniQMT → TDX
港股日线：miniQMT → Sina
美股日线：Yahoo → Sina

A股财务：miniQMT → hithink
A股估值：miniQMT → hithink → TDX
A股指标：miniQMT → hithink
```

README 中所有相关表格、FAQ、说明都必须统一到这一套顺序。

## 必须修正的 FAQ

如果当前仍有：

```text
hithink → miniQMT → TDX
```

必须改为：

```text
miniQMT → hithink → TDX
```

不要允许 README 中同时存在两套 source priority。

---

# 8. “我需要配置哪个数据源？”建议最终表述

建议保留用户任务导向的表格：

| 我想获取 | 最简单配置 | auto 时的数据源 |
|---|---|---|
| 美股日线 | 最小安装即可 | Yahoo → Sina |
| 港股日线 | `.[public]` 即可用 Sina；有 miniQMT 时优先 miniQMT | miniQMT → Sina |
| A股日线 | 有 miniQMT 优先；否则 `.[public]` 可使用 TDX；配置 hithink 后增加一层官方源 | miniQMT → hithink → TDX |
| 港股财务 / 估值 | `.[public]` | AkShare / Eastmoney |
| A股财务 | miniQMT 或 hithink | miniQMT → hithink |
| A股估值 | miniQMT / hithink；无二者时可退到 TDX（主要 PB） | miniQMT → hithink → TDX |
| A股财务指标 | miniQMT 或 hithink | miniQMT → hithink |
| 日历 / 证券资料 / 分红 / 板块 | miniQMT | miniQMT |

这样比按 provider 分类更适合第一次使用的人。

---

# 9. README 首屏不要把 hithink 讲得过重

第一页仍应按用户能力组织：

```text
A股 / 港股 / 美股历史行情
A股 / 港股财务与估值
A股财务指标
交易日历 / 证券资料 / 公司行动 / 板块
```

hithink 只是其中一个 provider。

不要让 README 第一屏看起来像：

```text
mktdata = hithink 的包装器
```

mktdata 的核心价值仍然是：

```text
统一 API
多市场
多数据源
自动 fallback
统一数据语义
provenance
```

---

# 10. CLI help 必须同步 miniQMT-first

当前 CLI help 如果仍存在：

```text
hithink 优先、miniQMT 兜底
```

必须删除。

建议主描述：

```text
本地 miniQMT 可用时优先，多源自动 fallback 的市场数据入口
```

Financial：

```text
A股财务：miniQMT → hithink；港股：Eastmoney F10
```

Valuation：

```text
A股估值：miniQMT → hithink → TDX；港股：Eastmoney
```

重点：

```text
CLI help
README
Router
```

三者必须一致。

---

# 11. Windows Release Blocker：`mktdata --help` 中文编码

上一轮 clean-room 已在全新 Windows Server 2025 / Python 3.12 中真实复现：

```text
pip install .   PASS
pip check       PASS
mktdata --help  FAIL
```

异常：

```text
UnicodeEncodeError:
'charmap' codec can't encode characters
```

栈在：

```text
argparse.print_help()
encodings\cp1252.py
```

原因是 Windows stdout / pipe 在部分 locale 下不是 UTF-8，而 CLI help 包含中文。

## 修复要求

程序本身处理 UTF-8，不要求用户设置：

```text
PYTHONUTF8=1
```

建议只在：

```text
mktdata/cli.py
```

做窄修，例如：

```python
def _configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(
                    encoding="utf-8",
                    errors="replace",
                )
            except Exception:
                pass
```

在 `main()` 最开始调用，或采用等价跨平台安全方案。

不要把编码问题甩给用户配置环境变量。

---

# 12. 正式 CI 必须增加 Windows CLI smoke

当前 Linux CI 已经不能覆盖此问题。

在：

```text
.github/workflows/test.yml
```

增加轻量 Windows job：

```text
windows-latest
Python 3.12
pip install .
```

验证：

```powershell
mktdata --help
mktdata --help | Out-String
```

必须：

```text
exit code 0
```

CI 中不得预设：

```text
PYTHONUTF8
PYTHONIOENCODING
```

否则无法覆盖真实 Windows 默认编码问题。

---

# 13. README 30 秒首跑保持当前方向

继续使用：

```python
from mktdata import MarketData

md = MarketData()
r = md.history(
    "AAPL.US",
    "20260101",
    "20260110",
)["AAPL.US"]

if not r.ok:
    print("获取失败:", r.error)
else:
    print("数据来自:", r.source)
    print(r.data[:3])
```

不要在 first-run 强制写：

```python
source="yahoo"
```

第一例应该体现：

```text
source="auto"
```

是默认行为。

---

# 14. README 安装路径保持仓库安装优先

项目尚未正式发布 PyPI 时，第一推荐保持：

```bash
git clone https://gitee.com/smhe/mktdata.git
cd mktdata
python -m pip install ".[public]"
```

GitHub 镜像可以同时提供：

```text
https://github.com/smhe00/mktdata.git
```

不要把：

```bash
pip install "mktdata[public]"
```

写成当前主路径，除非已经正式发布 PyPI。

---

# 15. 本轮允许修改范围

只允许：

```text
README.md
mktdata/cli.py
.github/workflows/test.yml
tests/...   # 仅 CLI help / encoding contract
```

原则上不要修改：

```text
router.py
api.py
providers/*
capabilities.py
validation.py
pyproject.toml
```

尤其禁止：

```text
修改 source routing contract
重写 hithink provider
引入 HiThink Python SDK
引入 hithink CLI dependency
引入 MCP / Skill dependency
新增 cache / DB / async / backtest / Qlib
```

---

# 16. 建议新增测试

至少新增 CLI help contract 测试：

```python
assert "miniQMT" in help_text
assert "hithink 优先" not in help_text
```

exact wording 不重要，重点是：

```text
不能再次回退到 hithink-first 的错误文案
```

Windows encoding 由正式 Windows CI smoke 验证。

---

# 17. 本轮不要求重复的大范围测试

上一轮 clean-room 已实际通过：

```text
Gitee clone
GitHub clone
pip install .
pip install ".[public]"
Yahoo
Sina / AkShare HK
Sina / AkShare US
TDX A股 history
TDX A股 valuation
港股 financial
港股 valuation
无 miniQMT / hithink 时 fallback
```

因此本轮不需要 Agent 再扩大公网数据源测试。

miniQMT runtime 本轮也不要求重新测试。

hithink live API 也不要求在 CI 注入真实 API Key。

---

# 18. Agent 完成后只需回报

1. 新 commit SHA；
2. 修改文件列表；
3. README 中 hithink 最终简化内容；
4. CLI help miniQMT-first 修正；
5. README FAQ fallback 修正；
6. Windows CLI UTF-8 修复方式；
7. Ubuntu CI：Python 3.10 / 3.12；
8. Windows：
   - `mktdata --help`
   - `mktdata --help | Out-String`
9. 确认没有修改 Router / Provider contract。

---

# 19. 最终 Gate

如果：

```text
README hithink = API Key + 官方仓库引用
README/CLI/Router 的 miniQMT-first 语义一致
Windows mktdata --help PASS
Windows pipe help PASS
Ubuntu Python 3.10 / 3.12 CI PASS
```

则：

```text
mktdata V1.1 = RELEASE-READY
```

随后停止继续工程化扩张。
