# mktdata README 小白视角审阅与改版意见

> 当前 `main` 最新提交：`15e51f1eb0803ce1ef01f63192d2ebb4de6019a5`
>
> 目标：按第一次下载仓库、不了解项目历史和 provider 背景的普通用户视角审阅。
>
> 结论：**技术信息基本齐全，但阅读路径仍像工程验收文档，不像用户手册。建议只重写 README，不再改核心代码。**

## 1. 最大问题：仍在对项目组成员说话

README 中出现：

```text
R4 / R6 / R7 / R10 / P1L-2
canonical
provenance
forced source
capability
Market Data Access Layer
```

`R4/R6/R7/R10/P1L-2` 都是内部任务编号，对外 README 应全部删除。

普通用户只关心：

```text
这个库能拿什么数据？
我该装什么？
第一段代码怎么跑？
失败了怎么办？
不同市场怎么用？
```

## 2. 第一屏先讲“能做什么”

建议开头直接写：

```text
mktdata 是一个统一读取 A股 / 港股 / 美股市场数据的 Python 库。

可获取：
- 历史行情
- 财务报表
- 估值
- 财务指标
- 交易日历
- 证券资料
- 分红送转
- 板块成分

默认会根据市场自动选择数据源，并在主数据源不可用时 fallback。
```

不要先讲 Access Layer / canonical / provenance。

## 3. 安装应该按“用户类型”组织

当前先 `pip install .`，后面再出现 `.[public]`，小白不知道该装哪个。

建议：

### 大多数用户（推荐）

```bash
python -m pip install ".[public]"
```

可用 AkShare/Sina/TDX 等公开数据源。

### 最小安装

```bash
python -m pip install .
```

说明：只装核心，主要可直接用 Yahoo；hithink 还需 key。

### miniQMT 用户

说明：安装 mktdata 后，还必须启动 miniQMT，并保证当前 Python 可 `import xtquant`。

### 开发者

```bash
python -m pip install -e ".[dev]"
```

## 4. 30 秒首跑不要先教 `source="yahoo"`

第一例最好体现这个库的价值：通常无需关心 provider。

建议：

```python
from mktdata import MarketData

md = MarketData()

r = md.history(
    "AAPL.US",
    "20260101",
    "20260110",
)["AAPL.US"]

print("source:", r.source)
print(r.data[:3])
```

然后说明：

```text
默认 source="auto"。
美股日线会优先使用 Yahoo。
通常不需要手工指定 source。
```

forced source 放到高级用法。

## 5. DataResult 解释应分层

新用户最先只需要：

```python
r.ok
r.data
r.source
```

示例：

```python
if r.ok:
    print(r.data)
    print("数据来自:", r.source)
else:
    print("获取失败:", r.error)
```

`fallback_chain` / `provenance()` 放到“调试与高级用法”。

## 6. README 有一处实质错误，必须修

当前写：

```text
auto fallback 时错误通常进入 fallback_chain；
全部源失败时才抛 MktDataError。
```

这对 `history()` 不成立。

真实行为：

```text
history:
全部源失败 -> DataResult(ok=False, error=..., fallback_chain=...)
不会抛 MktDataError

financial / indicators / valuation:
没有可用源 -> 抛 MktDataError

非法参数/代码:
直接抛 InvalidParameter / InvalidSymbol
```

README 必须按真实 API 改。

## 7. Common API examples 现在像 API checklist

当前一次列 9 个方法，对小白没有教学顺序。

建议改为“常见任务”：

```text
获取 A 股行情
获取腾讯港股行情
获取美股行情
获取财报
获取估值
```

每项 2~4 行代码。

`calendar / instrument / corporate_actions / sector / crosscheck`
放到“更多 API”表格即可。

## 8. 增加“我想取什么数据，该装什么”表

比 provider capability 表更实用：

| 我想获取 | 最简单配置 | auto 数据源 |
|---|---|---|
| 美股日线 | core | Yahoo → Sina |
| 港股日线 | `.[public]` | miniQMT → Sina |
| A股日线 | `.[public]` 可先用 TDX | hithink → miniQMT → TDX |
| 港股财务/估值 | `.[public]` | AkShare/Eastmoney |
| A股财务/估值 | hithink 或 miniQMT | hithink → miniQMT |
| 日历/证券资料/分红/板块 | miniQMT | miniQMT |

用户是按“我要什么数据”思考，不是按 provider 思考。

## 9. capability / supports() 后置

`supports()` 是好接口，但不是首页核心。

建议放到“高级用法”。

首页不要让 capability registry 抢占怎么拿数据的篇幅。

## 10. Symbol 规则前移

特别是：

```text
00700.HK
```

必须 5 位。

建议放在首跑后马上给：

| Market | Example |
|---|---|
| SH | `600519.SH` |
| SZ | `000858.SZ` |
| BJ | `xxxxxx.BJ` |
| HK | `00700.HK` |
| US | `AAPL.US` |

并明确：

```text
00700.HK valid
0700.HK / 700.HK invalid
```

## 11. 标题语言统一

现在中英混用：

```text
What it is / Install / Common API examples / Provider setup / Tests
```

正文基本是中文。

建议统一成：

```text
简介
安装
30 秒上手
数据源配置
常见用法
返回结果与错误处理
证券代码与参数
自动数据源切换
CLI
高级用法
开发与测试
```

## 12. Architecture 放最后

架构图没错，但属于 contributor 信息。

放到：

```text
开发者说明
```

下面即可。

## 13. 增加“常见失败”区

建议只写 4 个：

### A股为什么取不到？

```text
auto 会尝试 hithink / miniQMT / TDX。
三者均不可用时 history 返回 ok=False。
```

### miniQMT 为什么不工作？

```text
必须启动 miniQMT，并保证当前 Python 可 import xtquant。
```

### 腾讯为什么报 InvalidSymbol？

```text
使用 00700.HK，不是 700.HK。
```

### 港股财报为什么和 A 股字段不同？

```text
港股 financial 当前来自 Eastmoney F10，入口统一，但返回 schema 尚未与 A 股完全统一。
```

这一条很重要，避免把“统一 API”误解为“所有市场返回字段完全一致”。

## 14. 推荐 README 最终结构

```text
# mktdata
一句话价值

## 能做什么

## 安装
- 推荐公开数据源
- 最小安装
- miniQMT
- 开发者

## 30 秒上手

## 证券代码格式

## 常见任务
- A股
- 港股
- 美股
- 财务
- 估值

## 我需要配置哪个数据源？

## 返回结果与错误处理

## 自动 fallback

## 常见问题

## CLI

## 数据契约

## 高级用法
- forced source
- supports()
- crosscheck()

## 开发与测试
- architecture
- pytest
- integration
- license
```

## 15. 最终评价

当前 README：

```text
技术完整度：8.5/10
小白友好度：5.5/10
```

问题不是继续加内容，而是：

```text
删掉约 25% 工程术语
重排约 40% 内容
```

最重要的原则：

1. 先讲用户能拿什么数据，不先讲架构。
2. 按任务组织，不按 provider/module 组织。
3. 给一个明确“推荐安装方式”。
4. 第一例体现 `auto`。
5. 先教 `data/source/ok`，provenance 后置。
6. 修正 history 全源失败行为的错误描述。
7. 删除所有 R*/P1L-* 内部任务编号。
8. Architecture / Tests 放最后。

本轮建议**只改 README，不再动 mktdata 核心代码**。
