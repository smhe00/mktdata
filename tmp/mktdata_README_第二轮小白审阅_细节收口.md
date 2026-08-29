# mktdata README 小白视角第二轮审阅

> 仓库：`smhe00/mktdata`
>
> 当前 `main` HEAD：`9999d0e7b05d780493246cff768acb6a0b34ab7f`
>
> README 改版提交：`6c6adc3048ddf8b470fbb33812717a54e6d1b97a`
>
> Gate：**CHANGES_REQUIRED（README + 1项窄范围 auto 路由优先级调整）**
>
> 代码 Gate：**PASS**
>
> 结论：上一轮提出的主要“小白视角”问题基本都已经修掉。这一版已经接近可以公开给陌生用户使用。当前只剩几处会导致“照着 README 做却失败”或“误判支持范围”的具体问题，建议做最后一次纯文档收口。

---

# 1. 已确认改好的部分

本轮 README 已完成：

- 删除 `R4 / R6 / R7 / R10 / P1L-2` 等内部任务编号；
- 首页直接讲“能做什么”；
- 安装按用户类型组织；
- 30 秒首跑使用默认 `source="auto"`；
- `DataResult` 优先解释 `ok / data / source`；
- `provenance / supports()` 后置到高级用法；
- Symbol 格式前移；
- 常见任务改成按用户目标组织；
- 增加“我需要配置哪个数据源”表；
- 增加 FAQ；
- Architecture / Tests 下沉到末尾；
- 修正 `history()` 全源失败时返回 `ok=False`、而非抛异常的错误描述。

Agent 还新增：

```text
tests/test_error_contract.py
```

锁定以下行为：

```text
history 全源失败 -> DataResult(ok=False)
financial / indicators / valuation 无源 -> MktDataError
非法参数 -> InvalidParameter
非法代码 -> InvalidSymbol
```

这是合理的 contract regression。

---

# 2. CI：PASS

当前 `main` HEAD：

```text
9999d0e7b05d780493246cff768acb6a0b34ab7f
```

GitHub Actions 已独立确认：

```text
Python 3.10 = success
Python 3.12 = success
CLI smoke = success
Offline pytest = success
```

因此代码和 packaging 没有新的 blocker。

---

# 3. Blocker R1：README 首选安装命令假定已经发布到 PyPI

当前 README 的第一推荐安装方式是：

```bash
python -m pip install "mktdata[public]"
```

这条命令只有在：

```text
mktdata 已经发布到 PyPI
```

或用户已配置自定义 package index 时才成立。

当前仓库只能证明：

```toml
[project]
name = "mktdata"
```

以及 extras 已定义，并不能证明包已经发布。

本次公开检索没有找到与该仓库对应的 `mktdata` PyPI 发布页。

## 修复要求

如果项目**尚未发布 PyPI**，README 不应把：

```bash
pip install "mktdata[public]"
```

作为第一推荐。

推荐改成仓库安装：

```bash
git clone https://github.com/smhe00/mktdata.git
cd mktdata
python -m pip install ".[public]"
```

如果 Gitee 是主要分发源，则给出真实 Gitee 地址。

只有正式发布 PyPI 后，再把：

```bash
pip install "mktdata[public]"
```

放到第一位。

如果其实已经发布到私有 index，也必须明确 index URL / 配置方式。

---

# 4. Blocker R2：`git clone <本仓库地址>` 仍是占位符

当前 README：

```bash
git clone <本仓库地址>
```

对于 README 来说，这不是可复制执行的命令。

## 修复要求

直接写真实地址，例如：

```bash
git clone https://github.com/smhe00/mktdata.git
```

如果优先 Gitee，则：

```bash
git clone https://gitee.com/smhe/mktdata.git
```

可以同时列两个，但不要保留占位符。

---

# 5. Blocker R3：“能做什么”表没有说明市场范围，容易让用户以为 US 也支持财报/估值

README 开头先说：

