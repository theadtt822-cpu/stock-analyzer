# StockHolmes 炒股龙虾 - 项目交接书

## 项目概览

A股股票分析系统，支持实时行情、技术分析、StockHolmes规则评分、AI分析、自选股管理、持仓仪表盘、定时报告推送。

**服务器地址**: http://47.116.23.182:8081/（报告中心）+ 8082（交互式仪表盘）
**项目路径**: `/home/admin/.openclaw/workspace/daily_stock_analysis/`
**Python 虚拟环境**: 项目目录下的 `.venv/`
**Python 版本**: 3.11

---

## 两个用户数据隔离（⚠️ 核心业务逻辑，不要搞混）

整个系统服务两个独立用户，数据完全隔离：

| 用户 | 身份 | open_id | 专属目录 | 看板链接 |
|---|---|---|---|---|
| **邓天天（老板）** | 老板 | `ou_0b30fb807b98f8f5c18865912b8975cf` | `output/boss/` | `http://47.116.23.182:8082/tiantian/` |
| **波波** | 本人 | `ou_cc19d62ec1cb5c5db18c13bc61efce53` | `output/boyfriend/` | `http://47.116.23.182:8082/bobo/` |

**数据源文件**：
- 天天：`output/boss/portfolio_dashboard.json`（含 sector 字段）
- 波波：`output/boyfriend/portfolio_dashboard.json`（不含 sector 字段）

⚠️ 严禁把一个人的数据混到另一个人的文件里。

---

## 文件清单和功能

### 核心服务（两个服务器）

| 文件 | 功能 | 端口 | 用途 |
|---|---|---|---|
| `dashboard_server.py` | 交互式持仓仪表盘 | **8082** | Web 界面，展示持仓/自选股，支持增删改查 |
| `report_server.py` | 静态报告中心 | **8081** | 展示所有历史报告文件 |

### 定时报告脚本

| 文件 | 功能 | 执行时间 |
|---|---|---|
| `daily_scheduler.py` | 定时调度器（跑所有报告） | 08:30 / 11:30 / 15:30（工作日） |
| 底层调 `src/daily_collector.py` | 财经日报 / 午间新闻 / 收盘复盘 | 三个报告各一个函数 |

### 数据分析脚本

| 文件 | 功能 |
|---|---|
| `dashboard_server.py` 中的 `stockholmes_rules()` | StockHolmes 规则引擎（均线/MACD/RSI/乖离率/量比评分） |
| `dashboard_server.py` 中的 `generate_ai_analysis()` | 调用本地 LLM 做 AI 分析 |
| `fetch_kline_tencent.py` | 腾讯 API 获取 K 线数据（备选方案） |
| `watchlist_analyze.py` | 自选股批量分析（同时产生 StockHolmes 规则 + AI 分析） |

### 报告生成脚本

| 文件 | 功能 |
|---|---|
| `gen_dashboard_v2.py` | 生成持仓仪表盘 HTML 报告 |
| `generate_index.py` | 刷新报告中心首页 |
| `generate_report_tencent.py` | 生成个股分析报告 |

### KOL 追踪（老板专属功能）

| 文件 | 功能 |
|---|---|
| `kol_tracker.py` | KOL 代码跟踪，更新推荐/统计 |
| `kol_feishu_parser.py` | 解析飞书消息提取代码 |
| `kol_feishu_handler.py` | 飞书消息处理逻辑 |
| `templates/kol_tracker.html` | KOL 追踪页面模板 |

### 价格监控

| 文件 | 功能 |
|---|---|
| `price_monitor.py` | 价格监控主程序 |
| `price_monitor_alert.py` | 价格触发报警脚本 |
| `price_alert.sh` | 报警脚本 bash 封装 |
| `send_price_alert.py` | 飞书发送报警 |
| `alert_check.py` | 报警检查脚本 |

### 模板文件

| 文件 | 功能 |
|---|---|
| `templates/dashboard_v2.html` | **仪表盘主模板**（持仓+自选股都在一个页面） |
| `templates/dashboard.html` | 旧版仪表盘模板 |
| `templates/kol_tracker.html` | KOL 追踪页面 |

### 数据文件

| 文件 | 功能 |
|---|---|
| `output/boss/portfolio_dashboard.json` | 天天持仓数据 |
| `output/boyfriend/portfolio_dashboard.json` | 波波持仓数据 |
| `output/portfolio_data.json` | 波波旧持仓数据（兼容） |
| `output/boss/watchlist.json` | 天天自选股 |
| `output/boyfriend/watchlist.json` | 波波自选股 |
| `src/stock_codes.json` | A股代码映射表 |

