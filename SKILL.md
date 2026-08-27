---
name: miniqmt
description: 当用户或 Agent 需要通过本机 miniQMT（迅投/国金 QMT，xtquant/xtdata）获取、查询、导出 A 股或港股行情（历史 K 线、最新快照、分红除权因子、交易日历、证券资料、板块成分）时使用。也适用于"用 QMT/miniQMT 查数据""本地行情库""腾讯 00700.HK 历史"等场景。只读数据查询，不涉及交易。
---

# miniQMT 数据查询

> **本机 CLI 已封装**：任何目录下可直接用 `mktdata`（多源入口）与 `qmt`（单源入口）两个命令，
> 等价于 `& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' '<skill>\scripts\mktdata.py' ...`。
> 包装在 `C:\Users\peter\AppData\Local\Python\bin\`（已在 PATH）。

本机 **miniQMT 数据服务**（xtquant/xtdata，默认 `127.0.0.1:58610`）的只读数据查询入口。它是本机实时/历史行情源，**支持 A 股与港股**，是 hithink（同花顺）之外补充港股行情的唯一本地通道。例如"腾讯 00700.HK 历史"必须走这里，同花顺不支持港股。

## 三数据源策略：hithink 优先，miniQMT 兜底，通达信(tdx)第三方冗余

A 股日线等 hithink 支持的需求**优先走 hithink**；hithink 不支持（港股、分钟线、实时）或调用失败时**自动转 miniQMT 兜底**。此外 mktdata.py 还支持：
- **通达信 easy-tdx 第三源**（`--source tdx`，零认证直连通达信服务器，全面替代 pytdx）做 A 股行情/PB/资金流向三方交叉；
- **新浪港股源**（`--source sina`，akshare `stock_hk_daily`，港股日线与 miniQMT 逐日一致）；
- **F10 基本面**（`f10` 子命令）：港股财务/估值/公司资料/分红（akshare 东财）+ A股财务摘要（同花顺）——**港股财务由此补上**（hithink/miniQMT/TDX 三源本无港股财务）。

一键入口：

```powershell
& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' 'D:\gitee\miniqmt-skill\scripts\mktdata.py' history `
  --codes 00700.HK,600519.SH,601318.SH --start 20240101 --end 20260824 --adjust back --outdir .\out

# 港股第二行情源 / 港股F10财务：
& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' 'D:\gitee\miniqmt-skill\scripts\mktdata.py' history --codes 00700.HK --source sina --start 20260801 --end 20260824
& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' 'D:\gitee\miniqmt-skill\scripts\mktdata.py' f10 --codes 00700.HK
```

路由规则、hithink 失败签名与能力对照详见 `references/fallback.md`；tdx 源能力与验证详见 `references/coverage.md`。也可直接调 `qmt.py`（单源、更多子命令）。

## 前置条件（使用前先确认）

1. **miniQMT 终端在运行**：存在 `XtMiniQmt` 与 `miniquote` 进程（本机：`D:\国金证券QMT交易端` 实盘端 / `D:\国金QMT交易端模拟` 模拟端）。
2. **xtquant 已安装**：必须用 miniQMT 项目的 venv Python 运行脚本：
   - Python：`D:\gitee\miniQMT\.venv\Scripts\python.exe`
   - 技能脚本：`D:\gitee\miniqmt-skill\scripts\qmt.py`
3. 数据服务端口 `127.0.0.1:58610` 由终端自动提供；脚本 `connect` 即可自检。

## 直接描述需求

允许自然语言开始，不需要用户提供技术参数。例如：

- "查一下腾讯 00700 今天的最新价。"
- "导出腾讯近 5 年后复权日线到 CSV。"
- "中国平安和腾讯过去一年的走势对比。"
- "查腾讯 2024 年以来有几次分红、每股派多少。"
- "本周港股有哪些交易日？"
- "上证 50 有哪些成分股？"

先把自然语言转换成具体的数据任务（标的、区间、复权口径），再用 `qmt.py` 取数。

## 任务与命令路由

| 用户意图 | 子命令 | 关键参数 |
| --- | --- | --- |
| 连接自检 / 数据目录 | `connect` | — |
| 历史 K 线（日/分钟） | `history` | `--code --period --start --end --adjust --csv/--json` |
| 最新快照（现价/量额） | `quote` | `--code 00700.HK 600519.SH`（可多只） |
| 分红/送转/除权因子 | `dividends` | `--code --start --end` |
| 证券基础资料 | `instrument` | `--code` |
| 交易日历 | `calendar` | `--market SH/SZ/HK --start --end` |
| 板块成分 | `sector` | `--name`（如 `上证50`） |

## 接入方式

所有查询统一走：

```powershell
& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' 'D:\gitee\miniqmt-skill\scripts\qmt.py' <子命令> ...
```

历史数据流程（脚本内部已封装）：`download_history_data` → `get_market_data_ex`。时间参数用 `YYYYMMDD`。

## 关键口径与避错要点

- **代码格式**：A 股 `600519.SH` / `000858.SZ`；**港股必须 5 位补零**，如腾讯 = `00700.HK`（`0700.HK` 无效）。用 `instrument` 可验证代码是否有效。
- **复权** `--adjust`：`none`=不复权（真实成交价）；`front`=前复权（最近价对齐）；`back`=后复权（早期价对齐，**含现金分红与拆股送转**，适合算总回报 CAGR）。
- **回购注销无法通过复权捕获**：回购没有"除权日/复权因子"。后复权回报是"每股已实现回报（价格+分红）"，回购对股价的影响已内含在市场定价中，**不要**把"回购收益率"直接加回历史价格回报（会重复计算）。如需单独说明腾讯回购规模，用 web 信息，别从行情序列硬加。
- **时间戳**：`get_market_data_ex` 索引为 `YYYYMMDD` 整数；`get_full_tick`/`get_trading_dates` 为毫秒（北京时间 UTC+8）。脚本已统一转换。
- **分钟级**：`--period 5m/1m` 可用，但窗口与数据量受限；日线最稳。
- **只读**：仅取数，不包含下单/交易接口。
- **币种**：港股以港币计，A 股以人民币计；跨市场组合需自行注明未做汇率折算。

## 输出要求

每次给出数据回答时注明：数据源（本机 miniQMT/xtdata）、时间窗口、复权口径；大结果（如多年日线）落盘到文件并给出路径；涉及投资结论一律标注"非投资建议"。

## 参考

- `references/setup.md` — 环境、连接、代码格式与常见坑
- `references/commands.md` — 每个子命令的完整参数与示例输出
- `references/fallback.md` — hithink ↔ miniQMT 能力对照、失败签名与自动兜底策略
- `references/coverage.md` — **hithink 59 端点逐项兜底覆盖矩阵**（哪些能兜、哪些不能、缺口清单）
- `references/sources.md` — **全源能力地图**（hithink/miniQMT/TDX/akshare 各源拼图、命令↔源映射）
- `references/STATUS.md` — **封板记录**（v1.0 稳定版，33/33 全量回归通过、能力/边界清单）

## 回归测试

`scripts/test_all.py` 全量回归（6 子命令 × 全部源 + 跨源一致性，33 项）：

```powershell
& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' 'D:\gitee\miniqmt-skill\scripts\test_all.py'
```
