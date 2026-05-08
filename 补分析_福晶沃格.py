#!/usr/bin/env python3
"""补福晶科技和沃格光电的 StockHolmes分析、AI建议、新闻"""
import json
import os
import sys
import requests
import time
import numpy as np
from datetime import datetime

# numpy bool -> python bool 转换
class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        return super().default(obj)

sys.path.insert(0, 'src')
from fetch_kline_tencent import fetch_kline, compute_indicators

BOSS_DIR = os.path.join(os.path.dirname(__file__), 'output', 'boss')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')

TARGETS = [
    {'code': '002222', 'name': '福晶科技', 'market': 'sz'},
    {'code': '603773', 'name': '沃格光电', 'market': 'sh'},
]

def get_stockholmes_analysis(code, name, klines, tech):
    close = klines[-1]['close']
    ma5 = tech['ma5']
    ma10 = tech['ma10']
    ma20 = tech['ma20']
    ma60 = tech['ma60']
    rsi = tech['rsi']
    macd_signal = tech.get('macd_signal', '')
    vol_ratio = tech.get('vol_ratio', 1.0)
    
    if ma5 > ma10 > ma20 > ma60:
        trend = '多头排列'
        ma_align = '多头排列 MA5>MA10>MA20>MA60'
        trend_strength = 85
    elif ma5 > ma10 > ma20:
        trend = '多头排列'
        ma_align = '多头排列 MA5>MA10>MA20'
        trend_strength = 75
    elif ma5 < ma10 < ma20 < ma60:
        trend = '空头排列'
        ma_align = '空头排列 MA5<MA10<MA20<MA60'
        trend_strength = 15
    elif ma5 < ma10 < ma20:
        trend = '空头排列'
        ma_align = '空头排列 MA5<MA10<MA20'
        trend_strength = 25
    else:
        trend = '震荡整理'
        ma_align = '均线交织'
        trend_strength = 50
    
    bias5 = round((close - ma5) / ma5 * 100, 2) if ma5 else 0
    bias10 = round((close - ma10) / ma10 * 100, 2) if ma10 else 0
    bias20 = round((close - ma20) / ma20 * 100, 2) if ma20 else 0
    
    if vol_ratio > 1.5:
        vol_status = '放量'
    elif vol_ratio < 0.5:
        vol_status = '缩量'
    else:
        vol_status = '量能正常'
    
    support_ma5 = close >= ma5
    support_ma10 = close >= ma10
    
    if '金叉' in str(macd_signal):
        macd_status = '多头'
        macd_sig = '✓ MACD金叉，上涨动能增强'
    elif '死叉' in str(macd_signal):
        macd_status = '空头'
        macd_sig = '✗ MACD死叉，下跌动能增强'
    else:
        macd_status = '中性'
        macd_sig = 'MACD无明显信号'
    
    if rsi > 70:
        rsi_status = '超买'
        rsi_sig = f'⚠️ RSI超买({rsi}>70)，短期回调风险高'
    elif rsi < 30:
        rsi_status = '超卖'
        rsi_sig = f'✓ RSI超卖({rsi}<30)，可能反弹'
    elif rsi > 50:
        rsi_status = '偏强'
        rsi_sig = f'RSI偏强({rsi})，多方占优'
    else:
        rsi_status = '偏弱'
        rsi_sig = f'RSI偏弱({rsi})，空方占优'
    
    score = 50
    reasons = []
    risks = []
    
    if trend == '多头排列':
        score += 15
        reasons.append('✅ 多头排列，顺势做多')
    elif trend == '空头排列':
        score -= 15
        risks.append('⚠️ 空头排列，趋势向下')
    
    if abs(bias5) < 2:
        score += 10
        reasons.append(f'✅ 价格贴近MA5({abs(bias5)}%)，介入好时机')
    elif bias5 > 5:
        score -= 10
        risks.append(f'⚠️ 乖离率过大({bias5}%)，有回落风险')
    
    if support_ma5:
        score += 5
        reasons.append('✅ MA5支撑有效')
    
    if '金叉' in str(macd_signal):
        score += 10
        reasons.append('✅ MACD金叉确认')
    elif '死叉' in str(macd_signal):
        score -= 10
        risks.append('⚠️ MACD死叉')
    
    if rsi > 70:
        score -= 10
        risks.append(rsi_sig)
    elif rsi < 30:
        score += 10
        reasons.append('✅ RSI超卖，可能反弹')
    
    score = max(0, min(100, score))
    
    if score >= 60:
        signal = '买入'
    elif score >= 45:
        signal = '持有'
    elif score >= 35:
        signal = '观望'
    else:
        signal = '卖出'
    
    if not reasons:
        reasons.append('— 无明显信号')
    
    stockholmes = {
        'code': code,
        'trend_status': trend,
        'ma_alignment': ma_align,
        'trend_strength': trend_strength,
        'ma5': ma5,
        'ma10': ma10,
        'ma20': ma20,
        'ma60': ma60,
        'current_price': close,
        'bias_ma5': bias5,
        'bias_ma10': bias10,
        'bias_ma20': bias20,
        'volume_status': vol_status,
        'volume_ratio_5d': vol_ratio,
        'volume_trend': vol_status,
        'support_ma5': support_ma5,
        'support_ma10': support_ma10,
        'buy_signal': signal,
        'signal_score': score,
        'signal_reasons': reasons,
        'risk_factors': risks,
        'macd_status': macd_status,
        'macd_signal': macd_sig,
        'rsi_status': rsi_status,
        'rsi_signal': rsi_sig,
    }
    
    return stockholmes, score, signal