---

## 常用操作命令

### 生成报告
```bash
# 同时为两人生成持仓仪表盘
python gen_dashboard_v2.py all

# 单独生成
python gen_dashboard_v2.py boss
python gen_dashboard_v2.py boyfriend

# 自选股分析
python watchlist_analyze.py sz002192 sh600105 --user boss
python watchlist_analyze.py sh603601 --user boyfriend

# 跑定时调度器（立即执行所有）
python daily_scheduler.py --now

# 刷新报告中心首页
python generate_index.py
```

### 启动/重启服务器
```bash
# 仪表盘（8082端口）
kill $(pgrep -f "dashboard_server.py")
sleep 1
nohup .venv/bin/python3 dashboard_server.py > /tmp/dashboard_server.log 2>&1 &

# 报告中心（8081端口）
kill $(pgrep -f "report_server.py")
sleep 1
nohup .venv/bin/python3 report_server.py > /tmp/report_server.log 2>&1 &
```

### 查看日志
```bash
tail -f /tmp/dashboard_server.log
tail -f /tmp/report_server.log
tail -f scheduler.log
```

---

## API 数据源

| 数据 | 来源 | 备注 |
|---|---|---|
| 实时行情 | 腾讯 `qt.gtimg.cn` | 已验证可用 |
| K线数据 | 腾讯 API（备选） | 东方财富 push2his 已不可用 |
| 新闻 | 妙想搜索 / 东方财富 | `eastmoney_financial_search` skill |
| 资金流向 | 东方财富 API | `dashboard_server.py` 中 `fetch_money_flow()` |
| AI分析 | 本地 LLM（`ollama` 或类似） | 超时约 30-60s |

---

## 已知的技术决策

1. **报告服务器文件命名规则**：个股报告文件名必须以 `sh` 或 `sz` 开头（如 `sz000823_超声电子_report.html`），否则不会被报告中心识别
2. **模板共享**：`dashboard_v2.html` 是唯一模板，两个用户共用。修改后需 **kill+重启 dashboard_server** + **Ctrl+F5 硬刷新**
3. **持仓卡片 div 平衡**：持仓卡片模板在第443行需要4个 `</div>` 来关闭 tv → tech-item → tech-row → _sh。来自今天的血泪教训
4. **K线数据**：东方财富的 push2his API 已完全不通，腾讯 `qt.gtimg.cn` 是可靠的备选

---

## 定时任务（已配好，一般不用动）

| 任务 | 时间 | 说明 |
|---|---|---|
| 财经日报 | 工作日 08:30 | 隔夜外盘 + 政策 + 板块预测 |
| 财经日报（波波） | 工作日 08:31 | 同上，波波专属投递 |
| 午间新闻 | 工作日 11:30 | A股/美股要闻汇总 |
| 午间新闻（波波） | 工作日 11:31 | 同上，波波专属投递 |
| 收盘复盘 | 工作日 15:30 | 指数 + 板块 + 技术分析 |
| 收盘复盘（波波） | 工作日 15:31 | 同上，波波专属投递 |
| KOL追踪 | 工作日 15:30 | 更新 KOL 推荐跟踪 |
| 价格监控 | 工作日 14:00-15:00 每5分钟 | 实时价格报警 |

全部通过 OpenClaw cron 和系统 crontab 管理。

---

## 目录结构

```
daily_stock_analysis/
├── dashboard_server.py         # 交互仪表盘（8082端口）
├── report_server.py            # 报告中心（8081端口）
├── daily_scheduler.py          # 定时调度器
├── watchlist_analyze.py        # 自选股分析
├── gen_dashboard_v2.py         # 持仓仪表盘生成
├── generate_report_tencent.py  # 个股报告生成
├── fetch_kline_tencent.py      # K线数据获取
├── kol_tracker.py              # KOL追踪
├── templates/
│   └── dashboard_v2.html       # 仪表盘模板（主要改这个）
├── output/
│   ├── boss/                   # 天天数据
│   │   ├── portfolio_dashboard.json
│   │   ├── watchlist.json
│   │   └── watchlist/          # 自选股分析报告
│   └── boyfriend/              # 波波数据
│       ├── portfolio_dashboard.json
│       └── watchlist.json
├── src/                        # 核心库
│   ├── daily_collector.py      # 日报/午间/收盘报告
│   ├── config.py               # 配置
│   └── ...
└── project.json
```
