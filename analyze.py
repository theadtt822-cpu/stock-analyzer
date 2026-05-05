#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
股票分析脚本 - 以贵州茅台为例
"""
from src import StockData, MarketData, TechIndicator, Visualizer
from src.data.storage import DataStorage
import pandas as pd
import os

# 设置中文显示
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 创建输出目录
os.makedirs("./output", exist_ok=True)

def main():
    print("=" * 60)
    print("股票分析工具 - 贵州茅台 (sh600519)")
    print("=" * 60)

    # 初始化
    stock = StockData()
    storage = DataStorage("./data")
    viz = Visualizer()

    # 获取最近两年的日线数据
    print("\n[1] 获取股票数据...")
    df = stock.get_stock_daily("sh600519", "20230101", "20260505")

    if df.empty:
        print("获取数据失败")
        return

    print(f"成功获取 {len(df)} 条数据")
    print(df.tail())

    # 如果列名是 amount，重命名为 volume
    if 'amount' in df.columns and 'volume' not in df.columns:
        df = df.rename(columns={'amount': 'volume'})

    # 保存数据
    storage.save_stock_data(df, "sh600519", force=True)
    print("\n数据已保存到 ./data/stock_sh600519.csv")

    # 计算技术指标
    print("\n[2] 计算技术指标...")
    ti = TechIndicator(df)

    # 移动平均线
    df['sma5'] = ti.calc_sma(5)
    df['sma10'] = ti.calc_sma(10)
    df['sma20'] = ti.calc_sma(20)
    df['sma60'] = ti.calc_sma(60)

    # MACD
    macd_data = ti.calc_macd()
    df['dif'] = macd_data['dif']
    df['dea'] = macd_data['dea']
    df['macd'] = macd_data['macd']

    # RSI
    df['rsi'] = ti.calc_rsi(14)

    # 布林带
    boll_data = ti.calc_boll(20)
    df['upper'] = boll_data['upper']
    df['middle'] = boll_data['middle']
    df['lower'] = boll_data['lower']

    # KDJ
    kdj_data = ti.calc_kdj(9)
    df['k'] = kdj_data['k']
    df['d'] = kdj_data['d']
    df['j'] = kdj_data['j']

    # ATR
    df['atr'] = ti.calc_atr(14)

    print("技术指标计算完成")
    print(df[['date', 'close', 'sma20', 'macd', 'rsi']].tail())

    # 保存带指标的数据
    df.to_csv("./data/stock_sh600519_with_indicators.csv", index=False, encoding='utf-8-sig')
    print("\n带指标的数据已保存")

    # 可视化
    print("\n[3] 生成图表...")

    # 图1: K线图 + 成交量
    print("\n正在生成 K线图 + 成交量...")
    viz.plot_candlestick_with_volume(df, "贵州茅台", save_path="./output/01_candlestick_volume.png")
    print("已保存: ./output/01_candlestick_volume.png")

    # 图2: MACD
    print("正在生成 MACD...")
    viz.plot_macd(df, "贵州茅台")
    plt.savefig("./output/02_macd.png", dpi=150, bbox_inches='tight')
    plt.close()
    print("已保存: ./output/02_macd.png")

    # 图3: RSI
    print("正在生成 RSI...")
    viz.plot_rsi(df, "贵州茅台")
    plt.savefig("./output/03_rsi.png", dpi=150, bbox_inches='tight')
    plt.close()
    print("已保存: ./output/03_rsi.png")

    # 图4: 布林带
    print("正在生成 布林带...")
    viz.plot_boll(df, "贵州茅台")
    plt.savefig("./output/04_boll.png", dpi=150, bbox_inches='tight')
    plt.close()
    print("已保存: ./output/04_boll.png")

    # 图5: KDJ
    print("正在生成 KDJ...")
    viz.plot_kdj(df, "贵州茅台")
    plt.savefig("./output/05_kdj.png", dpi=150, bbox_inches='tight')
    plt.close()
    print("已保存: ./output/05_kdj.png")

    # 图6: ATR
    print("正在生成 ATR...")
    viz.plot_atr(df, "贵州茅台")
    plt.savefig("./output/06_atr.png", dpi=150, bbox_inches='tight')
    plt.close()
    print("已保存: ./output/06_atr.png")

    # 图7: 综合分析报告
    print("正在生成 综合分析报告...")
    viz.plot_analysis_report(df, "贵州茅台", save_path="./output/07_analysis_report.png")
    print("已保存: ./output/07_analysis_report.png")

    # 图8: 专业分析 HTML 报告
    print("\n[4] 生成专业分析报告...")
    from src.analysis import ReportGenerator
    rg = ReportGenerator(df, "贵州茅台 (sh600519)")
    report_path = rg.generate_html("./output/analysis_report.html")
    print(f"已保存: {report_path}")

    print("\n" + "=" * 60)
    print("所有图表已生成并保存到 ./output/")
    print("=" * 60)
    print("\n生成的文件:")
    for f in sorted(os.listdir("./output")):
        filepath = os.path.join("./output", f)
        size = os.path.getsize(filepath) / 1024
        print(f"  - {f} ({size:.1f} KB)")

if __name__ == "__main__":
    main()
