#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量股票分析脚本
用法: python batch_analyze.py sh600186 sh600519 sz000858
"""
import sys
import os
from datetime import datetime

# 设置中文显示
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

from src import StockData, TechIndicator
from src.analysis import ReportGenerator

os.makedirs("./output", exist_ok=True)

# 股票列表（命令行参数）
stocks = sys.argv[1:] if len(sys.argv) > 1 else ["sh600186"]

stock = StockData()
today = datetime.now().strftime('%Y-%m-%d')

print(f"批量分析 {len(stocks)} 只股票: {', '.join(stocks)}")
print("=" * 60)

results = []

for i, symbol in enumerate(stocks, 1):
    print(f"\n[{i}/{len(stocks)}] 分析 {symbol} ...")

    try:
        df = stock.get_stock_daily(symbol, "20230101", "20260505")
        if df.empty:
            print(f"  ✗ 获取数据失败")
            continue

        if 'amount' in df.columns and 'volume' not in df.columns:
            df = df.rename(columns={'amount': 'volume'})

        ti = TechIndicator(df)
        df['sma5'] = ti.calc_sma(5)
        df['sma10'] = ti.calc_sma(10)
        df['sma20'] = ti.calc_sma(20)
        df['sma60'] = ti.calc_sma(60)
        macd_data = ti.calc_macd()
        df['dif'], df['dea'], df['macd'] = macd_data['dif'], macd_data['dea'], macd_data['macd']
        df['rsi'] = ti.calc_rsi(14)
        boll_data = ti.calc_boll(20)
        df['upper'], df['middle'], df['lower'] = boll_data['upper'], boll_data['middle'], boll_data['lower']
        kdj_data = ti.calc_kdj(9)
        df['k'], df['d'], df['j'] = kdj_data['k'], kdj_data['d'], kdj_data['j']
        df['atr'] = ti.calc_atr(14)

        # 获取资金流数据（用于交易策略卡片）
        print(f"  获取资金流数据...", end=' ', flush=True)
        fund_flow = stock.get_fund_flow_data(symbol)
        print("OK")

        rg = ReportGenerator(df, symbol)
        score = rg.calc_composite_score()
        trend = rg.analyze_trend()
        indicators = [rg.interpret_macd(), rg.interpret_rsi(), rg.interpret_ma(), rg.interpret_kdj(), rg.interpret_boll()]
        advice = rg.get_advice()

        close = df.iloc[-1]['close']
        prev = df.iloc[-2]['close'] if len(df) > 1 else close
        chg = close - prev
        chg_pct = (chg / prev * 100) if prev > 0 else 0

        results.append({
            'symbol': symbol,
            'close': close,
            'chg': chg,
            'chg_pct': chg_pct,
            'score': score['score'],
            'level': score['level'],
            'short': trend['short']['trend'],
            'mid': trend['mid']['trend'],
            'long': trend['long']['trend'],
            'indicators': indicators,
            'support': advice['stop_loss'],
            'risks': advice['risks']
        })

        # 生成单只股票的 HTML 报告（含交易策略卡片）
        rg.generate_html(f"./output/{symbol}_report.html", fund_flow_data=fund_flow)

        # 只生成综合报告PNG，不生成各个指标图（加速）
        from src import Visualizer
        viz = Visualizer()
        viz.plot_analysis_report(df, symbol, save_path=f"./output/{symbol}_chart.png")
        plt.close('all')

        print(f"  [OK] 综合评分: {score['score']}/100 ({score['level']})")
        print(f"  [OK] 短期: {trend['short']['trend']} 中期: {trend['mid']['trend']} 长期: {trend['long']['trend']}")
        print(f"  [OK] 报告: output/{symbol}_report.html")

    except Exception as e:
        print(f"  [FAIL] 分析失败: {e}")

# 汇总输出
print("\n" + "=" * 60)
print("批量分析汇总")
print("=" * 60)

for r in results:
    chg_sign = "+" if r['chg'] >= 0 else ""
    print(f"\n{r['symbol']}: {r['close']:.2f} ({chg_sign}{r['chg_pct']:.2f}%) | 评分 {r['score']}/100 {r['level']}")
    print(f"  趋势: 短{r['short']} 中{r['mid']} 长{r['long']}")
    for ind in r['indicators']:
        print(f"  {ind['name']}: {ind['status']} - {ind['desc']}")

print(f"\n共完成 {len(results)}/{len(stocks)} 只股票分析")
print(f"HTML 报告: output/{stocks[0]}_report.html (等)")
