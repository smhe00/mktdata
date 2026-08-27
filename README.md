# miniqmt-skill — miniQMT 多源数据查询技能

> 本机 miniQMT（迅投/国金 xtquant/xtdata）**多源数据查询**技能包：hithink 优先、miniQMT 兜底，
> 通达信/新浪/Yahoo/东财依次补位，全自动路由。已封板 v1.0（33/33 回归通过）。

## 结构

```
miniqmt-skill/
├── SKILL.md                  # 技能主入口（Agent 说明书）
├── references/
│   ├── STATUS.md             # 封板记录（v1.0，能力/边界清单）
│   ├── sources.md            # 全源能力地图（9 源拼图）
│   ├── fallback.md           # 自动路由表 + 失败签名
│   ├── coverage.md           # hithink 59 端点逐项矩阵
│   ├── commands.md / setup.md
└── scripts/
    ├── mktdata.py            # 6 子命令 × 9 源，全自动路由
    ├── qmt.py                # 单源查询（7 子命令）
    └── test_all.py           # 全量回归（33 项）
```

## 依赖关系（重点）

### 核心结论
- **仓库代码自包含**：`mktdata.py`/`qmt.py` 只用 Python **标准库**（urllib/json/argparse 等），
  **不依赖同花顺 skill**——对 hithink 是**直接 REST 调用**（`fuyao.aicubes.cn`），只用它的 **API Key**。
- `xtquant` / `easy-tdx` / `akshare` 均为**函数内惰性导入**：缺失时该数据源报错/降级，不影响其它源、不影响模块启动。
- 缺哪个源 → 自动路由跳过/降级到替代源，**不会崩**。

### 每个数据源的依赖

| 数据源 | 需要什么 | 缺了会怎样 |
| --- | --- | --- |
| **hithink** | API Key（`%APPDATA%\hithink-finance\credentials.env`）+ 网络 `fuyao.aicubes.cn` | 丢 hithink 独有：概念板块成分、研报、个股新闻、异动、基金26端点；A股行情/财务由 miniQMT/TDX/东财顶 |
| **miniQMT** | miniQMT 终端运行（`127.0.0.1:58610`）+ `xtquant` 包 | 丢 A股财务双源之一、A股分钟双源之一、港股行情主源 |
| **TDX(通达信)** | `easy-tdx` 包 + 网络可达通达信行情服务器（默认 5 台） | 丢 A股行情/PB 第三源 |
| **akshare(东财/同花顺/新浪/雪球/宏观)** | `akshare` 包 + 网络可达对应域名 | 丢 港股财务F10、A股摘要、公告、涨停/龙虎、资金流/板块/两融 |
| **Yahoo(美股)** | 网络 `query1.finance.yahoo.com` | 丢 美股行情 |

### 新机器最小启动（按需取舍）

| 场景 | 必装 |
| --- | --- |
| 只要行情多源 | Python + `easy-tdx` + `akshare`（+ 网络）→ TDX/新浪/Yahoo/东财 即可 |
| + A股/港股行情主源 | 装 **miniQMT 终端** + venv 里 `xtquant` |
| + hithink 财务/特色 | 配 **hithink API Key** |
| 一键跑回归 | venv 装 `easy-tdx akshare pandas`（`test_all.py` 里 `PY` 改本机 venv 路径） |

> 注：`test_all.py` 与 `mktdata.cmd`/`qmt.cmd` 里硬编码了本机 venv 路径，新机器按上表改路径即可。

## 本机 CLI（已封装，任意目录可用）

```powershell
mktdata history --codes 00700.HK,600519.SH,AAPL.US --start 20240101 --end 20260824
mktdata f10 --codes 00700.HK          # 港股 F10（财务/估值/资料/分红）
mktdata extra --type all              # 量化辅助（资金流/板块/两融）
qmt connect                           # 单源自检
```

等价长命令：`& '<venv-python>' '<此仓库>\scripts\mktdata.py' ...`
CLI 包装：`<bin-dir>\mktdata.cmd` / `qmt.cmd`

## Agent 技能挂载

`<agent-skill-dir>\miniqmt` 是一个 **junction**，指向本仓库 `<repo>`——
技能目录路径不变（Agent 自动发现不受影响），文件实体在本仓库（可 git 管理、独立推送 GitHub）。

## 回归测试

```powershell
& '<venv-python>' 'scripts\test_all.py'
```

## 数据源（9 个）

hithink(同花顺API) / miniQMT(本机xtdata) / TDX(通达信easy-tdx) / akshare-东财 / akshare-同花顺 /
akshare-新浪 / akshare-雪球 / akshare-宏观 / Yahoo直连

详见 `references/sources.md`。
