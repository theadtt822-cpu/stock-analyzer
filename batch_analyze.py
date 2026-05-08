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

import akshare as ak
import pandas as pd
import requests
from src import StockData, TechIndicator
from src.analysis import ReportGenerator

os.makedirs("./output", exist_ok=True)

# 股票列表（命令行参数）
stocks = sys.argv[1:] if len(sys.argv) > 1 else ["sh600186"]

def fetch_tencent_today(symbol):
    """从腾讯实时行情获取今日数据，补充到日线DataFrame"""
    try:
        code_num = symbol.replace('sh', '').replace('sz', '')
        prefix = 'sh' if code_num.startswith('6') else 'sz'
        url = f"https://qt.gtimg.cn/q={prefix}{code_num}"
        resp = requests.get(url, timeout=5)
        resp.encoding = 'GBK'
        parts = resp.text.split('~')
        if len(parts) > 35:
            dt_str = parts[30]  # e.g. 20260506161405
            today = f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:8]}"
            return pd.DataFrame([{
                'date': today,
                'open': float(parts[5]),
                'close': float(parts[3]),
                'high': float(parts[33]) if len(parts) > 33 else float(parts[3]),
                'low': float(parts[34]) if len(parts) > 34 else float(parts[3]),
                'volume': float(parts[6]),
            }])
    except Exception as e:
        print(f"  ⚠️ 腾讯实时行情获取失败: {e}")
    return None

def ensure_today_data(df, symbol):
    """确保日线数据包含今天数据，AKShare未更新则用腾讯实时补充"""
    if df.empty:
        return df
    last_date = str(df.iloc[-1]['date'])
    today = datetime.now().strftime('%Y-%m-%d')
    if last_date != today:
        realtime = fetch_tencent_today(symbol)
        if realtime is not None:
            df = pd.concat([df, realtime], ignore_index=True)
            print(f"  📡 AKShare数据截至{last_date}，已用腾讯实时行情补充今日({today})")
        else:
            print(f"  ⚠️ 腾讯实时行情未更新，使用截至 {last_date} 的数据")
    return df

# 获取股票代码到名称的映射
def get_stock_name(symbol):
    """获取股票名称"""
    try:
        code = symbol.replace('sh', '').replace('sz', '')
        df = ak.stock_info_a_code_name()
        row = df[df['code'] == code]
        if not row.empty:
            return row.iloc[0]['name']
    except:
        pass
    return symbol

stock = StockData()
today = datetime.now().strftime('%Y-%m-%d')

print(f"批量分析 {len(stocks)} 只股票: {', '.join(stocks)}")
print("=" * 60)

results = []

for i, symbol in enumerate(stocks, 1):
    print(f"\n[{i}/{len(stocks)}] 分析 {symbol} ...")

    try:
        end = datetime.now().strftime('%Y%m%d')
        df = stock.get_stock_daily(symbol, "20230101", end)
        # 如果日线数据没到今天，用腾讯实时行情补充
        df = ensure_today_data(df, symbol)
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
        # 双版本评分
        stockholmes = rg.analyze_stockholmes()
        ai_analysis = rg.analyze_with_ai()
        # 兼容旧接口
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
            'stockholmes': stockholmes,
            'ai_analysis': ai_analysis,
            'short': trend['short']['trend'],
            'mid': trend['mid']['trend'],
            'long': trend['long']['trend'],
            'indicators': indicators,
            'support': advice['stop_loss'],
            'risks': advice['risks']
        })

        # 获取股票名称
        stock_name = get_stock_name(symbol)

        # 生成单只股票的 HTML 报告（双评分）
        rg.generate_html_dual(f"./output/{symbol}_{stock_name}_report.html", fund_flow_data=fund_flow, stock_name=stock_name, stockholmes=stockholmes, ai_analysis=ai_analysis)

        # 只生成综合报告PNG，不生成各个指标图（加速）
        from src import Visualizer
        viz = Visualizer()
        viz.plot_analysis_report(df, symbol, save_path=f"./output/{symbol}_{stock_name}_chart.png")
        plt.close('all')

        print(f"  [OK] 综合评分: {score['score']}/100 ({score['level']})")
        print(f"  [OK] 短期: {trend['short']['trend']} 中期: {trend['mid']['trend']} 长期: {trend['long']['trend']}")
        print(f"  [OK] 报告: output/{symbol}_{stock_name}_report.html")

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
