# 股票分析工具

基于 Python + AKShare 的 A 股技术分析工具，自动生成专业股票分析报告。

## 功能

- 获取 A 股日线数据（AKShare）
- 计算技术指标：MA、MACD、RSI、布林带、KDJ、ATR
- 自动生成 HTML 分析报告：评分、趋势判断、买卖信号、操作建议
- 生成 K 线图及各项指标图表
- 每日定时调度：盘前预测、午间新闻、收盘复盘
- 6 步交易策略：行情→盘口→技术指标→资金流向→关键价位→交易策略
- 微信推送（Server酱）

## 项目结构与文件说明

```
├── analyze.py                  # 单只股票深度分析（手动运行）
├── batch_analyze.py            # 批量分析多只股票，生成各自 HTML 报告
├── daily_scheduler.py          # 定时调度器（APScheduler），工作日自动运行三段报告
├── generate_index.py           # 扫描 output/ 生成汇总入口页 index.html
├── main.py                     # 模块导出入口，聚合各模块类/函数
├── requirements.txt            # Python 依赖
├── project.json                # 项目元信息（名称/版本/Python 版本）
├── .env.example                # 环境变量模板
├── .gitignore                  # Git 忽略规则
│
├── src/
│   ├── __init__.py             # 包初始化，导出 StockData/MarketData/TechIndicator 等核心类
│   ├── config.py               # 配置管理，加载环境变量（DATA_DIR/LOG_LEVEL/AK_TOKEN/股票列表）
│   ├── logger.py               # JSON 格式日志输出（stdout）
│   ├── daily_collector.py      # 定时报告数据收集层：串联 AKShare 数据 → 报告生成器
│   │
│   ├── api/
│   │   ├── __init__.py         # 导出 StockData / MarketData
│   │   ├── stock.py            # 股票数据：日线、分时、资金流、融资融券
│   │   └── market.py           # 市场数据：指数日线、行业板块、成交额、融资融券
│   │
│   ├── analysis/
│   │   ├── __init__.py         # 导出所有分析类/报告生成器
│   │   ├── tech_indicator.py   # 技术指标计算：SMA/MACD/RSI/布林带/KDJ/ATR
│   │   ├── visualizer.py       # matplotlib 图表生成：K线+成交量、MACD、RSI、布林带等
│   │   ├── report_generator.py # 个股 HTML 报告生成器（含 6 步交易策略卡片）
│   │   ├── factor_analyzer.py  # 因子分析：收益率、波动率、夏普比率、最大回撤、Alpha/Beta
│   │   ├── news_report.py      # 午间新闻 HTML 报告生成器
│   │   ├── premarket_report.py # 盘前预测 HTML 报告生成器
│   │   └── postmarket_report.py# 收盘复盘 HTML 报告生成器
│   │
│   ├── data/
│   │   ├── __init__.py         # 包初始化
│   │   └── storage.py          # CSV 文件存储/加载（支持增量追加、去重）
│   │
│   └── utils/
│       ├── __init__.py         # 包初始化
│       ├── data_utils.py       # 数据清洗工具：去重、去空值、价格标准化、日期过滤
│       └── push.py             # Server酱微信推送
│
├── output/                     # 报告输出目录
│   ├── index.html              # 报告汇总入口页（自动生成）
│   ├── premarket_*.html        # 盘前预测报告
│   ├── news_*.html             # 午间新闻报告
│   ├── postmarket_*.html       # 收盘复盘报告
│   ├── *_report.html           # 个股分析报告
│   └── *.png                   # 指标图表
│
└── data/                       # 股票数据缓存（CSV）
```

### 入口脚本说明

| 脚本 | 用途 | 运行方式 |
|------|------|----------|
| `analyze.py` | 单只股票深度分析，生成完整图表+HTML | `python analyze.py` |
| `batch_analyze.py` | 批量分析多只股票 | `python batch_analyze.py sh600186 sh600519` |
| `daily_scheduler.py` | 定时调度（盘前/午间/收盘） | `python daily_scheduler.py` 或 `--now` 立即执行 |
| `generate_index.py` | 生成报告汇总入口页 | `python generate_index.py` |

### 定时调度说明

| 时间 | 报告 | 内容 |
|------|------|------|
| 08:30 | 盘前预测 | 隔夜外盘、期货、政策消息、板块预测、综合研判 |
| 11:30 | 午间新闻 | A股/美股要闻、经济指标、投行观点 |
| 15:30 | 收盘复盘 | 指数、板块排行、涨跌停、技术面、明日展望 |

## 数据源

- [AKShare](https://akshare.akshare.xyz/) - 开源金融数据接口

## 重要规范

- **永远不要使用模拟/编造数据**：所有行情数据（股价、指数、板块涨跌、涨跌停）必须来自真实 API 或 WebSearch 获取
- 市场休市/未开盘时明确告知用户，不可用模拟数据填充
- 生成报告时必须标注实际交易日日期