```text
统一读取 A股 / 港股 / 美股市场数据
```

紧接着表格写：

```text
财务报表 ✅
估值（PE / PB / PS / PCF）✅
财务指标 ✅
交易日历 ✅
...
```

小白很容易理解成：

```text
A / HK / US 都支持这些功能
```

但实际不是。

当前实际主要是：

```text
history       -> A / HK / US
financial     -> A / HK
valuation     -> A / HK
indicators    -> A
calendar      -> miniQMT（SH/SZ/HK）
instrument    -> miniQMT
actions       -> miniQMT
sector        -> miniQMT
```

## 修复要求

把首屏表格改成：

| 数据 | 支持范围 |
|---|---|
| 历史行情 | A股 / 港股 / 美股 |
| 财务报表 | A股 / 港股 |
| 估值 | A股 / 港股 |
| 财务指标 | A股 |
| 交易日历 | miniQMT：SH / SZ / HK |
| 证券资料 | miniQMT |
| 分红送转 | miniQMT |
| 板块成分 | miniQMT |

这样用户在第一屏就能建立正确预期。

---

# 6. Blocker R4：“估值 PE/PB/PS/PCF”表述过满

当前 README 写：

```text
估值（PE / PB / PS / PCF） ✅
```

但不同 fallback source 返回字段并不一样。

例如：

```text
TDX valuation -> 主要只有 PB
HK AkShare/Eastmoney -> 当前主要 PE / PB
```

因此不能让小白认为：

```text
只要 valuation() 成功，PE/PB/PS/PCF 一定全部存在。
```

## 建议改成

```text
估值快照（字段随数据源而异；A股主要 PE/PB/PS/PCF，港股目前主要 PE/PB）
```

并在数据契约或 FAQ 写一句：

```text
不同 provider 能提供的估值字段不同，不可得字段返回 None。
```

---

# 7. Blocker R5：“A股财务 / 估值”被合并成同一 fallback 链，实际不准确

当前“我需要配置哪个数据源”表：

```text
A股财务 / 估值 | hithink 或 miniQMT | hithink → miniQMT
```

但实际：

```text
A股 financial:
hithink → miniQMT

A股 valuation:
hithink → miniQMT → TDX
```

而且：

```text
TDX valuation fallback 主要只能提供 PB。
```

## 修复要求

拆成两行：

| 我想获取 | 最简单配置 | auto |
|---|---|---|
| A股财务 | hithink 或 miniQMT | hithink → miniQMT |
| A股估值 | hithink / miniQMT；公开源可退到 TDX PB | hithink → miniQMT → TDX |

不要把两个 API 合并。

---

# 8. R6：北交所示例 `xxxxxx.BJ` 不是一个可复制的合法示例

当前 Symbol 表：

```text
北交所 | xxxxxx.BJ
```

这是格式占位符，不是真实代码。

README 其他例子都是可复制的：

```text
600519.SH
000858.SZ
00700.HK
AAPL.US
```

BJ 也应该一致。

建议使用真实的当前 6 位代码，例如：

```text
920002.BJ
```

北交所当前 920 号段是实际证券代码体系的一部分。

如果只想表达格式，也应明确写：

```text
`6位数字.BJ`，例如 `920002.BJ`
```

---

# 9. R7：开发者安装建议最好包含 public extras

当前：

```bash
python -m pip install -e ".[dev]"
```

而 `dev` 当前只包含：

```text
pytest
```

所以开发者按 README 安装后可以跑 offline tests，但不能完整运行：

```text
AkShare
TDX
integration tests
```

这不是硬 blocker，但建议更符合直觉：

```bash
python -m pip install -e ".[public,dev]"
```

并说明：

```text
miniQMT / xtquant 仍需单独配置。
```

如果只做核心开发，`.[dev]` 仍可以保留为最小开发环境。

---

# 10. R8：30 秒首跑应处理一次失败分支

当前：

```python
print("数据来自:", r.source)
print(r.data[:3])
```

