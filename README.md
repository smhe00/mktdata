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

## 前置条件（环境相关，非仓库内容）

- **Python 3.12 venv**：`D:\gitee\miniQMT\.venv`（含 xtquant、pytdx、akshare、arcticdb）
- **miniQMT 终端运行**（`127.0.0.1:58610`）：A股/港股行情主源
- **hithink API Key**（`%APPDATA%\hithink-finance\credentials.env`）：A股行情/财务主源
- 网络可达：通达信行情服务器、Yahoo、新浪、东财 datacenter、同花顺 10jqka

## 本机 CLI（已封装，任意目录可用）

```powershell
mktdata history --codes 00700.HK,600519.SH,AAPL.US --start 20240101 --end 20260824
mktdata f10 --codes 00700.HK          # 港股 F10（财务/估值/资料/分红）
mktdata extra --type all              # 量化辅助（资金流/板块/两融）
qmt connect                           # 单源自检
```

等价长命令：`& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' '<此仓库>\scripts\mktdata.py' ...`
CLI 包装：`C:\Users\peter\AppData\Local\Python\bin\mktdata.cmd` / `qmt.cmd`

## Agent 技能挂载

`C:\Users\peter\.agents\skills\miniqmt` 是一个 **junction**，指向本仓库 `D:\gitee\miniqmt-skill`——
技能目录路径不变（Agent 自动发现不受影响），文件实体在本仓库（可 git 管理、独立推送 GitHub）。

## 回归测试

```powershell
& 'D:\gitee\miniQMT\.venv\Scripts\python.exe' 'scripts\test_all.py'
```

## 数据源（9 个）

hithink(同花顺API) / miniQMT(本机xtdata) / TDX(通达信pytdx) / akshare-东财 / akshare-同花顺 /
akshare-新浪 / akshare-雪球 / akshare-宏观 / Yahoo直连

详见 `references/sources.md`。
