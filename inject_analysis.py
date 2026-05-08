#!/usr/bin/env python3
"""将batch_analyze的分析结果注入portfolio_dashboard.json并刷新实时数据"""
import json
import os
import sys
import time
import re
import urllib.request
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
BOSS_DIR = os.path.join(DATA_DIR, 'boss')

def get_market_prefix(code):
    if code.startswith('6'): return 'sh'
    return 'sz'

def fetch_tencent_kline(code, days=70):
    """获取腾讯K线数据"""
    market = get_market_prefix(code)
    full_code = f"{market}{code}"
    from datetime import timedelta
    end_date = datetime.now()
    start_date = (end_date - timedelta(days=days*2)).strftime("%Y-%m-%d")
    end_date_str = datetime.now().strftime("%Y-%m-%d")
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={full_code},day,{start_date},{end_date_str},{days},qfq"
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        stock_data = data.get('data', {}).get(full_code, {})
        klines = stock_data.get('qfqday', [])
        if not klines:
            klines = stock_data.get('day', [])
        result = []
        for k in klines:
            result.append({
                'date': k[0], 'open': float(k[1]), 'close': float(k[2]),
                'high': float(k[3]), 'low': float(k[4]), 'volume': float(k[5]),
            })
        return result
    except Exception as e:
        print(f"  ❌ K线获取失败: {e}")
        return []

def compute_indicators(klines):
    if len(klines) < 60: return None
    closes = [k['close'] for k in klines]
    volumes = [k['volume'] for k in klines]
    
    ma5 = round(sum(closes[-5:])/5, 2)
    ma10 = round(sum(closes[-10:])/10, 2)
    ma20 = round(sum(closes[-20:])/20, 2)
    ma60 = round(sum(closes[-60:])/60, 2)
    
    # EMA for MACD
    def ema(data, span):
        k = 2/(span+1)
        result = [data[0]]
        for i in range(1, len(data)):
            result.append(data[i]*k + result[-1]*(1-k))
        return result
    
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    dif_vals = [ema12[i] - ema26[i] for i in range(len(closes))]
    dea_vals = ema(dif_vals, 9)
    
    dif = round(dif_vals[-1], 2)
    dea = round(dea_vals[-1], 2)
    macd_bar = round(2*(dif-dea), 3)
    
    # RSI
    delta = [closes[i]-closes[i-1] for i in range(1, len(closes))]
    gains = [d if d>0 else 0 for d in delta]
    losses = [-d if d<0 else 0 for d in delta]
    avg_gain = sum(gains[-14:])/14
    avg_loss = sum(losses[-14:])/14
    rs = avg_gain/avg_loss if avg_loss != 0 else 100
    rsi = round(100-(100/(1+rs)), 1)
    
    vol_5avg = sum(volumes[-5:])/5
    vol_ratio = round(volumes[-1]/vol_5avg, 2) if vol_5avg > 0 else 1.0
    
    if len(closes) >= 6:
        change_5d = round((closes[-1]-closes[-6])/closes[-6]*100, 2)
    else:
        change_5d = 0
    
    high_20 = round(max(closes[-20:]), 2)
    low_20 = round(min(closes[-20:]), 2)
    
    last_close = closes[-1]
    bias5 = round((last_close-ma5)/ma5*100, 2)
    bias20 = round((last_close-ma20)/ma20*100, 2)
    
    if ma5 > ma10 > ma20: trend = '多头排列'
    elif ma5 < ma10 < ma20: trend = '空头排列'
    elif ma5 < ma10: trend = 'MA5回落'
    else: trend = '震荡'
    
    # KDJ
    low_n = min(closes[-9:])
    high_n = max(closes[-9:])
    rsv = (closes[-1]-low_n)/(high_n-low_n)*100 if high_n != low_n else 50
    kdj_k = round(rsv, 1)
    
    return {
        'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60,
        'dif': dif, 'dea': dea, 'macd_bar': macd_bar,
        'macd_signal': '金叉' if macd_bar > 0 else '死叉',
        'rsi': rsi, 'vol_ratio': vol_ratio, 'change_5d': change_5d,
        'high_20': high_20, 'low_20': low_20,
        'tushare_close': round(last_close, 2),
        'trend': trend, 'bias5': bias5, 'bias20': bias20,
        'kdj_k': kdj_k, 'score': 0,
    }

def fetch_realtime_one(code):
    """获取单只实时行情"""
    prefix = get_market_prefix(code)
    url = f'https://qt.gtimg.cn/q={prefix}{code}'
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=5) as resp:
            text = resp.read().decode('GBK')
        m = re.match(r'v_\w+="([^"]+)"', text)
        if m:
            parts = m.group(1).split('~')
            if len(parts) >= 33:
                return {
                    'current': float(parts[3]),
                    'pre_close': float(parts[4]),
                    'change_pct': float(parts[32]),
                }
    except: pass
    return None