在 Yahoo 网络不可用时：

```text
r.ok=False
r.data=None
```

那么：

```python
r.data[:3]
```

会报：

```text
TypeError
```

这会把一个“网络数据源不可用”伪装成“示例代码坏了”。

## 推荐首跑写成

```python
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

或者：

```python
assert r.ok, r.error
```

这与后面的 DataResult contract 保持一致。

---

# 11. 关于“港股日线最简单配置”可以再说得更自然

当前：

```text
港股日线 | .[public] | miniQMT → Sina
```

技术上 chain 没错，但：

```text
.[public]
```

并不会安装 miniQMT。

建议描述为：

```text
港股日线 | .[public] 即可使用 Sina；有 miniQMT 时会优先 miniQMT
```

这样新用户不会问：

> 为什么我明明装了 public，表里第一源却是 miniQMT？

---


# 12. 新增要求 R9：miniQMT 应成为本地可用时的第一优先级

用户侧的默认策略建议调整为：

> **本地 miniQMT 可用时优先使用 miniQMT；不可用时再 fallback 到外部数据源。**

理由不是简单追求某个 provider，而是：

```text
miniQMT = 本地终端 / 本地 xtdata 服务
```

在已经安装并运行的机器上：

- 调用链更短；
- 不需要每次走公网 REST；
- 通常延迟更低；
- A 股 history / financial / indicators / valuation 覆盖已经较完整；
- 港股日线也可直接使用。

因此 auto 路由应该体现“本地优先”。

## 当前实际 Router

目前仍是：

```text
A股日线       hithink -> miniQMT -> TDX
A股财务       hithink -> miniQMT
A股估值       hithink -> miniQMT -> TDX
A股财务指标   hithink -> miniQMT
```

这与新的使用原则不一致。

## 建议调整

改为：

```text
A股日线       miniQMT -> hithink -> TDX
A股分钟       miniQMT -> TDX               # 已符合
港股日线      miniQMT -> Sina              # 已符合
美股日线      Yahoo -> Sina                # miniQMT 当前不支持 US，保持

A股财务       miniQMT -> hithink
A股估值       miniQMT -> hithink -> TDX
A股财务指标   miniQMT -> hithink

港股财务      AkShare/Eastmoney            # 保持
港股估值      AkShare/Eastmoney            # 保持
```

`crosscheck()` 是主动比较多个数据源，不属于 fallback 路由，不改。

`calendar / instrument / corporate_actions / sector` 本来就是 miniQMT，保持。

## 代码修改边界

这里只允许窄改：

```text
mktdata/router.py
tests 中对应 source-chain / fallback 顺序断言
README.md
```

不要因此重构 Router 或 Provider。

## README 文案建议

在“我需要配置哪个数据源？”前明确写：

```text
如果本机已经安装并运行 miniQMT，mktdata 会优先使用 miniQMT；
miniQMT 不可用时，再自动切换到 hithink、TDX 或其他公网数据源。
```

Auto fallback 表同步改为上述新顺序。

---

# 13. 新增要求 R10：hithink 接入说明应写清“无需安装 CLI，只需 API Key”

目前 README 只说：

```text
hithink 需要 API Key
```

但第一次使用的人会自然产生两个问题：

```text
hithink 从哪里安装？
API Key 从哪里拿？
```

## 关键事实

`mktdata` 当前的 hithink provider：

```text
不依赖 hithink Python 包
不依赖 hithink CLI
```

它直接通过 Python 标准库访问同花顺官方 REST API：

```text
https://fuyao.aicubes.cn
```

因此对 mktdata 用户来说，hithink 的“安装”实际是：

```text
1. 注册 / 获取 API Key
2. 配置 API Key
```

官方同花顺金融数据服务由 HiThink-Tech 维护，统一 API Key 可在：

```text
https://fuyao.aicubes.cn/admin/
```

创建。

官方推荐凭据名：

```text
HITHINK_FINANCE_API_KEY
```

## README 建议用非常短的说明

建议直接写：

### hithink（同花顺官方 A 股数据）

mktdata 直接调用 hithink REST API，**不需要另外安装 hithink Python 包或 CLI**。

1. 打开同花顺金融数据服务并创建 API Key：

```text
https://fuyao.aicubes.cn/admin/
```

2. 配置 API Key。

推荐使用官方统一环境变量：

```text
HITHINK_FINANCE_API_KEY
```

Windows PowerShell 示例：

```powershell
[Environment]::SetEnvironmentVariable(
    "HITHINK_FINANCE_API_KEY",
    "你的_API_Key",
    "User"
)
```

重新打开终端后生效。

也可以使用用户级凭据文件：

```text
Windows:
%APPDATA%\hithink-finance\credentials.env

