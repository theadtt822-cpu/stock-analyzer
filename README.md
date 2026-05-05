# 股票分析工具

基于 Python + AKShare 的 A 股技术分析工具，自动生成专业股票分析报告。

## 功能

- 获取 A 股日线数据（AKShare）
- 计算技术指标：MA、MACD、RSI、布林带、KDJ、ATR
- 自动生成 HTML 分析报告：评分、趋势判断、买卖信号、操作建议
- 生成 K 线图及各项指标图表

## 安装

```bash
pip install -r requirements.txt
```

## 使用

```bash
python analyze.py
```

运行后会在 `output/` 目录生成：
- `analysis_report.html` - 专业分析报告（浏览器打开）
- `01_candlestick_volume.png` ~ `07_analysis_report.png` - 各项指标图表

## 修改分析标的

编辑 `analyze.py`，修改股票代号和名称：

```python
# 获取数据
df = stock.get_stock_daily("sh600519", "20230101", "20260505")
```

## 项目结构

```
├── src/
│   ├── api/              # 数据获取
│   │   ├── stock.py      # 股票数据
│   │   └── market.py     # 市场/指数数据
│   ├── analysis/         # 分析模块
│   │   ├── tech_indicator.py   # 技术指标计算
│   │   ├── visualizer.py       # 图表生成
│   │   └── report_generator.py # HTML 报告生成
│   └── data/             # 数据存储
├── analyze.py            # 主入口脚本
└── requirements.txt      # 依赖
```

## 数据源

- [AKShare](https://akshare.akshare.xyz/) - 开源金融数据接口
