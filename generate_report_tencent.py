#!/usr/bin/env python3
"""
基于腾讯K线数据生成个股HTML分析报告
用法: python generate_report_tencent.py 000823 超声电子
"""
import json
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 设置中文显示
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'WenQuanYi Micro Hei']
plt.rcParams['axes.unicode_minus'] = False

sys.path.insert(0, os.path.dirname(__file__))
from src import TechIndicator
from src.analysis import ReportGenerator

def fetch_kline_full(code, days=120):
    """获取更长的K线数据用于计算指标"""
    market = 'sh' if code.startswith('6') else 'sz'
    full_code = f"{market}{code}"
    end_date = datetime.now()
    start_date = (end_date - timedelta(days=days*2)).strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    import urllib.request
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={full_code},day,{start_date},{end_date_str},{days},qfq"
    
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    req.add_header('Referer', 'https://stockapp.finance.qq.com/')
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    
    stock_data = data.get('data', {}).get(full_code, {})
    klines = stock_data.get('qfqday', []) or stock_data.get('day', [])
    
    result = []
    for k in klines:
        result.append({
            'date': k[0],
            'open': float(k[1]),
            'close': float(k[2]),
            'high': float(k[3]),
            'low': float(k[4]),
            'volume': float(k[5]),
        })
    
    return result

def generate_chart(df, symbol, stock_name, save_path):
    """生成K线+指标图表"""
    fig, axes = plt.subplots(4, 1, figsize=(12, 14), gridspec_kw={'height_ratios': [3, 1, 1, 1]})
    fig.suptitle(f'{stock_name} ({symbol}) 技术分析', fontsize=16, fontweight='bold')
    
    dates = range(len(df))
    
    # K线 + MA
    ax1 = axes[0]
    ax1.plot(dates, df['close'], 'k-', linewidth=1.5, label='Close')
    if 'sma5' in df.columns:
        ax1.plot(dates, df['sma5'], 'orange', linewidth=1, label='MA5')
    if 'sma10' in df.columns:
        ax1.plot(dates, df['sma10'], 'blue', linewidth=1, label='MA10')
    if 'sma20' in df.columns:
        ax1.plot(dates, df['sma20'], 'purple', linewidth=1, label='MA20')
    if 'sma60' in df.columns:
        ax1.plot(dates, df['sma60'], 'gray', linewidth=1, label='MA60')
    ax1.set_ylabel('Price')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.grid(True, alpha=0.3)
    
    # MACD
    ax2 = axes[1]
    if 'dif' in df.columns:
        ax2.plot(dates, df['dif'], 'red', linewidth=1, label='DIF')
    if 'dea' in df.columns:
        ax2.plot(dates, df['dea'], 'blue', linewidth=1, label='DEA')
    if 'macd' in df.columns:
        colors = ['red' if v > 0 else 'green' for v in df['macd'].values]
        ax2.bar(dates, df['macd'].values, color=colors, alpha=0.5, width=0.8, label='MACD')
    ax2.set_ylabel('MACD')
    ax2.legend(loc='upper left', fontsize=8)
    ax2.grid(True, alpha=0.3)
    
    # RSI
    ax3 = axes[2]
    if 'rsi' in df.columns:
        ax3.plot(dates, df['rsi'], 'purple', linewidth=1, label='RSI(14)')
    ax3.axhline(y=70, color='r', linestyle='--', alpha=0.5)
    ax3.axhline(y=30, color='g', linestyle='--', alpha=0.5)
    ax3.set_ylabel('RSI')
    ax3.legend(loc='upper left', fontsize=8)
    ax3.grid(True, alpha=0.3)
    
    # Volume
    ax4 = axes[3]
    if 'volume' in df.columns:
        vol_colors = ['red' if df.iloc[i]['close'] >= df.iloc[i]['open'] else 'green' for i in range(len(df))]
        ax4.bar(dates, df['volume'].values, color=vol_colors, alpha=0.6, width=0.8, label='Volume')
    ax4.set_ylabel('Volume')
    ax4.legend(loc='upper left', fontsize=8)
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close('all')

def main():
    if len(sys.argv) < 2:
        print("用法: python generate_report_tencent.py 000823 [股票名称]")
        sys.exit(1)
    
    code = sys.argv[1]
    stock_name = sys.argv[2] if len(sys.argv) > 2 else code
    
    print(f"📈 获取 {stock_name} ({code}) 的K线数据...")
    
    # 获取K线数据
    klines = fetch_kline_full(code, days=120)
    
    if not klines:
        print("❌ 获取K线数据失败")
        sys.exit(1)
    
    print(f"✅ 获取到 {len(klines)} 条K线数据")
    
    # 转换为DataFrame
    df = pd.DataFrame(klines)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    # 计算技术指标
    ti = TechIndicator(df)
    df['sma5'] = ti.calc_sma(5)
    df['sma10'] = ti.calc_sma(10)
    df['sma20'] = ti.calc_sma(20)
    df['sma60'] = ti.calc_sma(60)
    macd_data = ti.calc_macd()
    df['dif'] = macd_data['dif']
    df['dea'] = macd_data['dea']
    df['macd'] = macd_data['macd']
    df['rsi'] = ti.calc_rsi(14)
    boll_data = ti.calc_boll(20)
    df['upper'] = boll_data['upper']
    df['middle'] = boll_data['middle']
    df['lower'] = boll_data['lower']
    kdj_data = ti.calc_kdj(9)
    df['k'] = kdj_data['k']
    df['d'] = kdj_data['d']
    df['j'] = kdj_data['j']
    df['atr'] = ti.calc_atr(14)
    
    # 生成报告
    symbol = code
    rg = ReportGenerator(df, symbol)
    
    # 生成图表
    chart_path = f"./output/{symbol}_{stock_name}_chart.png"
    generate_chart(df, symbol, stock_name, chart_path)
    print(f"📊 图表已保存: {chart_path}")
    
    # 生成HTML报告
    html_path = f"./output/{symbol}_{stock_name}_report.html"
    rg.generate_html(html_path, fund_flow_data=None, stock_name=stock_name)
    print(f"📄 报告已保存: {html_path}")
    
    # 输出简要信息
    score = rg.calc_composite_score()
    trend = rg.analyze_trend()
    close = df.iloc[-1]['close']
    prev = df.iloc[-2]['close'] if len(df) > 1 else close
    chg_pct = (close - prev) / prev * 100 if prev > 0 else 0
    
    print(f"\n{'='*50}")
    print(f"{stock_name} ({symbol}) 分析完成")
    print(f"收盘价: {close:.2f} ({chg_pct:+.2f}%)")
    print(f"综合评分: {score['score']}/100 ({score['level']})")
    print(f"趋势: 短期{trend['short']['trend']} 中期{trend['mid']['trend']} 长期{trend['long']['trend']}")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
