# 数据源总览：全源能力地图（2026-08-24 实测）

> 把 hithink / miniQMT / TDX / akshare(东财·同花顺·新浪·雪球·宏观) 所有源拼起来的总表。
> 统一入口：`mktdata.py`（`history` / `financial` / `valuation` / `crosscheck` / `f10`）。

## 一、数据源一览

| 源 | 通道 | 认证/环境 | 主要能力（已实测 ✅） | 被墙/缺 ❌ |
| --- | --- | --- | --- | --- |
| **hithink**（同花顺 API） | REST `fuyao.aicubes.cn` | API Key | A股日线/快照/复权因子、三表+指标、PE/PB/PS/PCF、日历、指数、概念板块目录/成分、基金26端点、涨停/龙虎/热榜/异动、全市场 Parquet | 无港股/分钟/美股 |
| **miniQMT**（迅投/国金 xtdata） | 本地 `127.0.0.1:58610` | 需终端运行 | A股+港股 日/分钟/tick、除权因子、日历、证券资料、板块成分、三表（A股）、估值自算 | 港股财务、估值直接接口 |
| **TDX**（通达信 pytdx） | 直连行情服务器（5 台实测） | 零认证 | A股日线(20年原始价)、快照价、每股净资产→PB（银行股准）、除权除息 | 港股、PE、财务三表 |
| **akshare-东财** | `datacenter/data.eastmoney.com` | 无 | 港股三大报表/指标/估值/资料/分红、A股公告、涨停池、龙虎榜、人气榜、基金净值 | `push2.eastmoney.com`（行情/板块/美股K线）被墙 |
| **akshare-同花顺** | `10jqka.com.cn` | 无 | A股财务摘要（103期）、概念板块列表(375个) | 概念成分函数缺 |
| **akshare-新浪** | `finance.sina.com.cn` | 无 | 港股日线（与 miniQMT 逐日一致）、港股实时 | 美股实时慢 |
| **akshare-雪球** | `xueqiu.com` | 无 | 基金资料 | — |
| **akshare-宏观** | 各宏观源 | 无 | 中国 GDP/CPI 等、央视新闻联播 | 个股新闻接口坏 |
| **Yahoo Finance** | `query1.finance.yahoo.com` | 无 | **美股历史行情**（日/分钟，chart 端点免费开放，0.3s） | 实时报价/财务估值(v7/v10)已 401 鉴权 |

## 二、按数据类别的全源拼图

### 行情
| 数据 | 源（已实测） | 冗余 |
| --- | --- | --- |
| A股日线 | hithink / miniQMT / **TDX** | 三源 |
| A股分钟 | miniQMT（5m/1m）+ **TDX（5m/15m/30m/60m/1m）** | 双源（已实测 5m 48/48 一致） |
| A股实时 | miniQMT tick / TDX 快照 / hithink snapshot | 三源 |
| 港股日线 | miniQMT / **新浪** | 双源 |
| **美股日线** | **Yahoo Finance**（`--source yahoo`）/ akshare `stock_us_daily` | 双源 |
| 港股分钟/实时 | miniQMT | 单源 |
| 除权除息 | hithink / miniQMT / TDX | 三源 |
| 交易日历 | hithink / miniQMT | 双源 |
| 标准指数成分 | miniQMT / TDX（沪深300/上证50/中证500） | 双源 |

### 财务
| 数据 | 源 | 冗余 |
| --- | --- | --- |
| A股三大报表 | hithink / miniQMT | 双源 |
| A股财务指标 | hithink / miniQMT 自算 | 双源 |
| A股财务摘要（复核） | **akshare-同花顺** | 第三方复核 |
| **港股三大报表/指标** | **akshare-东财** | 单源（补缺口） |
| 港股公司资料/分红 | akshare-东财 | 单源 |

### 估值
| 数据 | 源 | 冗余 |
| --- | --- | --- |
| A股 PE/PB/PS/PCF | hithink / miniQMT 自算 / **TDX(PB)** | 三源（TDX 银行股 PB 最准） |
| 港股 PE/PB | akshare-东财 | 单源（补缺口） |

### 特色/语义
| 数据 | 源 | 冗余 |
| --- | --- | --- |
| 涨停池/龙虎榜 | hithink / **akshare-东财** | 双源 |
| 人气榜/热榜 | akshare-东财 | 单源 |
| 概念板块列表 | hithink / akshare-同花顺 | 双源（**成分仍缺**） |
| A股公告 | akshare-东财 | 单源 |
| 宏观 | akshare 宏观 | 单源 |
| **沪深港通资金流** | akshare（`extra --type hsgt`） | 单源 |
| **行业板块行情排名**（90板块） | akshare-同花顺（`extra --type industry`） | 单源（轮动用） |
| **概念板块行情/题材** | akshare-同花顺（`extra --type concept`） | 单源 |
| **两融余额** | akshare（`extra --type margin`，上交所） | 单源 |

### 基金 / 其他
| 数据 | 源 | 状态 |
| --- | --- | --- |
| 基金净值/经理/资料 | akshare-东财/雪球 | ✅ 可用 |
| 基金持仓 | akshare-东财 | ❌ 接口坏 |
| 个股新闻/研报 | — | ❌ 缺（研报 hithink wenda 独有） |
| 异动分析 | — | ❌ 缺 |
| **美股** | — | ⚠️ 行情已补（Yahoo/akshare）；**估值/财务仍缺**（雅虎 v7/v10 鉴权、百度/东财被墙） |
| Level-2/盘口深度 | — | ❌ 结构性缺（无合法免费通道） |

## 三、mktdata.py 命令 ↔ 源映射（auto 全自动）

| 命令 | 来源（auto 自动切换链） | 用法示例 |
| --- | --- | --- |
| `history` | A股 hithink→miniQMT→TDX；港股 miniQMT→新浪；美股 Yahoo→新浪 | `history --codes 600519.SH,00700.HK,AAPL.US --start ... --end ...` |
| `financial` | A股 hithink→miniQMT；**港股 自动转东财 F10** | `financial --codes 600519.SH / 00700.HK` |
| `valuation` | A股 hithink→miniQMT 自算；**港股 自动转东财 F10(PE/PB)**；`--source tdx`（A股PB） | `valuation --codes 600519.SH,00700.HK` |
| `crosscheck` | hithink/miniQMT/TDX 三方 | `crosscheck --codes 600519.SH --start ... --end ...` |
| `f10` | akshare-东财（港股 F10）/同花顺（A股摘要） | `f10 --codes 00700.HK / 600519.SH` |
| `extra` | akshare（沪深港通资金/行业板块行情/概念行情/两融） | `extra --type all --start ... --end ...` |

> `--source hithink|miniqmt|tdx|sina|yahoo` 可强制单一源（对账/测试）。每行输出标注实际来源。

## 四、决策结论

1. **核心数据（行情/财务/估值）已全面覆盖且有冗余**：A股行情三源、港股行情双源、A股财务双源+第三方复核、港股财务东财补齐、估值 A股三源。
2. **仍未覆盖**：概念板块**成分**、基金持仓、个股新闻/研报、异动、**美股**、Level-2、港股深度明细（研发/分部）。
3. **网络规律**：`push2.eastmoney.com` 被墙是美股/东财板块行情拿不到的主因；财务/公告/基金走 `datacenter/data` 域名正常。
