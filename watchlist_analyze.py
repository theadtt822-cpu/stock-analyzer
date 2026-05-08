#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自选股分析报告：分析观望中的股票是否有入场机会
用法: python watchlist_analyze.py sh600186 sz000858 --user boss    # 天天
       python watchlist_analyze.py sh600186 sz000858 --user boyfriend  # 波波
"""
import sys
import os
from datetime import datetime

# 设置中文显示
import matplotlib
matplotlib.use('Agg')

import akshare as ak
import pandas as pd
import requests
from src import StockData, TechIndicator
from src.analysis import ReportGenerator

os.makedirs("./output", exist_ok=True)

# 解析参数
user_type = "boss"  # 默认 boss
stocks = []
i = 1
while i < len(sys.argv):
    if sys.argv[i] == "--user":
        user_type = sys.argv[i+1]
        i += 2
    else:
        stocks.append(sys.argv[i])
        i += 1

if not stocks:
    print("用法: python watchlist_analyze.py sh600186 sz000858 --user boss|boyfriend")
    sys.exit(1)

# 输出目录（自选股单独目录）
output_dir = f"./output/boss/watchlist" if user_type == "boss" else f"./output/boyfriend/watchlist"
os.makedirs(output_dir, exist_ok=True)

def fetch_tencent_today(symbol):
    """从腾讯实时行情补充今日数据"""
    try:
        code_num = symbol.replace('sh', '').replace('sz', '')
        prefix = 'sh' if code_num.startswith('6') else 'sz'
        url = f"https://qt.gtimg.cn/q={prefix}{code_num}"
        resp = requests.get(url, timeout=5)
        resp.encoding = 'GBK'
        parts = resp.text.split('~')
        if len(parts) > 35:
            dt_str = parts[30]
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
        print(f"  ⚠️ 腾讯实时获取失败: {e}")
    return None

def ensure_today_data(df, symbol):
    if df.empty:
        return df
    last_date = str(df.iloc[-1]['date'])
    today = datetime.now().strftime('%Y-%m-%d')
    if last_date != today:
        realtime = fetch_tencent_today(symbol)
        if realtime is not None:
            df = pd.concat([df, realtime], ignore_index=True)
    return df

def get_stock_name(symbol):
    try:
        code = symbol.replace('sh', '').replace('sz', '')
        df = ak.stock_info_a_code_name()
        row = df[df['code'] == code]
        if not row.empty:
            return row.iloc[0]['name']
    except:
        pass
    return symbol

def generate_watchlist_html(save_path, results, user_label):
    """生成自选股分析汇总报告"""
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # 按评分排序
    results_sorted = sorted(results, key=lambda x: (x['stockholmes']['signal_score'] + x['ai_analysis']['signal_score']) / 2, reverse=True)
    
    rows_html = ""
    for r in results_sorted:
        avg_score = (r['stockholmes_score'] + r['ai_score']) / 2
        
        if avg_score >= 70:
            badge, badge_bg, badge_fg = '🔴 可介入', '#DC143C', '#fff'
        elif avg_score >= 55:
            badge, badge_bg, badge_fg = '🟡 观察中', '#FF8C00', '#fff'
        elif avg_score >= 40:
            badge, badge_bg, badge_fg = '🟢 暂不碰', '#2E8B57', '#fff'
        else:
            badge, badge_bg, badge_fg = '⚫ 回避', '#666', '#fff'
        
        chg_color = "#DC143C" if r['chg_pct'] >= 0 else "#008000"
        chg_sign = "+" if r['chg_pct'] >= 0 else ""
        
        rows_html += f"""<tr>
    <td class="name-cell">{r['name']}<br/><span class="code">{r['symbol']}</span></td>
    <td style="color:{chg_color}">{r['close']:.2f}<br/><span style="font-size:12px">{chg_sign}{r['chg_pct']:.2f}%</span></td>
    <td class="ma-cell">
        <div class="ma-val">MA5: {r['ma5']:.2f}</div>
        <div class="ma-val">MA10: {r['ma10']:.2f}</div>
        <div class="ma-val">MA20: {r['ma20']:.2f}</div>
        <div class="ma-val">MA60: {r['ma60']:.2f}</div>
    </td>
    <td><div class="mini-score" style="background:{score_color(r['stockholmes_score'])}20;color:{score_color(r['stockholmes_score'])}">{r['stockholmes_score']}</div>
        <div class="mini-signal">{r['stockholmes_signal']}</div></td>
    <td><div class="mini-score" style="background:{score_color(r['ai_score'])}20;color:{score_color(r['ai_score'])}">{r['ai_score']}</div>
        <div class="mini-signal">{r['ai_signal']}</div></td>
    <td><span class="badge" style="background:{badge_bg};color:{badge_fg}">{badge}</span></td>
    <td class="advice-cell">{r['entry_advice']}</td>
</tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>自选股分析报告 - {today_str}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Microsoft YaHei', 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; padding: 16px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px; }}
.header h1 {{ font-size: 22px; margin-bottom: 4px; }}
.header .date {{ font-size: 13px; opacity: 0.7; }}
.header .user-label {{ font-size: 14px; margin-top: 8px; opacity: 0.8; }}
.summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 16px 0 0; }}
.summary-item {{ background: rgba(255,255,255,0.1); border-radius: 8px; padding: 12px; text-align: center; }}
.summary-item .num {{ font-size: 28px; font-weight: bold; }}
.summary-item .label {{ font-size: 12px; opacity: 0.7; margin-top: 4px; }}
.card {{ background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 16px; padding: 20px; }}
h2 {{ font-size: 16px; color: #333; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px; margin-bottom: 16px; }}

/* Table */
.wl-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.wl-table th {{ background: #f5f7fa; padding: 10px 8px; text-align: left; font-size: 12px; color: #666; font-weight: 600; border-bottom: 2px solid #e8e8e8; }}
.wl-table td {{ padding: 12px 8px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }}
.wl-table tr:hover {{ background: #fafbfc; }}
.name-cell {{ font-weight: 600; }}
.code {{ font-size: 12px; color: #999; }}
.ma-cell {{ font-size: 12px; color: #666; line-height: 1.6; }}
.ma-val {{ white-space: nowrap; }}
.mini-score {{ font-size: 20px; font-weight: bold; text-align: center; border-radius: 8px; padding: 4px 8px; }}
.mini-signal {{ font-size: 12px; color: #666; text-align: center; margin-top: 4px; }}
.badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; white-space: nowrap; }}
.advice-cell {{ font-size: 13px; color: #555; line-height: 1.5; }}

/* Legend */
.legend {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }}
.legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: #666; }}
.legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}

.footer {{ text-align: center; padding: 16px; color: #999; font-size: 12px; }}

@media (max-width: 900px) {{
    .wl-table {{ font-size: 12px; }}
    .wl-table th, .wl-table td {{ padding: 8px 4px; }}
}}
</style>
</head>
<body>
<div class="container">

<div class="header">
    <h1>📋 自选股分析报告</h1>
    <div class="date">{today_str} 生成</div>
    <div class="user-label">{user_label} 的自选股池</div>
    <div class="summary">
        <div class="summary-item"><div class="num">{len(results)}</div><div class="label">分析股票</div></div>
        <div class="summary-item"><div class="num">{sum(1 for r in results if (r['stockholmes_score']+r['ai_score'])/2 >= 70)}</div><div class="label">可介入</div></div>
        <div class="summary-item"><div class="num">{sum(1 for r in results if 55 <= (r['stockholmes_score']+r['ai_score'])/2 < 70)}</div><div class="label">观察中</div></div>
        <div class="summary-item"><div class="num">{sum(1 for r in results if (r['stockholmes_score']+r['ai_score'])/2 < 40)}</div><div class="label">回避</div></div>
    </div>
</div>

<div class="card">
    <h2>自选股总览</h2>
    <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background:#DC143C"></div>可介入 (≥70分)</div>
        <div class="legend-item"><div class="legend-dot" style="background:#FF8C00"></div>观察中 (55-69分)</div>
        <div class="legend-item"><div class="legend-dot" style="background:#2E8B57"></div>暂不碰 (40-54分)</div>
        <div class="legend-item"><div class="legend-dot" style="background:#666"></div>回避 (&lt;40分)</div>
    </div>
    <div style="overflow-x:auto">
    <table class="wl-table">
        <thead>
            <tr>
                <th>股票</th>
                <th>现价/涨跌</th>
                <th>均线系统</th>
                <th>规则评分</th>
                <th>AI评分</th>
                <th>综合判断</th>
                <th>操作建议</th>
            </tr>
        </thead>
        <tbody>
{rows_html}
        </tbody>
    </table>
    </div>
</div>

<div class="footer">
    本报告基于技术分析自动生成，仅供参考，不构成投资建议
    <br>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>

</div>
</body>
</html>"""

    with open(save_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return save_path

def score_color(s):
    if s >= 75: return '#DC143C'
    if s >= 60: return '#E8555A'
    if s >= 45: return '#888'
    if s >= 30: return '#2E8B57'
    return '#008000'

stock = StockData()
today = datetime.now().strftime('%Y-%m-%d')
user_label = "天天" if user_type == "boss" else "波波"

print(f"自选股分析 ({user_label}): {len(stocks)} 只")
print("=" * 60)

results = []

for idx, symbol in enumerate(stocks, 1):
    print(f"\n[{idx}/{len(stocks)}] 分析 {symbol} ...")
    try:
        end = datetime.now().strftime('%Y%m%d')
        df = stock.get_stock_daily(symbol, "20230101", end)
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

        rg = ReportGenerator(df, symbol)
        stockholmes = rg.analyze_stockholmes()
        ai_analysis = rg.analyze_with_ai()

        close = df.iloc[-1]['close']
        prev = df.iloc[-2]['close'] if len(df) > 1 else close
        chg_pct = (close - prev) / prev * 100 if prev > 0 else 0

        # 生成入场建议
        avg_score = (stockholmes['signal_score'] + ai_analysis['signal_score']) / 2
        ma5 = df.iloc[-1].get('sma5', 0)
        ma20 = df.iloc[-1].get('sma20', 0)
        atr = df.iloc[-1].get('atr', 0)
        
        if avg_score >= 70:
            entry_advice = f"趋势向好，可考虑介入\n建议入场价: {close:.2f} 附近\n止损位: {close * 0.95:.2f}（-5%）\n目标位: {close * 1.08:.2f}（+8%）"
        elif avg_score >= 55:
            entry_advice = f"条件偏多但需等待更好位置\n建议回踩 MA20({ma20:.2f}) 附近低吸\n止损位: {ma20 * 0.97:.2f}\n仓位: 轻仓试探（10%-20%）"
        elif avg_score >= 40:
            entry_advice = f"趋势不明朗，暂不介入\n关注方向选择后再行动\n当前风险 > 收益比\n建议继续观望"
        else:
            entry_advice = f"趋势走弱，回避\n不建议抄底\n等待企稳信号出现\n关注是否出现底部反转"

        stock_name = get_stock_name(symbol)

        results.append({
            'symbol': symbol,
            'name': stock_name,
            'close': close,
            'chg_pct': chg_pct,
            'ma5': df.iloc[-1].get('sma5', 0),
            'ma10': df.iloc[-1].get('sma10', 0),
            'ma20': df.iloc[-1].get('sma20', 0),
            'ma60': df.iloc[-1].get('sma60', 0),
            'stockholmes_score': stockholmes['signal_score'],
            'stockholmes_signal': stockholmes['buy_signal'],
            'ai_score': ai_analysis['signal_score'],
            'ai_signal': ai_analysis['buy_signal'],
            'entry_advice': entry_advice,
            # 详细数据也保存（可选：后续扩展）
            'stockholmes': stockholmes,
            'ai_analysis': ai_analysis,
        })

        print(f"  [OK] 规则:{stockholmes['signal_score']}分({stockholmes['buy_signal']}) AI:{ai_analysis['signal_score']}分({ai_analysis['buy_signal']})")

    except Exception as e:
        print(f"  [FAIL] {e}")

# 生成汇总报告
ts = datetime.now().strftime('%Y%m%d_%H%M')
report_path = f"{output_dir}/自选股分析_{ts}.html"
latest_path = f"{output_dir}/自选股分析_最新.html"
generate_watchlist_html(report_path, results, user_label)
# 同时更新最新版本
generate_watchlist_html(latest_path, results, user_label)

print(f"\n{'='*60}")
print(f"自选股分析报告已生成: {report_path}")
print(f"最新版本: {latest_path}")
print(f"共完成 {len(results)}/{len(stocks)} 只分析")

# 输出各股排序
results_sorted = sorted(results, key=lambda x: (x['stockholmes_score'] + x['ai_score']) / 2, reverse=True)
print(f"\n{'排名':>4} {'股票':>10} {'现价':>8} {'涨跌':>8} {'规则':>6} {'AI':>6} {'综合':>6} {'判断':>8}")
print("-" * 70)
for i, r in enumerate(results_sorted, 1):
    avg = (r['stockholmes_score'] + r['ai_score']) / 2
    chg_sign = "+" if r['chg_pct'] >= 0 else ""
    print(f"{i:>4} {r['name']:>10} {r['close']:>8.2f} {chg_sign}{r['chg_pct']:>7.2f}% {r['stockholmes_score']:>5}分 {r['ai_score']:>5}分 {avg:>5.0f}分 {r['stockholmes_signal']:>8}")