macOS:
~/Library/Application Support/hithink-finance/credentials.env

Linux:
${XDG_CONFIG_HOME:-~/.config}/hithink-finance/credentials.env
```

文件内容：

```text
HITHINK_FINANCE_API_KEY=你的_API_Key
```

不要把 API Key 提交到 Git。

## 需要同步检查当前 mktdata 实现

当前 `mktdata/providers/hithink.py` 的 `_read_hithink_key()` 主要读取 Windows：

```text
%APPDATA%\hithink-finance\credentials.env
```

而官方现在推荐：

```text
HITHINK_FINANCE_API_KEY
```

并定义了 Windows / macOS / Linux 用户级 credentials 路径。

为了让 README 与官方方式一致，建议顺手做一个很窄的兼容增强：

```python
def _read_hithink_key():
    # 1. 官方环境变量优先
    key = os.environ.get("HITHINK_FINANCE_API_KEY")
    if key:
        return key.strip()

    # 2. 再读取当前平台用户级 credentials.env
    ...
```

建议优先级：

```text
HITHINK_FINANCE_API_KEY
    ->
当前平台 credentials.env
    ->
None
```

这样：

- README 可以给出跨平台统一配置方法；
- 不要求用户安装官方 CLI；
- 与 hithink 官方 credential convention 一致；
- 兼容现有 Windows credentials.env。

## 官方 CLI 只作为可选说明

如果用户希望独立在终端直接使用 hithink，官方另外提供 CLI：

```bash
npm install -g @hithink-tech/hithink-finance-cli
hithink-finance auth login
```

需要 Node.js `>=22.12.0`。

但 README 应明确：

> **这个 CLI 不是使用 mktdata 的前置条件。**

不要让用户为了 mktdata 多装一套 Node.js 工具链。

官方文档：

```text
https://github.com/HiThink-Tech/Financial-API
https://fuyao.aicubes.cn/
```

---

# 14. 推荐这次不要再重写整个 README

上一轮已经完成结构性改版。

现在只做以下小修：

```text
1. 安装命令改成真实可执行
2. clone URL 去占位符
3. “能做什么”补市场范围
4. valuation 字段能力写准确
5. A股 financial / valuation 拆开
6. BJ 用真实示例
7. 30 秒示例处理 r.ok=False
8. 开发安装可改成 [public,dev]
```

不要再重排整份 README。

---

# 15. 最终评价

上一版：

```text
小白友好度 ≈ 5.5/10
```

当前版：

```text
小白友好度 ≈ 8/10
```

修完上述 6~8 个细节后，可以达到：

```text
9/10 左右
```

届时 README 可以认为：

```text
RELEASE-READY
```

不需要继续做更多工程化包装。

---

# 16. Gate

当前：

```text
P1-lite code = PASS
README structure = PASS
README factual / copy-paste usability = CHANGES_REQUIRED
```

下一轮以 README 细节为主；核心代码只允许两项窄改：① Router 的 miniQMT-first 顺序；② hithink API Key 读取兼容官方环境变量/跨平台 credentials。不得扩大其他核心代码 scope。
