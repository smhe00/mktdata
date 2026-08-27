# hithink 59 端点 → miniQMT 兜底覆盖矩阵

> 逐端点审计（对照 hithink-finance `api/capability-map.md` 的 59 个端点，实测结论截止 2026-08-24）。
> 结论：**15/59 完全可兜底、5/59 部分可兜底（含估值自算）、39/59 无法兜底**。
> 其中 26 个基金 + 11 个特色数据端点属于「数据源本质不同」（miniQMT 是行情终端，不是基金/财经数据库），
> 把这两类剔除后，**行情/财务/估值/指数/日历类 22 个端点里 20 个可兜底（91%）**，真缺口只剩 2 个。

## ✅ 完全可兜底（15）——已实测

| hithink 端点 | miniQMT 等价 | 备注 |
| --- | --- | --- |
| `meta/tickers/list`（代码表） | `get_stock_list_in_sector('沪深A股')` | 5213 只实测 |
| `prices/snapshot`（最新快照） | `get_full_tick` / tick 行情 | A 股+港股 |
| `prices/historical`（日 K） | `get_market_data_ex(period='1d')` | 支持前/后复权；A 股+港股（已验证） |
| `corporate-actions/adjustment-factors`（分红送股事件） | `get_divid_factors` | 除权因子流（已验证） |
| `financials/income-statements` | `get_financial_data('Income')` | A 股；归母净利两源逐位一致（已验证） |
| `financials/balance-sheets` | `get_financial_data('Balance')` | A 股；三字段逐位一致（已验证） |
| `financials/cash-flow-statements` | `get_financial_data('CashFlow')` | A 股；三字段逐位一致（已验证） |
| `calendar/trading-days` | `get_trading_dates` | 多市场（已验证） |
| `index/prices/snapshot`（指数/板块行情） | 指数 tick / 日线 | 000300.SH 实测可查 |
| `index/prices/historical`（指数 K 线） | `get_market_data_ex(指数代码)` | 000300.SH 日线实测 |
| `fund/market/snapshot`（ETF/LOF 场内快照） | ETF tick | 510300.SH 实测可查 |
| `fund/market/historical`（ETF 日线） | `get_market_data_ex(基金代码)` | 510300.SH 日线实测 |
| `dump/daily-k`（全市场日 K Parquet） | 本机全市场库 + 批量拉取 | 5213 只本地可拉，无需逐股 HTTP |
| `dump/daily-k-10d`（近 10 日增量） | 本机每日增量数据 | 同上 |
| `dump/adjustment-factors`（全市场复权因子） | 全市场 `get_divid_factors` | 同上 |

## ⚠️ 部分可兜底（5）——有条件

| hithink 端点 | miniQMT 情况 | 缺口 |
| --- | --- | --- |
| `meta/tickers/search`（名称/代码检索消歧） | `get_instrument_detail` 按代码查资料 | **不能按名称模糊搜索**，只能按已知代码 |
| `financials/indicators`（五类财务指标） | 由三表自算核心指标（mktdata `financial --statement indicators`） | 毛利率算不了；净利率/ROE 有口径差；**仅 A 股** |
| `valuations/snapshot`（PE/PB/PS/PCF） | 由 最新价×总股本 / TTM财报 自算（mktdata `valuation`） | 详见下方"估值自算"精度表；**仅 A 股** |
| `auction/snapshot`（集合竞价快照） | 原生 tick（含竞价时段）可近似 | 无「竞价快照」语义封装，需自己拼 |
| `index/constituents`（板块/指数成分） | `get_stock_list_in_sector('沪深300')` 等 | **标准指数成分✅**（沪深300/上证50/中证500 实测）；**同花顺概念/行业板块成分❌** |

### 估值自算精度（miniQMT 计算 vs hithink，2026-08-24 实测，PB 已修复）

| 股票 | PE_ttm | PS_ttm | PCF_ttm | PB | 备注 |
| --- | --- | --- | --- | --- | --- |
| 600519.SH 茅台 | 20.03 = 20.03 ✅ | 9.41 = 9.41 ✅ | 13.69 = 13.69 ✅ | **6.491 = 6.491 ✅** | 全对得上 |
| 000858.SZ 五粮液 | 22.02 = 22.02 ✅ | 5.995 = 5.995 ✅ | 24.51 = 24.51 ✅ | **2.168 = 2.168 ✅** | 重述后一致 |
| 601318.SH 平安 | 6.16≈6.24 | 0.87≈0.90 | 1.43≈1.44 | **0.955≈0.967 ✅**（原 0.69） | PB 已修复 |
| 000333.SZ 美的 | 14.81≈14.84 | 1.42≈1.52 | 12.22≈12.25 | **2.82≈2.82 ✅** | |
| 600036.SH 招行 | 6.62 = 6.62 ✅ | 2.93≈3.32 | 2.07 = 2.07 ✅ | 0.778 vs 0.882 ⚠️ | 银行 PB 仍差 ~12% |

