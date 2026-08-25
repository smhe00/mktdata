# 多源能力对照与自动兜底策略（fallback）

设计原则：**hithink 优先，miniQMT 兜底，通达信/新浪/Yahoo/东财 依次补位**。
每个市场/数据类型都有自动切换链（`--source auto`），见下文"自动路由"。

## 能力对照表

| 数据需求 | hithink（同花顺） | miniQMT（本机） | 兜底结论 |
| --- | --- | --- | --- |
| A 股日线（后复权） | ✅（≤10 年窗口） | ✅ | hithink 优先，失败转 miniQMT |
| A 股快照（PE/PB/现价） | ✅ | ✅（tick 快照） | hithink 优先 |
| **港股行情（如 00700.HK）** | ❌ 不支持 | ✅ 日线+分钟线+快照 | **必走 miniQMT** |
| **分钟级 K 线（5m/1m）** | ❌ 不支持 | ✅ | **必走 miniQMT** |
| 实时/盘中快照 | 快照为准日级 | ✅ get_full_tick 实时 | 实时需求走 miniQMT |
| 分红/除权因子明细 | 仅有复权参数 | ✅ get_divid_factors | miniQMT 更细，可交叉验证 |
| 交易日历（多市场） | 未见独立接口 | ✅ get_trading_dates | 走 miniQMT |
| 财务三表/指标（利润表等） | ✅ 强项（三表+指标指标） | ✅ 三表 Income/Balance/CashFlow 已验证；**指标无现成表，由三表自算** | hithink 优先，失败转 miniQMT |
| 港股财务（腾讯利润表） | ❌ 不支持 | ❌ 无 ASHARE 财务 | **akshare 东财 F10 补位**（三表/指标/估值/分红） |
| 估值 PE/PB/PS | ✅ 强项 | ⚠️ 需自行算 | hithink 优先 |
| 指数/板块/特色数据（涨停等） | ✅ 强项 | 部分板块成分 | hithink 优先 |
| 公募基金/ETF 净值 | ✅ | ❌ | hithink 唯一 |
| 批量全市场/本地库 | ✅（DuckDB 同步） | 逐代码 | hithink 唯一 |

## hithink 失败签名（实测）

| 场景 | 返回 |
| --- | --- |
| 传港股代码 `00700.HK` | HTTP 200 + `code=1002 "Unknown thscode: 00700.HK"` |
| 传分钟 interval=5m | HTTP 200 + `code=1002 "Invalid parameter format: interval"` |
| 未知/错误代码 | HTTP 200 + `code=1002 "Unknown thscode: ..."` |
| 窗口超 10 年 | `code=1003`（start/end 最多 10 年） |
| 参数类错误 | `code=1001` |
| 鉴权失败 | `code=2001/2003` |
| 限流 | `code=4001` |
| 服务端异常 | `code=5xxx`；或网络层异常（TLS/超时） |

**判定"hithink 失败"**：HTTP 非 200 / 业务码非 0 / 数据为空 / 网络异常。能力边界（1001/1002）
无需重试，直接转 miniQMT；限流/网络/服务端错误可重试或转 miniQMT。

## 自动路由（`--source auto`，2026-08 全自动版）

统一入口，输出统一格式（date,open,high,low,close,volume,amount）：

```powershell
& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' 'D:\gitee\miniqmt-skill\scripts\mktdata.py' history `
  --codes 00700.HK,600519.SH,AAPL.US --start 20240101 --end 20260824 --adjust back --outdir .\out