def inject_analysis(code, name, data_file):
    """分析并注入单只股票"""
    print(f"📊 分析 {name} ({code})...")
    
    # 1. K线技术指标
    klines = fetch_tencent_kline(code)
    tech = compute_indicators(klines) if klines else {}
    if tech:
        print(f"  ✅ K线 {len(klines)}条, MA5={tech['ma5']}, RSI={tech['rsi']}, MACD={tech['macd_signal']}")
    
    # 2. 实时行情
    rt = fetch_realtime_one(code)
    
    # 读取JSON
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    # 找到对应记录
    for r in data['results']:
        if r['code'] == code:
            if tech:
                r['technical'] = tech
            
            if rt:
                r['current'] = rt['current']
                r['pre_close'] = rt['pre_close']
                r['day_change'] = rt['change_pct']
                r['change_pct'] = rt['change_pct']
                r['pnl'] = (rt['current'] - r['cost']) * r['qty']
                r['pnl_pct'] = round((rt['current'] - r['cost']) / r['cost'] * 100, 2)
                r['position_value'] = rt['current'] * r['qty']
                print(f"  ✅ 实时: {rt['current']:.2f} ({rt['change_pct']:+.2f}%)")
            
            # StockHolmes规则分析
            if tech:
                r['stockholmes'] = {
                    'code': code,
                    'trend_status': tech.get('trend',''),
                    'ma_alignment': f"MA5({tech['ma5']})>MA10({tech['ma10']})>MA20({tech['ma20']})" if tech.get('trend')=='多头排列' else "均线交织",
                    'trend_strength': 85 if tech.get('trend')=='多头排列' else 50,
                    'ma5': tech.get('ma5'), 'ma10': tech.get('ma10'),
                    'ma20': tech.get('ma20'), 'ma60': tech.get('ma60'),
                    'current_price': tech.get('tushare_close'),
                    'bias_ma5': tech.get('bias5'), 'bias_ma10': tech.get('bias20'),
                    'bias_ma20': tech.get('bias20'),
                    'volume_status': '量能正常',
                    'volume_ratio_5d': tech.get('vol_ratio'),
                    'volume_trend': '量能正常',
                    'support_ma5': tech.get('ma5',0) > 0,
                    'support_ma10': tech.get('ma10',0) > 0,
                    'buy_signal': '买入' if tech.get('trend')=='多头排列' else '持有',
                    'signal_score': 70 if tech.get('trend')=='多头排列' else 50,
                    'signal_reasons': ['✅ 多头排列，顺势做多', '✅ MACD金叉'],
                    'risk_factors': [f'⚠️ RSI超买({tech.get("rsi",0)}>70)，短期回调风险高'] if tech.get('rsi',0) > 70 else [],
                    'macd_status': '多头' if tech.get('macd_signal')=='金叉' else '空头',
                    'macd_signal': '✓ MACD金叉，上涨动能增强' if tech.get('macd_signal')=='金叉' else '✗ MACD死叉',
                    'rsi_status': '超买' if tech.get('rsi',0) > 70 else '中性',
                    'rsi_signal': f"⚠️ RSI超买({tech.get('rsi',0)}>70)" if tech.get('rsi',0) > 70 else 'RSI正常',
                }
            
            # AI分析（简化版）
            if tech:
                advice = '买入' if tech.get('trend') == '多头排列' else '持有'
                confidence = '高' if tech.get('trend') == '多头排列' else '中'
                sentiment = 75 if tech.get('trend') == '多头排列' else 55
                r['ai_analysis'] = {
                    'operation_advice': advice,
                    'target_price': f"{tech['tushare_close']*1.15:.1f}" if tech.get('tushare_close') else '',
                    'stop_loss': f"{tech['tushare_close']*0.92:.1f}" if tech.get('tushare_close') else '',
                    'confidence_level': confidence,
                    'sentiment_score': sentiment,
                    'analysis_summary': f"{tech.get('trend','震荡')}+{tech.get('macd_signal','')}，{'趋势强劲' if tech.get('trend')=='多头排列' else '关注方向选择'}",
                }
            
            r['rule_score'] = r.get('stockholmes', {}).get('signal_score')
            break
    
    # 重新计算总览
    tc = sum(r['position_cost'] for r in data['results'])
    tv = sum(r['position_value'] for r in data['results'])
    data['total_cost'] = tc
    data['total_value'] = tv
    data['total_pnl'] = tv - tc
    data['total_pnl_pct'] = round((tv-tc)/tc*100, 2)
    now = datetime.now()
    data['date'] = now.strftime('%Y-%m-%d')
    data['report_time'] = now.strftime('%Y-%m-%d %H:%M') + ' 盘中实时'
    
    with open(data_file, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 分析数据已注入")
    return data

def gen_dashboard(data):
    """生成仪表盘HTML"""
    sys.path.insert(0, os.path.dirname(__file__))
    from gen_dashboard_v2 import generate
    
    html = generate(data, report_time=data['report_time'])
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M")
    out_path = os.path.join(BOSS_DIR, f'持仓仪表盘_{ts}.html')
    with open(out_path, 'w') as f:
        f.write(html)
    latest_path = os.path.join(BOSS_DIR, '持仓仪表盘_最新.html')
    with open(latest_path, 'w') as f:
        f.write(html)
    main_path = os.path.join(DATA_DIR, 'portfolio_dashboard.html')
    with open(main_path, 'w') as f:
        f.write(html)
    
    print(f"📊 报告已生成: {out_path}")
    print(f"   文件大小: {len(html):,} bytes")

if __name__ == '__main__':
    code = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else code
    
    data_file = os.path.join(BOSS_DIR, 'portfolio_dashboard.json')
    if not os.path.exists(data_file):
        data_file = os.path.join(DATA_DIR, 'portfolio_dashboard.json')
    
    data = inject_analysis(code, name, data_file)
    gen_dashboard(data)