- **PE/PS/PCF 用 TTM**（最近年报 + 最新报告期 − 上年同期归母净利/营收/经营现金流），多数与 hithink **逐位一致**。
- **PB 分母必须用归母净资产 `tot_shrhldr_eqy_excl_min_int`**（剔除少数股东权益，最新报告期优先、年报兜底），**不能用 `total_equity` 总权益**——这是平安 PB 对不准的根因（总权益 14160 亿 vs 归母 10281 亿，差的是平安银行并表的少数股东权益 ~4000 亿）。修复后平安 0.955≈0.967。
- **银行 PB 残留差**（招行 0.778 vs 0.882）：银行归母净资产含**永续债/其他权益工具**（招行 ~1500 亿，12824−1500≈11318 ≈ hithink 隐含），miniQMT 无单独剔除字段，此口径差暂不可消除。
- `pe_mrq` 我按"最近完整年报"口径，hithink 的 MRQ 定义不透明（逐只都不对齐），**跨源对比一律以 PE_ttm 为准**。
- **财报重述处理（重要）**：miniQMT 同一报告期可能出现两行（如五粮液 2025 各季：旧版 148.6/194.9/215.1 亿 + 重述版 44.2/46.2/64.7 亿），必须按 `m_anntime`（公告日）**取最新**，否则估值/指标会错（五粮液 PE 会算成 129 而非 22）。`mktdata.py` 已内置 `_dedup_latest_announce` 去重。

## ❌ 无法兜底（39）——只能靠 hithink

### 真缺口（行情类数据源做不了，只剩 2 个）
| hithink 端点 | 缺口 |
| --- | --- |
| `auction/short-term-benchmark` | 集合竞价**短期强弱基准**（竞价涨幅排名） |
| `index/catalog/ths-index-list` | 同花顺**概念/区域/特色/行业指数目录** |

### 基金非场内行情（26 个）
`fund/profile/detail`、`portfolio/holdings`、`performance/nav`、`performance/returns`、`holders/detail`、`companies/detail`、`portfolio/industry-allocation`、`performance/indicators-historical`、`performance/drawdowns`、`holders/top`、`corporate-actions/dividends`、`diagnostics/detail`、`financials/indicators`、`financials/income-statements`、`financials/balance-sheets`、`managers/*`（4）、`news/article-list`、`offerings/list`、`portfolio/stock-history`、`portfolio/stock-report-dates`、`portfolio/bond-history`、`portfolio/bond-report-dates`、`portfolio/asset-allocation`

> miniQMT 只覆盖基金**场内行情**（上表 ✅ 的 2 个），不提供基金资料/持仓/经理/净值历史/收益/资讯。

### 特色数据（11 个）
`special-data/limit-up-pool`、`limit-down-pool`、`limit-break-pool`、`limit-up-ladder`、`anomaly-analysis-list`、`anomaly-analysis-stock`、`skyrocket-list`、`hot-stock-list`、`hot-stock-list-history`、`hot-stock-rank-trend`、`dragon-tiger-list`

> 涨停池/跌停池/炸板/连板/异动/飙升/热榜/龙虎榜——miniQMT 只有原始 tick，无这些语义池。

## 反向：miniQMT 有而 hithink 没有的（兜底之外的增量）

| 能力 | 说明 |
| --- | --- |
| **港股行情** | hithink 完全不支持；miniQMT A 股+港股日线/分钟/tick |
| **分钟 K / tick / 近似 L2** | hithink 仅日级；miniQMT 1m/5m/日/周/月 + 逐笔 tick |
| **实时快照** | hithink 准日级；miniQMT `get_full_tick` 实时五档 |
| **本地全市场库** | 5213 只 A 股本地直查，不耗远端配额、无逐股 HTTP |
| **港股财务** | ⚠️ 注意：**港股财务两源都没有**（见 fallback.md） |

## 通达信 easy-tdx 第三源（零认证，`--source tdx`）

