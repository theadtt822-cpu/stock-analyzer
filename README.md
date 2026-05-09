# StockHolmes 🕵️‍♂️ — AI 股市分析系统

混迹 K 线的福尔摩斯。A股技术分析、交互式持仓仪表盘、定时报告推送。

## 功能概览

### 📊 交互式持仓仪表盘（端口 8082）
- **天天（老板）**: http://47.116.23.182:8082/tiantian/
- **波波**: http://47.116.23.182:8082/bobo/
- 实时行情刷新（腾讯API）
- 增删改持仓、自选股管理
- StockHolmes 规则 + AI 双版本操作建议
- 个股分析报告自动生成

### 🖥️ 静态报告中心（端口 8081）
- **天天**: http://47.116.23.182:8081/tiantian_reports_8k3m/
- **波波**: http://47.116.23.182:8081/bobo_reports_9x7n/
- 每天定时报告归档
- 个股/自选/仪表盘报告统一展示

### 📅 定时报告（交易日自动）
| 时间 | 报告 | 脚本 |
|------|------|------|
| 08:30 | **财经日报**（A股开盘前必读） | `daily_scheduler.py` |
| 09:25 | **早盘荐股**（MX智能选股） | `morning_pick.py` |
| 11:35 | **午间复盘** | `midday_report.py` |
| 15:30 | **收盘复盘** | `daily_scheduler.py` |

> 定时报告同时推送给天天和波波，各自归档到独立目录。

### 📈 个股分析
- `batch_analyze.py` — 批量分析（支持多只股票代码）
- `watchlist_analyze.py` — 自选股分析（带双评分体系）
- `gen_dashboard_v2.py` — 持仓仪表盘数据生成

### 🧰 辅助工具
- `capital_flow.py` — 资本流数据（尾盘主力净额/全天主力排名）
- `yaogu_alert.py` — 妖股进场信号实时监控（交易日多时段轮询）
- `fetch_kline_tencent.py` — K线数据获取（腾讯API）

## 项目结构

```
daily_stock_analysis/
├── dashboard_server.py          # 交互式仪表盘服务（端口8082）
├── report_server.py             # 静态报告服务（端口8081）
├── gen_dashboard_v2.py          # 持仓仪表盘数据生成器
├── daily_scheduler.py           # 定时调度器（APScheduler）
├── batch_analyze.py             # 批量个股分析
├── watchlist_analyze.py         # 自选股分析
├── midday_report.py             # 午间复盘
├── morning_pick.py              # 早盘荐股
├── capital_flow.py              # 资本流模块
├── fetch_kline_tencent.py       # 腾讯API K线获取
├── yaogu_alert.py               # 妖股信号监控
├── yaogu_monitor.py             # 妖股监控辅助
├── trailing_stop.py             # 尾盘止损策略
│
├── templates/
│   ├── dashboard_v2.html        # 交互式仪表盘前端模板 ⚠️ 当前修复中
│   ├── dashboard.html           # 旧版仪表盘模板
│   └── kol_tracker.html         # KOL追踪模板
│
├── output/
│   ├── boss/                    # 天天（老板）的报告
│   └── boyfriend/               # 波波的报告
│
├── src/
│   ├── api/                     # 行情数据接口（Tencent API）
│   ├── analysis/                # 技术分析、报告生成
│   └── ...
│
├── TODO.md                      # Claude Code 修复清单
└── README.md
```

## 数据源

| 用途 | 数据源 | 状态 |
|------|--------|------|
| 实时行情/日K线 | 腾讯API (qt.gtimg.cn) | ✅ 稳定 |
| 选股/板块/资金流 | MX妙想（东方财富） | ✅ 稳定 |
| 资本流 | mx-xuangu skill | ✅ 稳定 |
| K线技术指标 | 腾讯API | ✅ 稳定 |
| AKShare | 东方财富 push2his | ❌ 不可用（空响应） |

## 数据隔离说明

**两人数据完全独立：**
- **天天（老板）**: `open_id = ou_0b30fb807b98f8f5c18865912b8975cf`，数据在 `output/boss/`
- **波波**: `open_id = ou_cc19d62ec1cb5c5db18c13bc61efce53`，数据在 `output/boyfriend/`
- 生成命令：`python gen_dashboard_v2.py all`（或 `boss`/`boyfriend` 单独）
- ⚠️ 严禁混用两人数据

## 技术栈

- Python 3.11
- Flask（Web服务）
- APScheduler（定时任务）
- 腾讯API / MX妙想（数据源）
- HTML/CSS/JS（前端 — 纯静态，无框架）
- systemd（服务管理）

## 服务管理

```bash
# 仪表盘服务
sudo systemctl restart dashboard-server.service

# 报告服务  
sudo systemctl restart report-server.service

# 查看状态
sudo systemctl status dashboard-server.service
```

## 依赖安装

```bash
pip install -r requirements.txt
```

> ⚠️ Flask 服务默认用 `python3.11`，pip 安装需用 `python3.11 -m pip install`

## 历史

- 2026-05-07: 新增交互式仪表盘（v2），实现两人数据隔离
- 2026-05-08: 新增午间复盘、早盘荐股、资本流模块
- 2026-05-09: 妖股监控上线，仪表盘模板修复中（推至 GitHub）