def fetch_news_eastmoney(code, name):
    try:
        url = "https://search-api-web.eastmoney.com/search/jsonp"
        params = {
            "cb": "jQuery",
            "type": "cms_news_webstock",
            "client": "web",
            "client_type": "web",
            "param": json.dumps({
                "uid": "",
                "keyword": name,
                "type": ["cms_news_webstock"],
                "range": "title",
                "pageSize": 1,
                "pageIndex": 1
            }),
        }
        resp = requests.get(url, params=params, timeout=10)
        text = resp.text
        start = text.find('(') + 1
        end = text.rfind(')')
        if start > 0 and end > start:
            data = json.loads(text[start:end])
            results = data.get('data', {}).get('list', [])
            if results:
                item = results[0]
                return {
                    'title': item.get('title', '').replace('<em>', '').replace('</em>', ''),
                    'summary': item.get('content', item.get('digest', ''))[:300].replace('<em>', '').replace('</em>', '')
                }
        return {'title': '', 'summary': ''}
    except Exception as e:
        print(f"  新闻获取失败: {e}")
        return {'title': '', 'summary': ''}

def generate_ai_analysis(name, code, stockholmes, tech, klines):
    sh_signal = stockholmes['buy_signal']
    sh_score = stockholmes['signal_score']
    trend = stockholmes['trend_status']
    rsi = tech['rsi']
    close = klines[-1]['close']
    ma20 = tech['ma20']
    
    if trend == '多头排列':
        target = round(close * 1.15, 2)
        stop = round(ma20 * 0.97, 2) if ma20 else round(close * 0.92, 2)
        confidence = '中' if sh_score < 70 else '高'
        summary = f'{trend}趋势，技术指标{sh_signal}信号，关注量能配合'
    elif trend == '空头排列':
        target = round(close * 1.05, 2)
        stop = round(close * 0.92, 2)
        confidence = '低'
        summary = f'{trend}，建议等待企稳信号，谨慎操作'
    else:
        target = round(close * 1.1, 2)
        stop = round(close * 0.93, 2)
        confidence = '中'
        summary = f'震荡格局，等待方向选择'
    
    if rsi > 70:
        summary += '；RSI偏高注意短线回调'
    elif rsi < 30:
        summary += '；RSI偏低有反弹机会'
    
    if sh_signal == '买入':
        advice = '买入'
    elif sh_signal == '持有':
        advice = '持有'
    elif sh_signal == '观望':
        advice = '观望'
    else:
        advice = '卖出'
    
    sentiment = min(95, max(20, sh_score + 10))
    
    return {
        'operation_advice': advice,
        'target_price': str(target),
        'stop_loss': str(stop),
        'confidence_level': confidence,
        'sentiment_score': sentiment,
        'analysis_summary': summary,
    }

def main():
    boss_file = os.path.join(BOSS_DIR, 'portfolio_dashboard.json')
    with open(boss_file) as f:
        boss_data = json.load(f)
    
    results = boss_data['results']
    
    for target in TARGETS:
        code = target['code']
        name = target['name']
        print(f"\n{'='*40}")
        print(f"处理 {name} ({code})")
        
        print(f"  获取K线数据...")
        klines = fetch_kline(code, days=70)
        if not klines:
            print(f"  ✗ 获取K线失败")
            continue
        print(f"  ✅ 获取 {len(klines)} 条K线")
        
        print(f"  计算技术指标...")
        tech = compute_indicators(klines)
        last_close = klines[-1]['close']
        print(f"  收盘价: {last_close} MA5: {tech['ma5']} MA10: {tech['ma10']} RSI: {tech['rsi']} trend: {tech['trend']}")
        
        print(f"  生成 StockHolmes 分析...")
        stockholmes, rule_score, rule_signal = get_stockholmes_analysis(code, name, klines, tech)
        print(f"  评分: {rule_score} 信号: {rule_signal}")
        
        print(f"  获取新闻...")
        news = fetch_news_eastmoney(code, name)
        print(f"  新闻: {news.get('title', '无')[:50]}")
        
        print(f"  生成 AI 分析...")
        ai = generate_ai_analysis(name, code, stockholmes, tech, klines)
        print(f"  建议: {ai['operation_advice']} 信心: {ai['confidence_level']}")
        
        for r in results:
            if r['code'] == code:
                r['stockholmes'] = stockholmes
                r['rule_score'] = rule_score
                r['rule_signal'] = rule_signal
                r['ai_analysis'] = ai
                r['news'] = news
                r['technical']['trend'] = stockholmes['trend_status']
                r['technical']['macd_signal'] = stockholmes['macd_status']
                r['technical']['score'] = stockholmes.get('signal_score', 50)
                print(f"  ✅ 更新 {name} 数据")
                break
        
        time.sleep(0.5)
    
    with open(boss_file, 'w') as f:
        json.dump(boss_data, f, indent=2, ensure_ascii=False, cls=NpEncoder)
    print(f"\n✅ boss/portfolio_dashboard.json 已更新")
    
    print("\n重新生成报告...")
    os.chdir(os.path.dirname(__file__))
    ret = os.system('python3 gen_dashboard_v2.py')
    if ret == 0:
        print("✅ 报告生成完成")
    else:
        print(f"❌ 报告生成失败, 返回码: {ret}")

if __name__ == '__main__':
    main()