> mktdata.py 额外支持**通达信 easy-tdx**（`pip install easy-tdx`，2026-08 已装 venv，全面替代 pytdx）作为独立第三方冗余。
> 直连通达信行情服务器（实测 5 台可用），不依赖 WorkBuddy MCP（其认证墙见下），全自动。

| 能力 | 状态（已实测） |
| --- | --- |
| **A 股日线（原始价）** | ✅ 20 年全历史翻页可拉；与 miniQMT none-adjust **逐日一致**（20/20 天精确） |
| **A 股分钟线**（1m/5m/15m/30m/60m） | ✅ 5m 与 miniQMT **48/48 时间点一致**（双源） |
| **历史资金流向**（主力/超大/大/中/小单） | ✅ `get_history_fund_flow`（茅台 8-26 主力 +4.47 亿）——easy-tdx 独有，补东财 push2 被墙的缺口 |
| **最新收盘** | ✅ 13 只与 hithink/miniQMT **三方逐只一致** |
| **PB**（最新价/每股净资产） | ✅ 与 hithink **13/13 一致**（茅台 6.491、招行 0.882、平安 0.967、比亚迪 3.564）——连银行/少数股东权益股都对齐，**比 miniQMT 自算还准** |
| 除权除息事件流 | ✅ `get_xdxr_info`（茅台 45 条） |
| 快照价格/量额 | ✅ vol 单位=手，与 miniQMT 一致；amount=元 |
| **PE/PS/PCF** | ❌ 快照 PE 字段为空、finance_info 净利字段单位有坑——tdx 源只出 PB，其余置 None |
| **港股** | ❌ 这台服务器 ExHq 扩展行情不支持（超时）；港股仍走 miniQMT |
| 财务三表 | ❌ 无（只有 finance_info 简表） |

用法：`history --codes 600519.SH --source tdx --adjust none` / `valuation --codes 600519.SH --source tdx`。
三方对账结论（13 只）：**收盘价 13/13 一致；PB 用 tdx/hithink 对 13/13 一致**（miniQMT 自算在招行/比亚迪有 ~0.1 偏差，tdx 与 hithink 相同）。

## akshare 公开源：新浪港股双源 + F10 基本面（补港股财务缺口）

> 除 hithink/miniQMT/TDX 外，mktdata.py 还接入 **akshare 公开接口**（新浪/东财/同花顺网页），
> 主要解决**港股财务缺口**与**港股行情双源**。已实测（2026-08-24）：

| 能力 | 接口（akshare） | 实测结果 |
| --- | --- | --- |
| **港股历史日线** | `stock_hk_daily` | 腾讯 5457 天；与 miniQMT **10/10 天逐日精确一致**（440.00=440.00） |
| **港股财务指标+估值** | `stock_hk_financial_indicator_em` | 腾讯 PE 15.01 / PB 3.06 / 净利 1141亿 / 营收 4012亿 / ROE 9.97% / 市值 4.005万亿 / 股息率 1.21% |
| **港股公司资料** | `stock_hk_company_profile_em` | 腾讯控股/注册地/行业/董事长/简介 |
| **港股分红历史** | `stock_hk_dividend_payout_em` | 腾讯 2025年度每股派 5.3 港元（2024→4.5、2023→3.4） |
| **A股财务摘要** | `stock_financial_abstract_ths` | 茅台 103 期：净利/ROE/毛利率/负债率/流动比率（同花顺网页，可复核 hithink） |

- 用法：`history --codes 00700.HK --source sina`；`f10 --codes 00700.HK / 600519.SH`。
- **意义**：港股财务（含腾讯）从"三源全无"变为**可用**；港股行情从单源变为 miniQMT+新浪双源。
- **边界**：港股三大报表接口 `stock_financial_hk_report_em` 当前返回空（代码格式未试通）；港股深度明细（分部收入/研发）暂无。

## 兜底策略总结

1. **auto 路由**（已实现于 mktdata.py `history`/`financial`/`valuation`）：A 股日线/财务/估值 → hithink 优先、失败转 miniQMT（估值/指标/三表由原始数据自算）；港股/分钟 → 直接 miniQMT。
2. **估值、竞价基准、概念板块目录、基金资料、特色数据** → 竞价基准/概念目录只能走 hithink；**估值已可自算兜底**；基金资料/特色数据属数据源本质差异，**不兜底也不假装**（hithink 挂了就是挂了，如实报告）。
3. **财报重述去重**：miniQMT 财务自算必须按 `m_anntime` 取最新版（见"估值自算精度"），mktdata.py 已内置。