```

| 市场 | 数据 | 自动切换链（依次兜底） |
| --- | --- | --- |
| A 股 | 日线 | hithink → miniQMT → TDX(pytdx) |
| A 股 | 分钟(1m/5m/15m/30m/60m) | miniQMT → TDX(pytdx)（双源，已实测 5m 48/48 一致） |
| 港股 | 日线 | miniQMT → 新浪(akshare) |
| 美股 | 日线 | Yahoo 直连 → 新浪(akshare) |
| A 股 | 财务/估值 | hithink → miniQMT 自算 |
| 港股 | 财务 | akshare 东财 F10（三表/指标/资料/分红） |
| 港股 | 估值 | akshare 东财 F10（PE/PB） |

- 每代码一行标出**实际来源**（`hithink` / `miniqmt` / `tdx` / `sina` / `yahoo` / `akshare东财` 及 `xxx(fallback:...)`），便于确认走了哪条路。
- `--source hithink|miniqmt|tdx|sina|yahoo`：强制只用单一源（不兜底，用于对账/测试）。
- `crosscheck`：hithink/miniQMT/TDX 三方收盘+PB 一致性一键对账。
- `f10`：港股(东财)财务/估值/资料/分红 + A股(同花顺)财务摘要。

## 财务兜底：mktdata.py financial（仅 A 股，三表）

```powershell
& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' 'D:\gitee\miniqmt-skill\scripts\mktdata.py' financial `
  --codes 600519.SH,601318.SH --statement all --period annual --limit 3
```

- `--statement income|balance|cashflow|indicators|all`：三表 + 财务指标（默认 income；`all` 四块一起）。
- **指标（indicators）**：hithink 走 `/financials/indicators`（`--report 2025-4`，缺省自动取最新年报期）；**miniQMT 没有现成指标表，兜底用三张原始报表自算核心指标**（营收同比/归母同比/净利率/ROE/负债率/流动比率/经营现金占营收），源码注释标明了每项口径。
- 路由：A 股 → hithink 优先，失败 → miniQMT 兜底；`--source miniqmt` 可强制。
- **港股财务（如腾讯）**：hithink/miniQMT/TDX 均不支持，**auto 自动转 akshare 东财 F10**（指标估值 PE/PB/净利/营收/ROE + 三大报表 + 公司资料 + 分红），不再报"不支持"。
- **跨源一致性（已实测）**：
  - **资产负债表**：`assets_total/total_debt/holder_equity_total`（hithink）↔ `tot_assets/tot_liab/total_equity`（miniQMT），**两源逐位一致**（茅台 FY2025 总资产 3038.35 亿 / 负债 498.76 亿 / 净资产 2539.59 亿）。
  - **现金流量表**：`act/invest/financing_cash_flow_net`（hithink）↔ `net_cash_flows_oper/inv/fnc_act`（miniQMT），**两源逐位一致**（茅台 FY2025 经营 615.22 亿 / 投资 −316.42 亿 / 筹资 −734.27 亿）。
  - **利润表**：`operating_income`（营业收入）vs `revenue`（营业总收入）差约 2%；归母净利 `parent_holder_net_profit` = `net_profit_excl_min_int_inc` **一致**。
  - **指标（茅台 FY2025，hithink vs 自算）**：归母同比 −4.53% = −4.53%、负债率 16.42 = 16.42、流动比率 5.09 = 5.09、营收同比 −1.21 ≈ −1.20、ROE 32.53 ≈ 32.41（hithink 用加权平均，自算用期末净资产）均高度一致；**净利率/经营现金占营收有 ~3pp 口径差**（营业总收入 vs 营业收入）；**毛利率 miniQMT 算不了（无可靠营业成本字段），标 —**。保险/银行等金融股 ROE/净利率口径差更大，以 hithink 为准。
- `--period quarterly` 可用（hithink 单季度口径）。

## 兜底注意事项

- **复权口径对齐**：hithink 的 `backward/forward` ↔ miniQMT 的 `back/front`，脚本已映射。
- **时间戳**：hithink 为毫秒（北京 0 点），miniQMT 日线索引 `YYYYMMDD`、分钟线 `YYYYMMDDHHMMSS`——脚本已统一。
- **币种**：港股港币 / A 股人民币，跨市场组合需注明未做汇率折算。
- **回购**：两个来源的后复权都不含回购注销（无除权因子），不要硬加回购收益率到历史回报。
- **只读**：mktdata 与 qmt.py 均只取数，不含交易。
