# 封板记录（STATUS）

> **封板日期**：2026-08-24
> **状态**：✅ 已封板（v1.0 稳定版）——全量回归 **33/33 通过**，多源自动路由、全部子命令可用。

## 最终能力

### 6 个子命令 × 9 个数据源（全自动路由）

| 子命令 | 覆盖 | 自动切换链 |
| --- | --- | --- |
| `history` | 行情 | A股日线 hithink→miniQMT→TDX；A股分钟 miniQMT→TDX；港股 miniQMT→新浪；美股 Yahoo→新浪 |
| `financial` | 财务 | A股 hithink→miniQMT；港股 东财F10 |
| `valuation` | 估值 | A股 hithink→miniQMT自算→TDX(PB)；港股 东财F10 |
| `crosscheck` | 对账 | hithink/miniQMT/TDX 三方收盘+PB |
| `f10` | 基本面 | 港股东财(指标/三表/资料/分红)；A股同花顺摘要 |
| `extra` | 量化辅助 | 沪深港通资金/行业板块行情/概念行情/两融 |

### 数据源（9）
hithink(同花顺API) / miniQMT(本机xtdata) / TDX(easy-tdx) / akshare-东财 / akshare-同花顺 / akshare-新浪 / akshare-雪球 / akshare-宏观 / Yahoo直连

### 全量回归（33 项，`scripts/test_all.py` 可重跑）
行情 10 ✓ 跨源一致性 3 ✓（A股日线/5m/港股 三方逐点一致）财务 7 ✓ 估值 4 ✓（PB 三源一致）F10/extra 5 ✓ CLI 4 ✓

## 关键口径
- 复权：`back`=后复权（含分红送转，不含回购）；跨源已对齐（hithink backward ↔ miniQMT back）
- 财报重述：miniQMT 同报告期取 `m_anntime` 最新版（`_dedup_latest_announce`）
- PB 分母：归母净资产（TDX 每股净资产口径，银行股与 hithink 一致）
- 港股财务：东财（hithink/miniQMT/TDX 均无）

## 已知边界（如实，不假装）
- **全部源都没有**：美股估值/财务、Level-2/盘口、基金持仓
- **仅 hithink 独有**：概念板块成分、研报、个股新闻、异动分析、基金26端点（hithink 挂了即无）
- **被墙/接口坏**：东财 push2（美股行情/板块/资金流）、深交所两融当日、业绩预告、个股新闻(akshare)
- **单源**：港股财务(东财)、沪深港通资金、板块行情、两融、公告、宏观、美股(行情双源但财务无)

## 使用
```powershell
# 本机 CLI（已封装，任意目录可直接用）：
mktdata --help                    # 多源数据入口（6 子命令，全自动路由）
mktdata history --codes 00700.HK,600519.SH,AAPL.US --start 20240101 --end 20260824
qmt --help                        # 单源查询入口（7 子命令）
# 全量回归
& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' 'D:\gitee\miniqmt-skill\scripts\test_all.py'
```
- CLI 包装：`C:\Users\peter\AppData\Local\Python\bin\mktdata.cmd` / `qmt.cmd`（已在 PATH）
- 下一步（可选）：把 mktdata 包成 MCP server（stdio / streamable-http），供 MCP 客户端调用

## 文档导航
- `sources.md` — 全源能力地图（9 源拼图）
- `fallback.md` — 自动路由表 + 失败签名
- `coverage.md` — hithink 59 端点逐项矩阵 + tdx/akshare 源
- `commands.md` / `setup.md` — 参数与避错
