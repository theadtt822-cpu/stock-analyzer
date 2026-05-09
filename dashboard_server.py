#!/usr/bin/env python3.11
"""
StockHolmes 交互式持仓仪表盘服务器 v3
- 独立用户页面：/tiantian/ (天天) 和 /bobo/ (波波)
- 实时行情刷新（腾讯API，手动刷新按钮）
- 持仓/自选股在线编辑
- 自动生成个股分析报告
- 三维数据整合：财务/两融/模式识别/DeepSeek AI
- 不影响旧 report_server (8081)
"""
import json
import os
import sys
from kol_tracker import (
    fetch_realtime_quote as _fetch_quote,
    load_sources, save_sources, load_recs, save_recs, load_stats, save_stats,
    summarize_article, update_tracking_for_rec, update_all_tracking, recalc_stats,
    fetch_historical_price, DEFAULT_SOURCES,
)
import time
import glob as globmod
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# 三维报告需要的额外模块
try:
    import pywencai
except ImportError:
    pywencai = None
    print("[WARN] pywencai not installed - margin/两融 queries will fall back to empty")
import requests as _http_requests

# mx-data 路径
sys.path.insert(0, '/home/admin/.openclaw/workspace/skills/mx-data')
sys.path.insert(0, '/home/admin/.openclaw/workspace/daily_stock_analysis')
try:
    from mx_data import MXData
    _mx = MXData()
    mx_data_available = True
except Exception:
    _mx = None
    mx_data_available = False

try:
    from capital_flow import get_close_capital_flow, format_capital_report, get_stock_money_flow
    capital_flow_available = True
except Exception:
    capital_flow_available = False
    def get_stock_money_flow(code, name): return {}

from flask import Flask, jsonify, request, render_template, send_from_directory

app = Flask(__name__, template_folder='templates')

# ===== 路径配置 =====
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / 'output'

# 用户配置 - 完全独立的数据目录
USERS = {
    'tiantian': {
        'label': '天天',
        'emoji': '\U0001F451',
        'dir': OUTPUT_DIR / 'boss',
        'portfolio': OUTPUT_DIR / 'boss' / 'portfolio_dashboard.json',
        'watchlist': OUTPUT_DIR / 'boss' / 'watchlist.json',
    },
    'bobo': {
        'label': '波波',
        'emoji': '\U0001F491',
        'dir': OUTPUT_DIR / 'boyfriend',
        'portfolio': OUTPUT_DIR / 'boyfriend' / 'portfolio_dashboard.json',
        'watchlist': OUTPUT_DIR / 'boyfriend' / 'watchlist.json',
    },
}


def get_market_prefix(code):
    code = str(code).strip()
    return 'sh' if code.startswith('6') else 'sz'


def fetch_realtime_quote(codes):
    if not codes:
        return {}
    query_parts = [f"{get_market_prefix(c)}{c}" for c in codes]
    url = f"https://qt.gtimg.cn/q={','.join(query_parts)}"
    try:
        req = urllib.request.Request(url)
        req.add_header('Referer', 'https://finance.qq.com/')
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode('gbk')
    except Exception as e:
        print(f"[quote error] {e}")
        return {}

    results = {}
    for line in data.strip().split('\n'):
        if '=' not in line:
            continue
        p = line.split('~')
        if len(p) < 50:
            continue
        code = p[2]
        # 5档盘口: buy1_price/buy1_vol @ p[9]/p[10] ... sell1_price/sell1_vol @ p[19]/p[20]
        bids = []
        for i in range(5):
            price = float(p[9 + i*2]) if len(p) > 9 + i*2 and p[9 + i*2] else 0
            volume = int(p[10 + i*2]) if len(p) > 10 + i*2 and p[10 + i*2] else 0
            bids.append({'price': price, 'volume': volume})
        asks = []
        for i in range(5):
            price = float(p[19 + i*2]) if len(p) > 19 + i*2 and p[19 + i*2] else 0
            volume = int(p[20 + i*2]) if len(p) > 20 + i*2 and p[20 + i*2] else 0
            asks.append({'price': price, 'volume': volume})
        results[code] = {
            'name': p[1],
            'price': float(p[3]) if p[3] else 0,
            'prev_close': float(p[4]) if p[4] else 0,
            'open': float(p[5]) if p[5] else 0,
            'high': float(p[33]) if len(p) > 33 and p[33] else 0,
            'low': float(p[34]) if len(p) > 34 and p[34] else 0,
            'volume': int(p[6]) if len(p) > 6 and p[6] else 0,
            'change_pct': float(p[32]) if len(p) > 32 and p[32] else 0,
            'update_time': p[30] if len(p) > 30 else '',
            'bids': bids,  # 买5档
            'asks': asks,  # 卖5档
            'turnover': float(p[38]) if len(p) > 38 and p[38] else 0,        # 换手率%
            'amount_wan': float(p[36]) if len(p) > 36 and p[36] else 0,       # 成交额(万)
        }
    return results


def fetch_money_flow(code, name=""):
    """从 mx-xuangu 获取主力资金流向数据（替代已失效的东方财富push2 API）"""
    if not name or not capital_flow_available:
        return {}
    try:
        result = get_stock_money_flow(code, name)
        return result  # returns {"zhu_li_net": 万元, ...}
    except Exception as e:
        print(f"[money flow error {code}] {e}")
        return {}


def fetch_kline_tencent(code, days=70):
    market = get_market_prefix(code)
    full = f"{market}{code}"
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={full},day,{start},{end},{days},qfq"
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        req.add_header('Referer', 'https://stockapp.finance.qq.com/')
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        sd = data.get('data', {}).get(full, {})
        klines = sd.get('qfqday', sd.get('day', []))
        return [{'date': k[0], 'open': float(k[1]), 'close': float(k[2]),
                 'high': float(k[3]), 'low': float(k[4]), 'volume': float(k[5])} for k in klines]
    except Exception as e:
        print(f"[kline error {code}] {e}")
        return []


def compute_indicators(klines):
    import pandas as pd
    if len(klines) < 60:
        return None
    df = pd.DataFrame(klines)
    closes = df['close']
    volumes = df['volume']
    ma5 = round(closes.tail(5).mean(), 2)
    ma10 = round(closes.tail(10).mean(), 2)
    ma20 = round(closes.tail(20).mean(), 2)
    ma60 = round(closes.tail(60).mean(), 2)
    ema12 = closes.ewm(span=12).mean()
    ema26 = closes.ewm(span=26).mean()
    dif = round(ema12.iloc[-1] - ema26.iloc[-1], 2)
    dea = round((ema12 - ema26).ewm(span=9).mean().iloc[-1], 2)
    macd_bar = round(2 * (dif - dea), 3)
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).tail(14).mean()
    loss = (-delta.where(delta < 0, 0)).tail(14).mean()
    rs = gain / loss if loss != 0 else 100
    rsi = round(100 - (100 / (1 + rs)), 1)
    vol_5avg = volumes.tail(5).mean()
    vol_ratio = round(volumes.iloc[-1] / vol_5avg, 2) if vol_5avg > 0 else 1.0
    change_5d = round((closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100, 2) if len(closes) >= 6 else 0
    high_20 = round(closes.tail(20).max(), 2)
    low_20 = round(closes.tail(20).min(), 2)
    last = closes.iloc[-1]
    if ma5 > ma10 > ma20:
        trend = '多头排列'
    elif ma5 < ma10 < ma20:
        trend = '空头排列'
    elif ma5 < ma10:
        trend = 'MA5回落'
    else:
        trend = '震荡'
    bias5 = round((last - ma5) / ma5 * 100, 2)
    bias20 = round((last - ma20) / ma20 * 100, 2)
    return {
        'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60,
        'dif': dif, 'dea': dea, 'macd_bar': macd_bar,
        'macd_signal': '金叉' if macd_bar > 0 else '死叉',
        'rsi': rsi, 'vol_ratio': vol_ratio, 'change_5d': change_5d,
        'high_20': high_20, 'low_20': low_20,
        'tushare_close': round(last, 2), 'trend': trend,
        'bias5': bias5, 'bias20': bias20,
    }


def stockholmes_rules(
    tech, money_flow=None, order_book=None,
    financial=None, pattern=None, turnover=None, amount_wan=None, day_change=None,
):
    """多因子波段评分系统（v2）

    五大因子：趋势(25) + 资金(20) + 量价(20) + 估值(15) + 技术形(20) = 100
    基准50分，范围0~100
    """
    if not tech:
        return {'buy_signal': '数据不足', 'signal_score': 0,
                'signal_reasons': [], 'risk_factors': [],
                'ma_alignment': '', 'macd_status': '', 'rsi_status': ''}

    score = 50
    reasons, risks = [], []

    def _add(v, reason, risk):
        nonlocal score
        if v > 0: score += v; reasons.append(reason)
        elif v < 0: score += v; risks.append(risk)

    # ====== 因子1: 趋势因子 (max +/-25) ======

    # 1a. 均线排列 +/-10
    ma5, ma10, ma20 = tech.get('ma5'), tech.get('ma10'), tech.get('ma20')
    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:
            _add(10, '多头排列，顺势做多', '')
            ma_align = '多头排列 MA5>MA10>MA20'
        elif ma5 < ma10 < ma20:
            _add(-10, '', '空头排列，趋势向下')
            ma_align = '空头排列 MA5<MA10<MA20'
        else:
            ma_align = '均线交织，方向不明'
            if ma5 > ma10 and ma10 < ma20:
                _add(3, '短线上穿中期，转多信号', '')
            elif ma5 < ma10 and ma10 > ma20:
                _add(-3, '', '短线破位中期，转空信号')
            else:
                _add(-2, '', '均线交织，方向不明')
    else:
        ma_align = '数据不足'

    # 1b. MACD评分 +/-8（零轴附近金叉最重要）
    ms = tech.get('macd_signal', '')
    dif = tech.get('dif', 0)
    if ms == '金叉':
        _add(8 if abs(dif) < 1 else 5, '零轴附近金叉' if abs(dif)<1 else 'MACD金叉', '')
    elif ms == '死叉':
        _add(-8 if abs(dif) < 1 else -6, '', '零轴附近死叉' if abs(dif)<1 else 'MACD死叉')

    # 1c. 趋势方向 +/-7
    trend = tech.get('trend', '震荡')
    if trend == '上升': _add(5, '中期趋势向上', '')
    elif trend == '下跌': _add(-5, '', '中期趋势向下')

    high20 = tech.get('high_20')
    low20 = tech.get('low_20')
    price = tech.get('close', tech.get('current', 0))
    if high20 and low20 and price and high20 > low20:
        rp = (price - low20) / (high20 - low20) * 100
        if rp > 80: _add(3, f'价格位于20日区间上沿({rp:.0f}%)，突破迹象', '')
        elif rp < 20: _add(-3, '', f'价格位于20日区间下沿({rp:.0f}%)，弱势')

    # ====== 因子2: 资金因子 (max +/-20) ======

    if money_flow and money_flow.get('zhu_li_net') is not None:
        zln = money_flow.get('zhu_li_net', 0)
        px = tech.get('close', tech.get('current', 50)) or 50
        sc = max(1, px / 50)
        th_h = int(1000 * sc)
        th_l = int(200 * sc)
        if zln > th_h:
            _add(10, f'主力大幅净流入({zln:.0f}万)，大资金进场', ''); mf_text = '主力大幅净流入'
        elif zln > th_l:
            _add(5, f'主力净流入({zln:.0f}万)', ''); mf_text = '主力净流入'
        elif zln < -th_h:
            _add(-10, '', f'主力大幅净流出({zln:.0f}万)，大资金离场'); mf_text = '主力大幅净流出'
        elif zln < -th_l:
            _add(-5, '', f'主力净流出({zln:.0f}万)'); mf_text = '主力净流出'
        else: mf_text = '资金平衡'
    else: mf_text = '暂无数据'

    # 盘口评分 +/-10
    ob_text = ''
    if order_book and order_book.get('bids') and order_book.get('asks'):
        bids = [b for b in order_book['bids'] if b and b.get('price', 0) > 0]
        asks = [a for a in order_book['asks'] if a and a.get('price', 0) > 0]
        if bids and asks:
            ratio = sum(int(b.get('volume',0)) for b in bids) / max(sum(int(a.get('volume',0)) for a in asks), 1)
            if ratio > 2: _add(8, f'买盘堆积(买/卖={ratio:.1f}倍)，支撑强劲', ''); ob_text = '买盘强势'
            elif ratio > 1.3: _add(4, f'买盘占优(买/卖={ratio:.1f}倍)', ''); ob_text = '买盘占优'
            elif ratio < 0.5: _add(-8, '', f'卖盘堆积(买/卖={ratio:.1f}倍)，抛压较重'); ob_text = '卖盘强势'
            elif ratio < 0.8: _add(-4, '', f'卖盘占优(买/卖={ratio:.1f}倍)'); ob_text = '卖盘占优'
            else: ob_text = '买卖均衡'

    # ====== 因子3: 量价配合 (max +/-20) ======

    vr = tech.get('vol_ratio', 1)
    dc = day_change or tech.get('day_change', 0) or 0
    if vr > 1.5 and dc > 2: _add(8, f'放量上涨(量比{vr:.1f} 涨幅{dc:+.1f}%)，量价配合好', '')
    elif vr > 1.5 and dc < -2: _add(-8, '', f'放量下跌(量比{vr:.1f} 涨幅{dc:+.1f}%)，抛压大')
    elif vr < 0.5 and dc > 1: _add(-3, '', f'缩量上涨(量比{vr:.1f})，上涨无量')
    elif vr < 0.5 and dc < -1: _add(3, f'缩量下跌(量比{vr:.1f})，抛压衰竭', '')
    elif vr > 1.5: _add(3, f'放量(量比{vr:.1f})，资金活跃', '')
    elif vr < 0.5: _add(-2, '', f'缩量(量比{vr:.1f})，交投清淡')

    to = turnover or tech.get('turnover', 0)
    if to:
        try:
            tf = float(to)
            if tf > 10: _add(-3, '', f'换手{tf:.1f}%过高，投机过热')
            elif tf > 5: _add(3, f'换手{tf:.1f}%活跃，交投活跃', '')
            elif tf > 2: _add(2, f'换手{tf:.1f}%适中', '')
        except: pass

    amt = amount_wan or tech.get('amount_wan', 0)
    if amt:
        try:
            af = float(amt)
            if af > 500000: _add(3, f'大成交{af/10000:.0f}亿', '')
            elif af > 200000: _add(2, f'成交{af/10000:.0f}亿', '')
        except: pass

    # ====== 因子4: 估值因子 (max +/-15) ======

    if financial:
        pe, pb, roe = financial.get('pe'), financial.get('pb'), financial.get('roe')
        if pe is not None and pe != '--' and pe != 0:
            try:
                pf = float(pe)
                if pf < 0: _add(-5, '', f'PE为负({pf:.0f})，企业亏损')
                elif pf > 100: _add(-3, '', f'PE{pf:.0f}偏高，估值压力大')
                elif 10 <= pf <= 30: _add(4, f'PE{pf:.0f}合理估值适中', '')
                elif pf < 10: _add(5, f'PE{pf:.0f}<10价值洼地', '')
                else: _add(-1, '', f'PE{pf:.0f}偏高')
            except: pass
        if roe is not None and roe != '--':
            try:
                rf = float(roe)
                if rf > 30: _add(6, f'ROE{rf:.1f}%盈利极优秀', '')
                elif rf > 15: _add(5, f'ROE{rf:.1f}%盈利良好', '')
                elif rf > 8: _add(3, f'ROE{rf:.1f}%盈利尚可', '')
                elif rf < 0: _add(-4, '', f'ROE{rf:.1f}%为负企业亏损')
                else: _add(-1, '', f'ROE{rf:.1f}%偏低')
            except: pass
        if pb is not None and pb != '--':
            try:
                bf = float(pb)
                if bf > 10: _add(-3, '', f'PB{bf:.1f}过高')
                elif bf < 1: _add(3, f'PB{bf:.2f}<1破净安全边际', '')
            except: pass

    # ====== 因子5: 技术形态 (max +/-20) ======

    if pattern:
        if pattern.get('head_and_shoulders_top'): _add(-10, '', '头肩顶形态，见顶风险')
        if pattern.get('double_top'): _add(-8, '', 'M顶形态，阻力强')
        if pattern.get('double_bottom'): _add(10, '双底形态，底部确认', '')
        if pattern.get('head_and_shoulders_bottom'): _add(8, '头肩底形态', '')
        if pattern.get('falling_wedge'): _add(6, '下降楔形可能翻转向上', '')
        if pattern.get('rising_wedge'): _add(-6, '', '上升楔形可能翻转下跌')
        if pattern.get('flag') or pattern.get('bull_flag'): _add(5, '旗形整理蓄力突破', '')
        if pattern.get('bear_flag'): _add(-5, '', '下跌旗形弱势持续')

    rsi = tech.get('rsi', 50)
    if rsi > 70: _add(-5, '', f'RSI超买({rsi:.0f}>70)')
    elif rsi < 30: _add(5, f'RSI超卖({rsi:.0f}<30)可能反弹', '')
    elif rsi > 60: _add(2, f'RSI{rsi:.0f}偏强', '')
    elif rsi < 40: _add(-2, '', f'RSI{rsi:.0f}偏弱')

    bias5 = tech.get('bias5', 0)
    if abs(bias5) <= 2: _add(3, f'价格贴近MA5(乖离{abs(bias5):.1f}%)', '')
    elif bias5 > 5: _add(-4, '', f'偏离MA5过远({bias5:.1f}%)')
    elif bias5 < -5: _add(3, f'负乖离{bias5:.1f}%超跌', '')

    # --- 总分 ---
    score = max(0, min(100, score))
    if score >= 70: bs = '买入'
    elif score >= 55: bs = '持有'
    elif score >= 40: bs = '观望'
    else: bs = '卖出'

    return {
        'buy_signal': bs, 'signal_score': score,
        'signal_reasons': reasons, 'risk_factors': risks,
        'ma_alignment': ma_align,
        'macd_status': '金叉看涨' if ms == '金叉' else ('死叉看跌' if ms == '死叉' else '待确认'),
        'rsi_status': '超买' if rsi > 70 else ('超卖' if rsi < 30 else ('偏强' if rsi > 50 else '偏弱')),
        'money_flow_status': mf_text,
        'order_book_status': ob_text,
    }

def generate_ai_analysis(code, name, tech, quote, money_flow=None, order_book=None):
    """调用本地 LLM 生成 AI 技术分析"""
    if not tech:
        return {}
    close = quote.get('price', tech.get('tushare_close', 0))
    prev_close = quote.get('prev_close', 0)
    chg_pct = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0

    # 资金流向文本
    mf_text = ''
    if money_flow:
        mf_text = f"""
资金流向（万元）：
- 主力净流入: {money_flow.get('zhu_li_net',0):+.0f} 万 (超大单 {money_flow.get('chao_da_net',0):+.0f} / 大单 {money_flow.get('da_net',0):+.0f})
- 中单净流入: {money_flow.get('zhong_net',0):+.0f} 万
- 小单净流入: {money_flow.get('xiao_net',0):+.0f} 万"""
    # 盘口文本
    ob_text = ''
    if order_book and order_book.get('bids') and order_book.get('asks'):
        bids = order_book['bids']
        asks = order_book['asks']
        bid_str = ' / '.join([f"{b['price']:.2f}({b['volume']}手)" for b in bids if b['price'] > 0])
        ask_str = ' / '.join([f"{a['price']:.2f}({a['volume']}手)" for a in asks if a['price'] > 0])
        ob_text = f"""
5档盘口：
- 买盘: {bid_str}
- 卖盘: {ask_str}"""

    prompt = f"""你是专业A股技术分析师。请对以下股票技术面进行综合研判，返回JSON格式结果。

股票：{name}（{code}）
技术指标数据：
- 现价: {close:.2f} ({chg_pct:+.2f}%)
- 均线: MA5={tech.get("ma5",0):.2f}, MA10={tech.get("ma10",0):.2f}, MA20={tech.get("ma20",0):.2f}, MA60={tech.get("ma60",0):.2f}
- MACD: DIF={tech.get("dif",0):.2f}, DEA={tech.get("dea",0):.2f}
- RSI(14): {tech.get("rsi",50):.1f}
- 量比: {tech.get("vol_ratio",1):.1f}
- 趋势: {tech.get("trend","震荡")}{mf_text}{ob_text}

请返回JSON（不要有其他文字）：
{{\"operation_advice\":\"买入/增持/持有/观望/减仓/卖出\",\"sentiment_score\":0-100整数,\"analysis_summary\":\"核心研判，40-60字，含多空逻辑及关键技术依据\",\"target_price\":数字,\"stop_loss\":数字,\"confidence_level\":\"高/中/低\"}}"""

    try:
        import requests as _req
        resp = _req.post(
            "http://localhost:15126/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer a425fdf94a7567401179a00d3eade5e2"
            },
            json={
                "model": "openclaw",
                "messages": [
                    {"role": "system", "content": "你是专业的A股技术分析师。请严格返回JSON格式，不要有其他文字。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            },
            timeout=120
        )
        data = resp.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        content = content.strip()
        if content.startswith('```'):
            parts = content.split('```')
            content = parts[1] if len(parts) > 1 else content
            if content.startswith('json'):
                content = content[4:]
        import json as _json
        ai_result = _json.loads(content)

        advice_map = {
            '买入': '买入', '增持': '买入', '持有': '持有',
            '观望': '观望', '减仓': '卖出', '卖出': '卖出'
        }
        operation = advice_map.get(ai_result.get('operation_advice', '观望'), '观望')
        sentiment = ai_result.get('sentiment_score', 50)

        return {
            'operation_advice': operation,
            'sentiment_score': sentiment,
            'analysis_summary': ai_result.get('analysis_summary', 'AI分析完成'),
            'target_price': str(ai_result.get('target_price', close)),
            'stop_loss': str(ai_result.get('stop_loss', close * 0.95)),
            'confidence_level': ai_result.get('confidence_level', '中'),
        }
    except Exception as e:
        print(f"[AI analyze error {code}] {type(e).__name__}: {e}")
        return {}


# ===== 新增：三维数据获取函数 =====

def fetch_financial_data(code, name):
    """获取 PE/PB/ROE 财务指标"""
    result = {'pe': '', 'pb': '', 'roe': ''}
    if mx_data_available and _mx:
        try:
            r = _mx.query(f'{name} 市盈率 市净率 ROE')
            tables = r.get('data',{}).get('data',{}).get('searchDataResultDTO',{}).get('dataTableDTOList',[])
            for dto in tables:
                tbl = dto.get('table', {})
                pe = tbl.get('328664', [''])[0] or tbl.get('f23', [''])[0]
                pb = tbl.get('328773', [''])[0] or tbl.get('f24', [''])[0]
                roe = tbl.get('100000000003466', [''])[0] or tbl.get('f129', [''])[0]
                if pe: result['pe'] = str(pe)[:20]
                if pb: result['pb'] = str(pb)[:20]
                if roe: result['roe'] = str(roe)[:20]
                if any([pe, pb, roe]):
                    break
        except Exception:
            pass
    # 回退到 pywencai
    if not any(result.values()):
        try:
            r = pywencai.get(query=f'{code} 市盈率 市净率 ROE', query_type='stock', perpage=1)
            tbl = r.get('tableV1')
            if tbl is not None and hasattr(tbl, 'to_dict'):
                rows = tbl.to_dict('records')
                if rows:
                    row = rows[0]
                    if not result['pe']: result['pe'] = str(row.get('pe_ttm', ''))
                    if not result['pb']: result['pb'] = str(row.get('市净率', ''))
                    if not result['roe']: result['roe'] = str(row.get('加权roe', ''))
        except Exception:
            pass
    return result


def fetch_margin_data(code, name):
    """获取两融数据（pywencai）"""
    if pywencai is None:
        return None  # pywencai not installed
    try:
        mkt = "sz" if code.startswith(("0","3")) else "sh"
        r = pywencai.get(query=f'{mkt}{code} 融资融券 融资余额 融券余额', query_type='stock', perpage=1)
        tbl = r.get('tableV1')
        if tbl is not None and hasattr(tbl, 'to_dict'):
            rows = tbl.to_dict('records')
            if rows:
                row = rows[0]
                def _to_num(v):
                    try: return float(v)
                    except: return 0.0
                return {
                    "融资余额": _to_num(row.get("融资余额", 0)),
                    "融券余额": _to_num(row.get("融券余额", 0)),
                    "融资买入额": _to_num(row.get("融资买入额", 0)),
                    "融资偿还额": _to_num(row.get("融资偿还额", 0)),
                    "融资余额增速": _to_num(row.get("融资余额增速", 0)),
                    "融资融券余额": _to_num(row.get("融资融券余额", 0)),
                }
    except Exception:
        pass
    return None


def _calc_rsi_for_pattern(cl):
    if len(cl) < 15:
        return 50
    g, l = [], []
    for i in range(1, len(cl)):
        d = cl[i] - cl[i-1]
        g.append(d if d > 0 else 0)
        l.append(-d if d < 0 else 0)
    ag = sum(g[-14:]) / 14
    al = sum(l[-14:]) / 14
    if al == 0:
        return 100
    return 100 - 100 / (1 + ag / al)


def run_pattern_recognition(code, closes):
    """对单只股票做历史模式识别"""
    if len(closes) < 30:
        return None
    
    def ma(data, period):
        if len(data) < period:
            return data[-1]
        return sum(data[-period:]) / period
    
    cur_price = closes[-1]
    cur_ma5 = ma(closes, 5)
    cur_ma10 = ma(closes, 10)
    cur_ma20 = ma(closes, 20)
    cur_rsi = _calc_rsi_for_pattern(closes)
    cur_rsi_zone = '超买' if cur_rsi > 70 else ('超卖' if cur_rsi < 30 else '中性')
    cur_trend = '上升' if cur_price > cur_ma20 else '下降'
    cur_macd = '金叉' if cur_ma5 > cur_ma10 else '死叉'
    
    similar_5d, similar_10d = [], []
    for idx in range(20, len(closes) - 11):
        h_rsi = _calc_rsi_for_pattern(closes[:idx+1])
        h_ma5 = ma(closes[:idx+1], 5)
        h_ma10 = ma(closes[:idx+1], 10)
        h_ma20 = ma(closes[:idx+1], 20)
        h_price = closes[idx]
        h_rsi_zone = '超买' if h_rsi > 70 else ('超卖' if h_rsi < 30 else '中性')
        h_trend = '上升' if h_price > h_ma20 else '下降'
        h_macd = '金叉' if h_ma5 > h_ma10 else '死叉'
        if h_rsi_zone == cur_rsi_zone and h_trend == cur_trend and h_macd == cur_macd:
            similar_5d.append((closes[idx+5] - closes[idx]) / closes[idx] * 100)
            similar_10d.append((closes[idx+10] - closes[idx]) / closes[idx] * 100)
    
    # 放宽匹配
    if len(similar_5d) < 3:
        for idx in range(20, len(closes) - 11):
            h_rsi = _calc_rsi_for_pattern(closes[:idx+1])
            h_price = closes[idx]
            h_ma20 = ma(closes[:idx+1], 20)
            h_rsi_zone = '超买' if h_rsi > 70 else ('超卖' if h_rsi < 30 else '中性')
            h_trend = '上升' if h_price > h_ma20 else '下降'
            if h_rsi_zone == cur_rsi_zone and h_trend == cur_trend:
                similar_5d.append((closes[idx+5] - closes[idx]) / closes[idx] * 100)
                similar_10d.append((closes[idx+10] - closes[idx]) / closes[idx] * 100)
    
    if similar_5d:
        avg_5 = sum(similar_5d) / len(similar_5d)
        avg_10 = sum(similar_10d) / len(similar_10d)
        win_5 = sum(1 for r in similar_5d if r > 0) / len(similar_5d) * 100
        win_10 = sum(1 for r in similar_10d if r > 0) / len(similar_10d) * 100
        return {
            "rsi": round(cur_rsi, 1),
            "rsi_zone": cur_rsi_zone,
            "trend": cur_trend,
            "macd": cur_macd,
            "ma5": round(cur_ma5, 2),
            "ma10": round(cur_ma10, 2),
            "ma20": round(cur_ma20, 2),
            "sample_5d": len(similar_5d),
            "avg_5d": round(avg_5, 2),
            "win_5d": round(win_5, 1),
            "sample_10d": len(similar_10d),
            "avg_10d": round(avg_10, 2),
            "win_10d": round(win_10, 1),
        }
    return None


def generate_deepseek_ai_batch(results_batch):
    """用 DeepSeek API 批量生成 AI 分析（替换本地 LLM）"""
    if not results_batch:
        return []
    # 构造输入
    # 构造输入
    sd = ""
    for i, r in enumerate(results_batch):
        code = r.get("code", "")
        name = r.get("name", "")
        sector = r.get("sector", "")
        price = r.get("current", 0) or r.get("price", 0)
        day_c = r.get("day_change", 0) or 0
        cost = r.get("cost", 0)
        pnl_pct = r.get("pnl_pct", 0)
        tech = r.get("technical", {})
        mf = r.get("money_flow", {})
        fin = r.get("financial", {})
        pat = r.get("pattern", {})
        rsi = tech.get("rsi", 50)
        macd_s = tech.get("macd_signal", "待确认")
        dif = tech.get("dif", 0)
        trend = tech.get("trend", "震荡")
        vr = tech.get("vol_ratio", 1)
        zln = mf.get("zhu_li_net", 0)
        # 新增数据字段
        ma5 = tech.get("ma5", "")
        ma10 = tech.get("ma10", "")
        ma20 = tech.get("ma20", "")
        to = tech.get("turnover", r.get("turnover", ""))
        amt = tech.get("amount_wan", r.get("amount_wan", ""))
        h20 = tech.get("high_20", "")
        l20 = tech.get("low_20", "")
        pe = fin.get("pe", "") if fin else ""
        pb = fin.get("pb", "") if fin else ""
        roe = fin.get("roe", "") if fin else ""
        pat_str = ""
        if pat:
            for k,v in [("head_and_shoulders_top","头肩顶"),("double_bottom","双底"),("double_top","M顶"),("falling_wedge","下降楔形"),("bull_flag","多头旗形")]:
                if pat.get(k): pat_str += v + " "
        sd += f'{i+1}. {name}({code}) {sector} 现{price:.2f}({day_c:+.1f}%) '
        sd += f'本{cost:.2f}(盈亏{pnl_pct:+.1f}%) RSI:{rsi:.0f} {macd_s}(DIF{dif:.1f}) {trend} '
        sd += f'量比{vr:.1f} 换手{to}% 成交{amt}万 主力{zln:.0f}万 '
        sd += f'MA5:{ma5} MA10:{ma10} MA20:{ma20} 20高:{h20} 20低:{l20} '
        sd += f'PE:{pe} PB:{pb} ROE:{roe}% 形态:{pat_str}\n'

    try:
        resp = _http_requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer sk-c6e0a0f9b7554680b1c4d81e2e5324e2"
            },
            json={
                "model": "deepseek-v4-flash",
                "messages": [
                    {"role": "system", "content": "A股分析师。输出JSON数组。"},
                    {'role': 'user', 'content': f'持仓数据：\n{sd}\n\n分析每只股票技术面、资金面、估值面。\n返回JSON数组，每个元素：{{"name":"股票名","advice":"持有/观望/减仓/卖出","sentiment":0-100,"summary":"15字观点","detailed":"30-50字分析","target":目标价,"stop":止损价,"confidence":"高/中/低"}}\n只返回JSON。',}
                ],
                "temperature": 0.3,
                "max_tokens": 4000
            },
            timeout=180
        )
        content = resp.json().get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        if content.startswith('```'):
            parts = content.split('```')
            content = parts[1] if len(parts) > 1 else content
            if content.startswith('json'):
                content = content[4:]
        ai_r = json.loads(content)
        results = []
        for ai in ai_r:
            results.append({
                'advice': ai.get('advice', '观望'),
                'sentiment': ai.get('sentiment', 50),
                'summary': ai.get('summary', ''),
                'detailed': ai.get('detailed', ''),
                'target': ai.get('target', 0),
                'stop': ai.get('stop', 0),
                'confidence': ai.get('confidence', '中'),
            })
        return results
    except Exception as e:
        print(f'[DeepSeek AI error] {e}')
        return []
def load_json(user_key, key):
    cfg = USERS[user_key]
    path = cfg[key]
    if path.exists():
        with open(path) as f:
            return json.load(f)
    if key == 'portfolio':
        return {'results': [], 'total_cost': 0, 'total_value': 0, 'total_pnl': 0, 'total_pnl_pct': 0}
    return {'groups': [{'name': '默认', 'stocks': []}]}


def save_json(user_key, key, data):
    cfg = USERS[user_key]
    cfg['dir'].mkdir(parents=True, exist_ok=True)
    with open(cfg[key], 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_report_exists(code, name, user_key=None):
    today = datetime.now().strftime("%Y%m%d")
    market = get_market_prefix(code)
    pattern = f"{market}{code}_{name}_report_{today}_*.html"
    dirs_to_check = [USERS[user_key]['dir']] if user_key and user_key in USERS else [OUTPUT_DIR]
    for d in dirs_to_check:
        if d.exists() and globmod.glob(str(d / pattern)):
            return True
    return False


def fetch_sector_analysis(sector_name):
    """获取板块行情分析数据"""
    if not sector_name or sector_name.strip() == '':
        return None
    try:
        # 获取行业板块列表
        url = 'https://push2.eastmoney.com/api/qt/clist/get?cb=jQuery&pn=1&pz=300&po=1&np=1&fields=f2,f3,f4,f12,f14&fs=m:90+t:2&ut=bd1d9ddb04089700cf9c27f6f7426281'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'})
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read().decode('utf-8')
        start = text.find('(') + 1
        end = text.rfind(')')
        data = json.loads(text[start:end])
        items = data.get('data', {}).get('diff', [])
        matched = []
        for item in items:
            name = item.get('f14', '')
            if sector_name in name or name in sector_name:
                chg_raw = item.get('f3', 0)
                price_raw = item.get('f2', 0)
                matched.append({
                    'name': name,
                    'code': item.get('f12', ''),
                    'price': price_raw / 100 if price_raw > 1000 else price_raw,
                    'chg_pct': chg_raw / 100 if abs(chg_raw) > 50 else chg_raw,
                    'vol_ratio': item.get('f4', 0) / 100 if abs(item.get('f4', 0)) > 50 else item.get('f4', 0),
                })
        return matched if matched else None
    except Exception as e:
        print(f'[sector fetch error {sector_name}] {e}')
        return None


def fetch_report_news(code, name, count=3):
    """获取个股最新资讯"""
    news_list = []
    try:
        param_json = urllib.parse.quote(json.dumps({
            'uid': '', 'keyword': name,
            'type': ['cmsArticle'], 'range': 'title',
            'pageSize': count, 'pageIndex': 1
        }, ensure_ascii=True))
        url = f'https://search-api-web.eastmoney.com/search/jsonp?cb=jQuery&type=cmsArticle&client=web&param={param_json}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read().decode('utf-8')
        start = text.find('(') + 1
        end = text.rfind(')')
        data = json.loads(text[start:end])
        articles = data.get('result', {}).get('cmsArticle', [])
        for a in articles:
            title = a.get('title', '').replace('<em>', '').replace('</em>', '')
            pub_date = a.get('date', '')
            news_list.append({
                'title': title,
                'source': a.get('mediaName', '东方财富'),
                'date': pub_date,
                'content': a.get('content', '').replace('<em>', '').replace('</em>', '')[:150],
            })
        return news_list if news_list else None
    except Exception as e:
        print(f'[news fetch error {code}] {e}')
        return None


def generate_report_html(code, name, tech, quote, sh, ai, user_key=None, sector=None, sector_data=None, news_data=None):
    market = get_market_prefix(code)
    now = datetime.now()
    filename = f"{market}{code}_{name}_report_{now.strftime('%Y%m%d_%H%M')}.html"

    price = quote.get('price', 0)
    prev_close = quote.get('prev_close', 0)
    chg = quote.get('change_pct', 0)
    is_up = chg >= 0
    chg_color = '#DC143C' if is_up else '#008000'
    chg_arrow = '▲' if is_up else '▼'
    chg_sign = '+' if is_up else ''

    td = tech or {}
    sd = sh or {}

    sh_score = sd.get('signal_score', 50)
    ai_score = ai.get('sentiment_score', 50) if ai else 50
    sh_signal = sd.get('buy_signal', '观望')
    ai_signal = ai.get('operation_advice', '观望') if ai else '观望'
    ai_summary = ai.get('analysis_summary', '') if ai else ''

    def score_color(s):
        if s >= 75: return '#DC143C'
        if s >= 60: return '#E8555A'
        if s >= 45: return '#888'
        if s >= 30: return '#2E8B57'
        return '#008000'

    # 技术指标解读
    rows = []
    ms = td.get('macd_signal', '')
    rows.append((
        f'<div class="indicator-row"><span class="ind-name">MACD</span>'
        f'<span class="ind-value">DIF {td.get("dif","--")} DEA {td.get("dea","--")} 柱{td.get("macd_bar","--")}</span>'
        f'<span class="ind-status {"status-red" if ms=="金叉" else "status-green" if ms=="死叉" else "status-gray"}">{"金叉看涨" if ms=="金叉" else "死叉看跌" if ms=="死叉" else "待确认"}</span>'
        f'<span class="ind-desc">{"MACD金叉，上涨动能增强" if ms=="金叉" else "MACD死叉，下跌动能仍在" if ms=="死叉" else "MACD处于平滑期"}</span></div>'
    ))
    rsi = td.get('rsi', 50)
    rsi_status = 'RSI超买' if rsi > 70 else 'RSI超卖' if rsi < 30 else ('RSI偏强' if rsi > 50 else 'RSI偏弱')
    rsi_color = 'status-red' if rsi > 70 else 'status-green' if rsi < 30 else 'status-orange' if rsi > 50 else 'status-gray'
    rows.append((
        f'<div class="indicator-row"><span class="ind-name">RSI</span>'
        f'<span class="ind-value">值 {rsi}</span>'
        f'<span class="ind-status {rsi_color}">{rsi_status}</span>'
        f'<span class="ind-desc">{"短期超买，有回调风险" if rsi > 70 else "短期超卖，可能触底反弹" if rsi < 30 else "处于中性区域"}</span></div>'
    ))
    trend_label = td.get('trend', '震荡')
    trend_color = 'status-red' if trend_label == '多头排列' else 'status-green' if trend_label == '空头排列' else 'status-orange'
    rows.append((
        f'<div class="indicator-row"><span class="ind-name">均线</span>'
        f'<span class="ind-value">MA5 {td.get("ma5","--")} MA10 {td.get("ma10","--")} MA20 {td.get("ma20","--")}</span>'
        f'<span class="ind-status {trend_color}">{trend_label}</span>'
        f'<span class="ind-desc">{"短期均线多头排列，趋势向好" if trend_label=="多头排列" else "短期均线空头排列，趋势偏弱" if trend_label=="空头排列" else "均线交织，方向不明"}</span></div>'
    ))
    vr = td.get('vol_ratio', 1)
    vr_status = '放量' if vr > 1.5 else '缩量' if vr < 0.5 else '正常'
    vr_color = 'status-red' if vr > 1.5 else 'status-green' if vr < 0.5 else 'status-gray'
    rows.append((
        f'<div class="indicator-row"><span class="ind-name">量能</span>'
        f'<span class="ind-value">量比 {vr}</span>'
        f'<span class="ind-status {vr_color}">{vr_status}</span>'
        f'<span class="ind-desc">{"成交量放大，资金活跃" if vr > 1.5 else "成交量萎缩，交投清淡" if vr < 0.5 else "成交量正常"}</span></div>'
    ))
    b5 = td.get('bias5', 0)
    b5_status = '偏离过大' if abs(b5) > 5 else '正常'
    b5_color = 'status-orange' if abs(b5) > 5 else 'status-gray'
    rows.append((
        f'<div class="indicator-row"><span class="ind-name">乖离</span>'
        f'<span class="ind-value">MA5乖离 {b5}%</span>'
        f'<span class="ind-status {b5_color}">{b5_status}</span>'
        f'<span class="ind-desc">{"股价偏离MA5较远，有回归需求" if abs(b5) > 5 else "股价在MA5附近，走势健康"}</span></div>'
    ))
    c5 = td.get('change_5d', 0)
    c5_status = '短期走强' if c5 > 5 else '短期走弱' if c5 < -5 else '短期平稳'
    c5_color = 'status-red' if c5 > 5 else 'status-green' if c5 < -5 else 'status-gray'
    rows.append((
        f'<div class="indicator-row"><span class="ind-name">5日</span>'
        f'<span class="ind-value">5日涨跌 {c5}%</span>'
        f'<span class="ind-status {c5_color}">{c5_status}</span>'
        f'<span class="ind-desc">{"近5日走势强劲" if c5 > 5 else "近5日走势偏弱" if c5 < -5 else "近5日窄幅震荡"}</span></div>'
    ))
    indicators_html = ''.join(rows)

    # 信号理由
    signal_reasons = sd.get('signal_reasons', [])
    risk_factors = sd.get('risk_factors', [])
    reasons_list = ''.join(f'<div class="reason-item">• {r}</div>' for r in signal_reasons)
    risks_list = ''.join(f'<div class="reason-item">• {r}</div>' for r in risk_factors)

    # AI内容
    ai_conf = ai.get('confidence_level', '--') if ai else '--'
    ai_target = ai.get('target_price', '--') if ai else '--'
    ai_stop = ai.get('stop_loss', '--') if ai else '--'

    # 支撑压力位
    high_20 = td.get('high_20', 0)
    low_20 = td.get('low_20', 0)
    ma5_val = td.get('ma5', 0)
    ma10_val = td.get('ma10', 0)
    ma20_val = td.get('ma20', 0)
    supports = []
    # 均线支撑（由近到远）
    if ma5_val and ma5_val < price:
        supports.append(f'{ma5_val:.2f}(MA5)')
    if ma10_val and ma10_val < price and abs(ma10_val - ma5_val) > 0.01:
        supports.append(f'{ma10_val:.2f}(MA10)')
    if ma20_val and ma20_val < price and abs(ma20_val - ma10_val) > 0.01:
        supports.append(f'{ma20_val:.2f}(MA20)')
    if low_20:
        supports.append(f'{low_20:.2f}(20日低)')
    if prev_close > 0:
        s2 = round(prev_close * 0.95, 2)
        supports.append(f'{s2}(-5%位)')
    resistances = []
    # 均线压力（由近到远）
    if ma5_val and ma5_val > price:
        resistances.append(f'{ma5_val:.2f}(MA5)')
    if ma10_val and ma10_val > price and abs(ma10_val - ma5_val) > 0.01:
        resistances.append(f'{ma10_val:.2f}(MA10)')
    if ma20_val and ma20_val > price and abs(ma20_val - ma10_val) > 0.01:
        resistances.append(f'{ma20_val:.2f}(MA20)')
    if high_20:
        resistances.append(f'{high_20:.2f}(20日高)')
    if prev_close > 0:
        r2 = round(prev_close * 1.05, 2)
        resistances.append(f'{r2}(+5%位)')

    supply_html = ''.join(f'<span class="level-tag">{s}</span>' for s in supports[:5])
    resist_html = ''.join(f'<span class="level-tag">{r}</span>' for r in resistances[:5])

    # 策略建议
    sh_sig_lower = sd.get('buy_signal', '观望')
    if sh_sig_lower == '买入':
        holder_advice = f'持有为主，可在回调至MA5({td.get("ma5","?")})附近加仓'
        watcher_advice = f'可考虑在回调至MA5附近时分批建仓'
        pos_advice = f'仓位可逐步增加至5-7成'
    elif sh_sig_lower == '持有':
        holder_advice = f'继续持有，关注MA20({td.get("ma20","?")})支撑'
        watcher_advice = f'等待回调至MA20附近再考虑入场'
        pos_advice = f'保持3-5成仓位'
    elif sh_sig_lower == '观望':
        holder_advice = f'减仓观望，跌破关键支撑需止损'
        watcher_advice = f'暂时观望，等待趋势明确再入场'
        pos_advice = f'仓位控制在2成以下'
    else:
        holder_advice = '建议止损离场，等待企稳'
        watcher_advice = '暂时回避，不宜抄底'
        pos_advice = '空仓或极轻仓'

    vol_str = f"{quote.get('volume',0)/10000:.1f}万手" if quote.get('volume',0) >= 10000 else f"{quote.get('volume',0)/1000:.1f}千手"

    now_str = now.strftime('%Y-%m-%d %H:%M')
    date_str = now.strftime('%Y-%m-%d')

    # 板块行情分析
    if sector_data is None and sector:
        sector_data = fetch_sector_analysis(sector)
    if sector_data:
        sec_rows = []
        for s in sector_data:
            s_up = s['chg_pct'] >= 0
            s_chg_sign = '+' if s_up else ''
            s_color = '#DC143C' if s_up else '#008000'
            sec_rows.append(
                f'<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:13px">'
                f'<span style="font-weight:600">{s["name"]}</span>'
                f'<span style="color:{s_color}">{s_chg_sign}{s["chg_pct"]:.2f}%</span>'
                f'<span>{s["price"]:.2f}</span>'
                f'</div>'
            )
        sector_html = f'''<div class="card">
    <h2>🏭 板块行情分析</h2>
    <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:11px;color:#999;border-bottom:2px solid #eee">
        <span>板块名称</span><span>涨跌幅</span><span>现价</span>
    </div>
    {''.join(sec_rows)}
</div>'''
    else:
        sector_html = ''

    # 最新资讯
    if news_data is None and code:
        news_data = fetch_report_news(code, name, 3)
    if news_data:
        news_rows = []
        for n in news_data:
            news_rows.append(
                f'<div style="padding:10px 0;border-bottom:1px solid #f0f0f0">'
                f'<div style="font-size:14px;font-weight:600;color:#333;margin-bottom:4px">{n["title"]}</div>'
                f'<div style="display:flex;gap:12px;font-size:11px;color:#999;margin-bottom:4px">'
                f'<span>{n["source"]}</span><span>{n["date"]}</span>'
                f'</div>'
                f'<div style="font-size:12px;color:#666;line-height:1.6">{n["content"]}</div>'
                f'</div>'
            )
        news_html = f'''<div class="card">
    <h2>📰 最新资讯</h2>
    {''.join(news_rows)}
</div>'''
    else:
        news_html = ''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} - 技术分析报告</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Microsoft YaHei', 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; padding: 16px; }}
.container {{ max-width: 900px; margin: 0 auto; }}
.card {{ background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 16px; padding: 20px; }}
h2 {{ font-size: 16px; color: #333; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px; margin-bottom: 16px; }}
.header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; border-radius: 12px; padding: 24px; margin-bottom: 16px; }}
.header h1 {{ font-size: 22px; margin-bottom: 4px; }}
.header .date {{ font-size: 13px; opacity: 0.7; }}
.price-row {{ display: flex; align-items: baseline; gap: 12px; margin: 12px 0; }}
.price {{ font-size: 36px; font-weight: bold; }}
.chg {{ font-size: 18px; font-weight: 500; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-top: 16px; }}
.stat-item {{ background: rgba(255,255,255,0.1); border-radius: 8px; padding: 10px; }}
.stat-label {{ font-size: 12px; opacity: 0.6; margin-bottom: 4px; }}
.stat-value {{ font-size: 16px; font-weight: 500; }}
.indicator-row {{ display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid #f5f5f5; gap: 12px; }}
.indicator-row:last-child {{ border-bottom: none; }}
.ind-name {{ width: 70px; font-weight: 500; color: #666; font-size: 14px; flex-shrink: 0; }}
.ind-value {{ width: 180px; font-size: 13px; color: #888; font-family: 'SF Mono', monospace; flex-shrink: 0; }}
.ind-status {{ width: 90px; font-size: 13px; font-weight: 600; flex-shrink: 0; }}
.ind-desc {{ flex: 1; font-size: 13px; color: #555; }}
.status-red {{ color: #DC143C; }}
.status-green {{ color: #008000; }}
.status-orange {{ color: #FF8C00; }}
.status-gray {{ color: #888; }}
.dual-score {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 0 auto; }}
.dual-box {{ background: #f8f9fa; border-radius: 12px; padding: 20px; text-align: center; border: 2px solid #e8e8e8; }}
.dual-box .title {{ font-size: 14px; font-weight: 600; color: #333; margin-bottom: 12px; }}
.score-circle {{ width: 100px; height: 100px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 0 auto 8px; border: 4px solid; }}
.score-num {{ font-size: 32px; font-weight: bold; }}
.score-label {{ font-size: 12px; margin-top: 2px; }}
.dual-box .reasons {{ font-size: 12px; color: #666; margin-top: 8px; text-align: left; line-height: 1.8; }}
.reason-item {{ padding: 2px 0; font-size: 13px; color: #555; }}
.price-levels {{ display: flex; gap: 24px; flex-wrap: wrap; }}
.level-group {{ flex: 1; min-width: 200px; }}
.level-group h4 {{ font-size: 13px; color: #666; margin-bottom: 6px; font-weight: 600; }}
.level-tag {{ display: inline-block; background: #f0f2f5; padding: 4px 10px; border-radius: 4px; font-size: 13px; margin: 2px 4px 2px 0; }}
.strategy-section {{ margin-bottom: 16px; }}
.strategy-section h4 {{ font-size: 13px; color: #666; margin-bottom: 8px; font-weight: 600; }}
.advice-line {{ font-size: 14px; color: #333; margin-bottom: 6px; padding-left: 12px; border-left: 3px solid #4a90d9; }}
.risk-tag {{ display: inline-block; background: #fff3e0; color: #e65100; padding: 4px 10px; border-radius: 4px; font-size: 12px; margin: 2px 4px 2px 0; }}
.footer {{ text-align: center; padding: 16px; color: #999; font-size: 12px; }}
.back-btn {{ display: inline-block; margin-bottom: 20px; color: #4a90d9; text-decoration: none; font-size: 14px; }}
@media (max-width: 600px) {{
    .price {{ font-size: 28px; }}
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .dual-score {{ grid-template-columns: 1fr; }}
    .indicator-row {{ flex-wrap: wrap; }}
    .ind-value {{ width: 100%; order: 3; }}
}}
</style>
</head>
<body>
<div class="container">
<a href="javascript:history.back()" class="back-btn">← 返回</a>
<button onclick="refreshReport()" id="refreshBtn" style="float:right;padding:6px 14px;border:none;border-radius:6px;background:#4a90d9;color:#fff;font-size:13px;cursor:pointer">&#x21BB; 刷新</button>

<div class="header">
    <h1>{name} ({code})</h1>
    <div style="font-size:14px;color:rgba(255,255,255,0.8);margin-bottom:4px">{'🏭 ' + sector if sector else ''}</div>
    <div class="date">{date_str} 实时分析</div>
    <div class="price-row">
        <span class="price" style="color: {chg_color}">{price:.2f}</span>
        <span class="chg" style="color: {chg_color}">{chg_arrow} {chg_sign}{price - prev_close:.2f} ({chg_sign}{chg:.2f}%)</span>
    </div>
    <div class="stats-grid">
        <div class="stat-item">
            <div class="stat-label">成交量</div>
            <div class="stat-value">{vol_str}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">MA5</div>
            <div class="stat-value">{td.get("ma5","--")}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">MA10</div>
            <div class="stat-value">{td.get("ma10","--")}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">MA20</div>
            <div class="stat-value">{td.get("ma20","--")}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">MA60</div>
            <div class="stat-value">{td.get("ma60","--")}</div>
        </div>
    </div>
</div>

<!-- 双版本评分 -->
<div class="card">
    <h2>双版本评分</h2>
    <div class="dual-score">
        <div class="dual-box">
            <div class="title">🕵️‍♂️ StockHolmes 规则评分</div>
            <div class="score-circle" style="border-color: {score_color(sh_score)}">
                <span class="score-num" style="color: {score_color(sh_score)}">{sh_score}</span>
                <span class="score-label" style="color: {score_color(sh_score)}">{sh_signal}</span>
            </div>
            <div class="reasons">
                <div class="reason-item">MA: {sd.get("ma_alignment","--")}</div>
                <div class="reason-item">MACD: {sd.get("macd_status","--")}</div>
                <div class="reason-item">RSI: {sd.get("rsi_status","--")}</div>
{reasons_list}
            </div>
        </div>
        <div class="dual-box">
            <div class="title">🤖 AI 分析评分</div>
            <div class="score-circle" style="border-color: {score_color(ai_score)}">
                <span class="score-num" style="color: {score_color(ai_score)}">{ai_score}</span>
                <span class="score-label" style="color: {score_color(ai_score)}">{ai_signal}</span>
            </div>
            <div class="reasons">
                <div class="reason-item">置信度: {ai_conf}%</div>
                <div class="reason-item">目标价: {ai_target}</div>
                <div class="reason-item">止损价: {ai_stop}</div>
                <div class="reason-item">{ai_summary}</div>
            </div>
        </div>
    </div>
</div>

<!-- 交易策略 -->
<div class="card">
    <h2>交易策略</h2>
    <div class="strategy-section">
        <h4>1. 关键价位</h4>
        <div class="level-group" style="margin-bottom:8px">
            <span style="font-size:12px;color:#999;margin-right:8px">支撑位:</span>
            {supply_html}
        </div>
        <div class="level-group">
            <span style="font-size:12px;color:#999;margin-right:8px">压力位:</span>
            {resist_html}
        </div>
    </div>
    <div class="strategy-section">
        <h4>2. 操作建议</h4>
        <div class="advice-line"><strong>若已持有：</strong>{holder_advice}</div>
        <div class="advice-line" style="border-left-color:#008000"><strong>若未持有：</strong>{watcher_advice}</div>
    </div>
    <div class="strategy-section" style="margin-bottom:0">
        <h4>3. 仓位建议</h4>
        <div class="advice-line" style="border-left-color:#FF8C00">{pos_advice}</div>
    </div>
</div>

<!-- 板块行情分析 -->
{sector_html}

<!-- 技术指标解读 -->
<div class="card">
    <h2>技术指标解读</h2>
    {indicators_html}
</div>

<!-- 风险因素 -->
<div class="card">
    <h2>风险因素</h2>
    <div>
        {"<div class='reason-item' style='color:#e65100'>⚠️ " + '</div><div class="reason-item" style="color:#e65100">⚠️ '.join(risk_factors) + '</div>' if risk_factors else '<div class="reason-item" style="color:#999">当前无明显风险因素</div>'}
    </div>
    <div style="margin-top:12px">
        <h4 style="font-size:13px;color:#666;margin-bottom:6px">支撑位</h4>
        {supply_html}
        <h4 style="font-size:13px;color:#666;margin:8px 0 6px">压力位</h4>
        {resist_html}
    </div>
</div>

<!-- 最新资讯 -->
{news_html}

<div class="footer">
    本报告由技术分析自动生成，仅供参考，不构成投资建议<br>
    数据来源：腾讯API + StockHolmes规则引擎<br>
    生成时间: {now_str}
</div>

</div>
<script>
function refreshReport(){{
  var btn=document.getElementById('refreshBtn');
  btn.disabled=true; btn.innerHTML='&#x21BB; 刷新中...'; btn.style.opacity='0.6';
  fetch('/api/'+window.location.pathname.split('/')[1]+'/reports/generate/{code}?name='+encodeURIComponent('{name}'),{{method:'POST'}})
    .then(function(r){{return r.json()}})
    .then(function(d){{
      if(d.ok) window.location.href=d.report_url;
      else alert('刷新失败: '+d.error);
    }})
    .catch(function(e){{alert('请求失败: '+e.message)}})
    .finally(function(){{btn.disabled=false; btn.innerHTML='&#x21BB; 刷新'}});
}}
</script>
</body>
</html>'''

    if user_key and user_key in USERS:
        d = USERS[user_key]['dir']
        d.mkdir(parents=True, exist_ok=True)
        with open(d / filename, 'w', encoding='utf-8') as f:
            f.write(html)
    return filename


# ===== Flask Routes =====

@app.route('/<user_key>/kol/')
def user_kol_tracker(user_key):
    if user_key not in USERS:
        return "User not found", 404
    return render_template('kol_tracker.html')

@app.route('/<user_key>/')
def user_dashboard(user_key):
    if user_key not in USERS:
        return "User not found", 404
    u = USERS[user_key]
    return render_template('dashboard_v2.html', user_key=user_key, user_label=u['label'], user_emoji=u['emoji'])


@app.route('/<user_key>/reports/<filename>')
def serve_report(user_key, filename):
    if user_key not in USERS:
        return "Not found", 404
    d = USERS[user_key]['dir']
    if (d / filename).exists():
        return send_from_directory(d, filename)
    if (OUTPUT_DIR / filename).exists():
        return send_from_directory(OUTPUT_DIR, filename)
    return "Report not found", 404


@app.route('/api/<user_key>/portfolio', methods=['GET'])
def api_get_portfolio(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_json(user_key, 'portfolio')
    # 惰性加载资金流向和盘口数据
    codes = [r['code'] for r in data.get('results', [])]
    if codes:
        quotes = fetch_realtime_quote(codes)
        for r in data['results']:
            code = r['code']
            if not r.get('money_flow'):
                r['money_flow'] = fetch_money_flow(code, r.get('name', ''))
            if not r.get('order_book'):
                q = quotes.get(code, {})
                r['order_book'] = {'bids': q.get('bids', []), 'asks': q.get('asks', [])}
            # 用新的资金/盘口数据更新StockHolmes评分
            tech = r.get('technical', {})
            if tech and (r.get('money_flow') or r.get('order_book')):
                r['stockholmes'] = stockholmes_rules(tech, money_flow=r.get('money_flow'), order_book=r.get('order_book'),
                    financial=r.get('financial'), pattern=r.get('pattern'),
                    turnover=r.get('turnover'), amount_wan=r.get('amount_wan'), day_change=r.get('day_change'))
    return jsonify(data)


@app.route('/api/<user_key>/portfolio', methods=['POST'])
def api_update_portfolio(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    action = request.json.get('action')
    data = load_json(user_key, 'portfolio')

    if action == 'add':
        stock = request.json.get('stock')
        if stock:
            if any(r['code'] == stock['code'] for r in data['results']):
                return jsonify({'error': f"Code {stock['code']} exists"}), 400
            data['results'].append(stock)
    elif action == 'delete':
        code = request.json.get('code')
        data['results'] = [r for r in data['results'] if r['code'] != code]
    elif action == 'edit':
        code = request.json.get('code')
        edits = request.json.get('edits', {})
        for r in data['results']:
            if r['code'] == code:
                r.update(edits)
                break

    data['total_cost'] = sum(r.get('position_cost', 0) for r in data['results'])
    data['total_value'] = sum(r.get('position_value', 0) for r in data['results'])
    data['total_pnl'] = round(data['total_value'] - data['total_cost'], 2)
    data['total_pnl_pct'] = round(data['total_pnl'] / data['total_cost'] * 100, 2) if data['total_cost'] > 0 else 0
    save_json(user_key, 'portfolio', data)
    return jsonify({'ok': True, 'data': data})


@app.route('/api/<user_key>/portfolio/refresh', methods=['POST'])
def api_refresh_portfolio(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_json(user_key, 'portfolio')
    codes = [r['code'] for r in data['results']]
    quotes = fetch_realtime_quote(codes)
    time.sleep(0.3)

    updated = 0
    reports_gen = 0
    for r in data['results']:
        code = r['code']
        q = quotes.get(code)
        if q:
            r['current'] = q['price']
            r['day_change'] = round(q['change_pct'], 2)
            r['position_value'] = round(q['price'] * r.get('qty', 100))
            cost = r.get('position_cost', r.get('cost', 0) * r.get('qty', 100))
            r['position_cost'] = cost
            r['pnl'] = round(r['position_value'] - cost, 2)
            r['pnl_pct'] = round(r['pnl'] / cost * 100, 2) if cost > 0 else 0
            # 保存换手率和成交额（从腾讯API直接获取）
            r['turnover'] = q.get('turnover', 0)
            r['amount_wan'] = q.get('amount_wan', 0)

            tech = None
            klines = fetch_kline_tencent(code, days=70)
            if klines:
                tech = compute_indicators(klines)
                if tech:
                    r['technical'] = tech
                    r['stockholmes'] = stockholmes_rules(tech, money_flow=r.get('money_flow'), order_book=r.get('order_book'),
                    financial=r.get('financial'), pattern=r.get('pattern'),
                    turnover=r.get('turnover'), amount_wan=r.get('amount_wan'), day_change=r.get('day_change'))
                    updated += 1

            # 资金流向
            if 'money_flow' not in r or not r['money_flow']:
                r['money_flow'] = fetch_money_flow(code, r.get('name', ''))
            # 5档盘口
            if 'order_book' not in r or not r['order_book']:
                r['order_book'] = {'bids': q.get('bids', []), 'asks': q.get('asks', [])}
            else:
                r['order_book'] = {'bids': q.get('bids', []), 'asks': q.get('asks', [])}

            # 板块行情数据（快速，东方财富API一次调用）
            if r.get('sector') and not r.get('sector_data'):
                sd = fetch_sector_analysis(r['sector'])
                if sd:
                    r['sector_data'] = sd
            
            # 财务指标（mx-data，快速）
            if not r.get('financial'):
                fin = fetch_financial_data(code, r['name'])
                if any(fin.values()):
                    r['financial'] = fin

            if tech and not check_report_exists(code, r['name'], user_key):
                try:
                    generate_report_html(code, r['name'], tech, q, r.get('stockholmes', {}), r.get('ai_analysis', {}), user_key, sector=r.get('sector', ''))
                    reports_gen += 1
                except Exception as e:
                    print(f"[report gen error {code}] {e}")
            time.sleep(0.3)

    data['total_cost'] = sum(r.get('position_cost', 0) for r in data['results'])
    data['total_value'] = sum(r.get('position_value', 0) for r in data['results'])
    data['total_pnl'] = round(data['total_value'] - data['total_cost'], 2)
    data['total_pnl_pct'] = round(data['total_pnl'] / data['total_cost'] * 100, 2) if data['total_cost'] > 0 else 0
    save_json(user_key, 'portfolio', data)

    return jsonify({
        'ok': True, 'data': data, 'updated': updated,
        'reports_generated': reports_gen,
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def import_watchlist_from_reports(user_key):
    """从自选股分析报告HTML中提取股票并导入watchlist.json"""
    if user_key not in USERS:
        return 0
    user_dir = USERS[user_key]['dir']
    reports_dir = user_dir / 'watchlist'
    wl_path = USERS[user_key]['watchlist']
    latest = reports_dir / '自选股分析_最新.html'
    if not latest.exists():
        return 0
    try:
        html = latest.read_text(encoding='utf-8')
        import re
        pattern = r'<td class="name-cell">([^<]+)<br/><span class="code">(sh|sz)(\d{6})</span></td>'
        matches = re.findall(pattern, html)
        if not matches:
            return 0
        try:
            import json
            with open(wl_path) as f:
                wl = json.load(f)
        except:
            wl = {'groups': [{'name': '默认', 'stocks': []}]}
        existing = set()
        for g in wl['groups']:
            for s in g['stocks']:
                existing.add(s['code'])
        added = 0
        for name_raw, market, code in matches:
            if code in existing:
                continue
            name = name_raw.strip().replace(' ', '')
            found = False
            for g in wl['groups']:
                if g['name'] == '默认':
                    g['stocks'].append({'code': code, 'name': name})
                    found = True
                    break
            if not found:
                wl['groups'].append({'name': '默认', 'stocks': [{'code': code, 'name': name}]})
            existing.add(code)
            added += 1
        if added > 0:
            import json
            with open(wl_path, 'w') as f:
                json.dump(wl, f, ensure_ascii=False, indent=2)
        return added
    except Exception as e:
        print(f"[import watchlist] error: {e}")
        return 0

@app.route('/api/<user_key>/watchlist', methods=['GET'])
def api_get_watchlist(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    # 如果watchlist为空，自动从报告导入
    wl = load_json(user_key, 'watchlist')
    stocks_count = sum(len(g.get('stocks',[])) for g in wl.get('groups',[]))
    if stocks_count == 0:
        n = import_watchlist_from_reports(user_key)
        if n > 0:
            print(f"[watchlist] auto-imported {n} stocks for {user_key}")
            wl = load_json(user_key, 'watchlist')
    # 惰性加载资金流向和盘口数据
    all_codes = [s['code'] for g in wl.get('groups', []) for s in g.get('stocks', [])]
    if all_codes:
        quotes = fetch_realtime_quote(all_codes)
        for g in wl['groups']:
            for s in g['stocks']:
                code = s['code']
                if not s.get('money_flow'):
                    s['money_flow'] = fetch_money_flow(code, s.get('name', ''))
                if not s.get('order_book'):
                    q = quotes.get(code, {})
                    s['order_book'] = {'bids': q.get('bids', []), 'asks': q.get('asks', [])}
                # 用新的资金/盘口数据更新StockHolmes评分
                tech = s.get('technical', {})
                if tech:
                    s['stockholmes'] = stockholmes_rules(tech, money_flow=s.get('money_flow'), order_book=s.get('order_book'))
    return jsonify(wl)


@app.route('/api/<user_key>/watchlist', methods=['POST'])
def api_update_watchlist(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    action = request.json.get('action')
    data = load_json(user_key, 'watchlist')

    if action == 'add':
        stock = request.json.get('stock')
        group = request.json.get('group', '默认')
        if stock:
            # 检查所有分组的代码是否重复（跨组去重）
            all_codes = [s['code'] for g in data['groups'] for s in g.get('stocks',[])]
            if stock['code'] in all_codes:
                return jsonify({'ok': False, 'error': f'股票 {stock["name"]}({stock["code"]}) 已在自选列表中', 'data': data})
            for g in data['groups']:
                if g['name'] == group:
                    g['stocks'].append(stock)
                    break
            else:
                data['groups'].append({'name': group, 'stocks': [stock]})
    elif action == 'delete':
        code = request.json.get('code')
        group = request.json.get('group')
        for g in data['groups']:
            if group and g['name'] == group:
                g['stocks'] = [s for s in g['stocks'] if s['code'] != code]
            elif not group:
                g['stocks'] = [s for s in g['stocks'] if s['code'] != code]
    elif action == 'add_group':
        name = request.json.get('name')
        if name and name not in [g['name'] for g in data['groups']]:
            data['groups'].append({'name': name, 'stocks': []})
    elif action == 'delete_group':
        name = request.json.get('name')
        data['groups'] = [g for g in data['groups'] if g['name'] != name]

    save_json(user_key, 'watchlist', data)
    return jsonify({'ok': True, 'data': data})


@app.route('/api/<user_key>/watchlist/refresh', methods=['POST'])
def api_refresh_watchlist(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_json(user_key, 'watchlist')
    all_codes = [s['code'] for g in data['groups'] for s in g['stocks']]
    quotes = fetch_realtime_quote(all_codes)
    time.sleep(0.3)

    reports_gen = 0
    for g in data['groups']:
        for s in g['stocks']:
            code = s['code']
            q = quotes.get(code)
            if q:
                s['price'] = q['price']
                s['change_pct'] = round(q['change_pct'], 2)
                s['update_time'] = q['update_time']
                # 5档盘口
                s['order_book'] = {'bids': q.get('bids', []), 'asks': q.get('asks', [])}
                # 资金流向
                if 'money_flow' not in s or not s['money_flow']:
                    s['money_flow'] = fetch_money_flow(code, s.get('name', ''))
                # 获取K线数据和技术指标
                klines = fetch_kline_tencent(code, days=70)
                tech = compute_indicators(klines) if klines else None
                sh = stockholmes_rules(tech, money_flow=s.get('money_flow'), order_book=s.get('order_book')) if tech else {}
                # 存储技术指标供前端展示
                s['technical'] = {
                    'ma5': tech.get('ma5'), 'ma10': tech.get('ma10'),
                    'ma20': tech.get('ma20'), 'ma60': tech.get('ma60'),
                    'rsi': tech.get('rsi'), 'vol_ratio': tech.get('vol_ratio'),
                    'macd_signal': tech.get('macd_signal'), 'trend': tech.get('trend'),
                    'bias5': tech.get('bias5'), 'change_5d': tech.get('change_5d'),
                } if tech else {}
                s['stockholmes'] = sh
                # 保留原有AI分析（刷新行情时不重新生成，避免长时间等待）
                if 'ai_analysis' not in s or not s['ai_analysis']:
                    ai = generate_ai_analysis(code, s['name'], tech, q, money_flow=s.get('money_flow'), order_book=s.get('order_book')) if tech else {}
                    if ai:
                        print(f"[AI analyze done {code}] score={ai.get('sentiment_score')}, advice={ai.get('operation_advice')}")
                    s['ai_analysis'] = ai
                # 生成个股报告（如果没有）
                if not check_report_exists(code, s['name'], user_key):
                    try:
                        generate_report_html(code, s['name'], tech, q, sh, ai, user_key, sector=s.get('sector', ''))
                        reports_gen += 1
                    except Exception as e:
                        print(f"[report gen error {code}] {e}")
                    time.sleep(0.3)

    save_json(user_key, 'watchlist', data)
    return jsonify({'ok': True, 'data': data, 'reports_generated': reports_gen,
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


@app.route('/api/<user_key>/watchlist/refresh-single', methods=['POST'])
def api_refresh_watchlist_single(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json()
    code = data.get('code', '') if data else ''
    if not code:
        return jsonify({'error': 'code required'}), 400
    wl = load_json(user_key, 'watchlist')
    found = None
    for g in wl['groups']:
        for s in g.get('stocks', []):
            if s.get('code') == code:
                found = s
                break
    if not found:
        return jsonify({'error': 'stock not found in watchlist'}), 404
    try:
        q = fetch_realtime_quote([code]).get(code, {})
        if q:
            found['price'] = q['price']
            found['change_pct'] = round(q['change_pct'], 2)
            found['update_time'] = q['update_time']
            found['order_book'] = {'bids': q.get('bids', []), 'asks': q.get('asks', [])}
        found['money_flow'] = fetch_money_flow(code, found.get('name', '')) or {}
        klines = fetch_kline_tencent(code, days=70)
        tech = compute_indicators(klines) if klines else None
        if tech:
            found['technical'] = {
                'ma5': tech.get('ma5'), 'ma10': tech.get('ma10'),
                'ma20': tech.get('ma20'), 'ma60': tech.get('ma60'),
                'rsi': tech.get('rsi'), 'vol_ratio': tech.get('vol_ratio'),
                'macd_signal': tech.get('macd_signal'), 'trend': tech.get('trend'),
                'bias5': tech.get('bias5'), 'change_5d': tech.get('change_5d'),
            }
            found['stockholmes'] = stockholmes_rules(tech,
                money_flow=found.get('money_flow'),
                order_book=found.get('order_book'))
        save_json(user_key, 'watchlist', wl)
        return jsonify({'ok': True, 'data': wl,
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
    except Exception as e:
        print(f'[watchlist refresh-single error] {code}: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/<user_key>/watchlist/ai-analyze', methods=['POST'])
def api_ai_analyze_watchlist(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_json(user_key, 'watchlist')
    analyzed = 0
    for g in data['groups']:
        for s in g.get('stocks', []):
            code = s.get('code', '')
            name = s.get('name', '')
            tech = s.get('technical', {})
            q = {'price': s.get('price', 0), 'prev_close': s.get('prev_close', 0),
                 'change_pct': s.get('change_pct', 0)}
            # 确保有资金流向和盘口数据
            if 'money_flow' not in s or not s.get('money_flow'):
                s['money_flow'] = fetch_money_flow(code, s.get('name', ''))
            mf = s.get('money_flow', {})
            ob = s.get('order_book', {})
            ai = generate_ai_analysis(code, name, tech, q, money_flow=mf, order_book=ob) if tech else {}
            if ai:
                print(f"[WL AI analyze done {code}] score={ai.get('sentiment_score')}")
                s['ai_analysis'] = ai
                analyzed += 1
            time.sleep(1)
    save_json(user_key, 'watchlist', data)
    return jsonify({'ok': True, 'analyzed': analyzed,
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})


@app.route('/api/<user_key>/reports/batch-check')
def api_batch_check_reports(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    codes_param = request.args.get('codes', '')
    codes = [c.strip() for c in codes_param.split(',') if c.strip()]
    result = {}
    d = USERS[user_key]['dir']
    for code in codes:
        market = get_market_prefix(code)
        files = sorted(globmod.glob(str(d / f"{market}{code}_*_report*.html")), reverse=True)
        result[code] = f"/{user_key}/reports/{os.path.basename(files[0])}" if files else None
    return jsonify({'reports': result})


@app.route('/api/<user_key>/reports/<code>')
def api_list_reports(user_key, code):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    market = get_market_prefix(code)
    reports = []
    for d in [USERS[user_key]['dir'], OUTPUT_DIR]:
        if d.exists():
            for f in sorted(globmod.glob(str(d / f"{market}{code}_*_report*.html")), reverse=True):
                reports.append({
                    'filename': os.path.basename(f),
                    'time': datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M"),
                    'size': os.path.getsize(f),
                    'url': f"/{user_key}/reports/{os.path.basename(f)}"
                })
    return jsonify({'reports': reports})


@app.route('/api/<user_key>/reports/generate/<code>', methods=['POST'])
def api_generate_report(user_key, code):
    name = request.args.get('name', '')  # use query param to avoid Latin-1 URL path encoding issue
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    # 从持仓数据中获取板块信息
    sector = ''
    if name:
        pdata = load_json(user_key, 'portfolio')
        for r in pdata.get('results', []):
            if r.get('code') == code or r.get('name') == name:
                sector = r.get('sector', '')
                break
    klines = fetch_kline_tencent(code, days=70)
    tech = compute_indicators(klines) if klines else None
    quote = fetch_realtime_quote([code]).get(code, {})
    mf = fetch_money_flow(code, name) or {}
    ob = {'bids': quote.get('bids', []), 'asks': quote.get('asks', [])} if quote else {}
    sh = stockholmes_rules(tech, money_flow=mf, order_book=ob) if tech else {}
    ob = {'bids': quote.get('bids', []), 'asks': quote.get('asks', [])} if quote else {}
    ai = generate_ai_analysis(code, name, tech, quote, money_flow=mf, order_book=ob) if tech else {}
    try:
        fn = generate_report_html(code, name, tech, quote, sh, ai, user_key, sector=sector)
        return jsonify({'ok': True, 'report_url': f"/{user_key}/reports/{fn}"})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/<user_key>/quotes')
def api_quotes(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    codes = request.args.get('codes', '').split(',')
    codes = [c.strip() for c in codes if c.strip()]
    return jsonify(fetch_realtime_quote(codes))



@app.route('/api/<user_key>/intraday/<code>')
def api_get_intraday(user_key, code):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    try:
        secid = get_secid(code)
        url = f'https://push2.eastmoney.com/api/qt/stock/trends2/get?fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&ut=fb5fd1943c7b386f172d6893dbfba10b&ndays=1&iscr=1&secid={secid}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        raw = json.loads(resp.read().decode('utf-8'))
        if raw.get('rc') != 0 or not raw.get('data'):
            return jsonify({'ok': False, 'error': 'no data'})
        data = raw['data']
        pre_close = data.get('preClose', 0)
        trends = data.get('trends', [])
        
        # Parse trends
        points = []
        for t in trends:
            parts = t.split(',')
            if len(parts) >= 6:
                points.append({
                    'time': parts[0][11:16],  # HH:MM
                    'price': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'volume': float(parts[5]),
                    'amount': float(parts[6]) if len(parts) > 6 and parts[6] else 0,
                })
        
        if not points:
            return jsonify({'ok': False, 'error': 'no intraday data'})
        
        # Calculate metrics
        prices = [p['price'] for p in points]
        volumes = [p['volume'] for p in points]
        high = max(prices)
        low = min(prices)
        open_price = prices[0] if points else 0
        last = prices[-1] if points else 0
        amplitude = round((high - low) / (pre_close or low) * 100, 2)
        avg_vol = (sum(volumes) / len(volumes)) if volumes else 0
        
        # Detect anomalies: minutes where price jumped >1% from previous
        anomalies = []
        for i in range(1, len(points)):
            prev = points[i-1]['price']
            cur = points[i]['price']
            if prev > 0:
                jump = (cur - prev) / prev * 100
                if abs(jump) >= 1:
                    anomalies.append({
                        'time': points[i]['time'],
                        'price': cur,
                        'jump_pct': round(jump, 2),
                        'direction': 'up' if jump > 0 else 'down',
                        'volume': int(points[i]['volume']),
                    })
        
        # Volume spikes (top 3)
        vol_max = max(volumes)
        vol_spikes = sorted(
            [{'time': p['time'], 'volume': int(p['volume']), 'amount': round(p['amount']/10000, 0)}
             for p in points if p['volume'] >= avg_vol * 2 and p['volume'] > 0],
            key=lambda x: -x['volume']
        )[:3]
        
        return jsonify({
            'ok': True,
            'code': code,
            'name': data.get('name', ''),
            'pre_close': pre_close,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'last': round(last, 2),
            'amplitude': amplitude,
            'avg_vol': int(avg_vol),
            'vol_max': int(vol_max),
            'anomalies': anomalies[:5],
            'vol_spikes': vol_spikes,
            'total_vol': int(sum(volumes)),
            'total_amount': round(sum(p['amount'] for p in points) / 100000000, 2),
        })
    except Exception as e:
        print(f'[intraday error {code}] {e}')
        return jsonify({'ok': False, 'error': str(e)})


def get_secid(code):
    code = code.strip()
    if code.startswith(('6', '9')):
        return f'1.{code}'
    return f'0.{code}'


@app.route('/api/<user_key>/news/<code>')
def api_get_news(user_key, code):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    name = request.args.get('name', '')
    if not name:
        return jsonify({'title': '', 'summary': ''})
    try:
        param_json = urllib.parse.quote(json.dumps({
            'uid': '',
            'keyword': name,
            'type': ['cmsArticle'],
            'range': 'title',
            'pageSize': 1,
            'pageIndex': 1
        }, ensure_ascii=True))
        url = f'https://search-api-web.eastmoney.com/search/jsonp?cb=jQuery&type=cmsArticle&client=web&param={param_json}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        text = resp.read().decode('utf-8')
        start = text.find('(') + 1
        end = text.rfind(')')
        if start > 0 and end > start:
            data = json.loads(text[start:end])
            results = data.get('result', {}).get('cmsArticle', [])
            if results:
                item = results[0]
                title = item.get('title', '').replace('<em>', '').replace('</em>', '')
                summary = (item.get('content', item.get('digest', ''))[:300]
                    .replace('<em>', '').replace('</em>', ''))
                return jsonify({'title': title, 'summary': summary})
        return jsonify({'title': '', 'summary': ''})
    except Exception as e:
        print(f'[news fetch error {code}] {e}')
        return jsonify({'title': '', 'summary': ''})


@app.route('/api/<user_key>/portfolio/ai-analyze', methods=['POST'])
def api_ai_analyze_portfolio(user_key):
    """用 DeepSeek 批量生成 AI 分析（替换之前的本地 LLM）"""
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_json(user_key, 'portfolio')
    to_analyze = [r for r in data['results'] if r.get('technical')]
    if not to_analyze:
        return jsonify({'ok': True, 'analyzed': 0, 'message': '没有技术数据，先刷新行情'})
    
    ai_results = generate_deepseek_ai_batch(to_analyze)
    analyzed = 0
    for i, r in enumerate(to_analyze):
        if i < len(ai_results):
            ai = ai_results[i]
            r['ai_deepseek'] = {
                'operation_advice': ai['advice'],
                'sentiment_score': ai['sentiment'],
                'analysis_summary': ai['summary'],
                'analysis_detailed': ai['detailed'],
                'target_price': str(ai['target']),
                'stop_loss': str(ai['stop']),
                'confidence_level': ai['confidence'],
            }
            analyzed += 1

    save_json(user_key, 'portfolio', data)
    return jsonify({'ok': True, 'analyzed': analyzed, 'data': data})


# ===== 新增：三维数据异步加载端点 =====

@app.route('/api/<user_key>/portfolio/deepseek-ai', methods=['POST'])
def api_deepseek_ai_portfolio(user_key):
    """用 DeepSeek 批量生成 AI 分析"""
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_json(user_key, 'portfolio')
    # 收集需要分析的股票（跳过已有deepseek的）
    to_analyze = []
    for r in data['results']:
        tech = r.get('technical')
        if tech and not r.get('ai_deepseek'):
            to_analyze.append(r)
    if not to_analyze:
        # 如果全都有，也重新生成
        to_analyze = [r for r in data['results'] if r.get('technical')]
    
    ai_results = generate_deepseek_ai_batch(to_analyze)
    for i, r in enumerate(to_analyze):
        if i < len(ai_results):
            ai = ai_results[i]
            r['ai_deepseek'] = {
                'operation_advice': ai['advice'],
                'sentiment_score': ai['sentiment'],
                'analysis_summary': ai['summary'],
                'analysis_detailed': ai['detailed'],
                'target_price': str(ai['target']),
                'stop_loss': str(ai['stop']),
                'confidence_level': ai['confidence'],
            }
    save_json(user_key, 'portfolio', data)
    return jsonify({'ok': True, 'analyzed': len(ai_results), 'data': data})


@app.route('/api/<user_key>/portfolio/financial-data', methods=['POST'])
def api_financial_data(user_key):
    """批量获取财务指标 (PE/PB/ROE)"""
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_json(user_key, 'portfolio')
    count = 0
    for r in data['results']:
        if not r.get('financial'):
            fin = fetch_financial_data(r['code'], r['name'])
            if any(fin.values()):
                r['financial'] = fin
                count += 1
            time.sleep(0.3)
    save_json(user_key, 'portfolio', data)
    return jsonify({'ok': True, 'fetched': count, 'data': data})


@app.route('/api/<user_key>/portfolio/margin-data', methods=['POST'])
def api_margin_data(user_key):
    """批量获取两融数据"""
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_json(user_key, 'portfolio')
    count = 0
    for r in data['results']:
        if not r.get('margin'):
            m = fetch_margin_data(r['code'], r['name'])
            if m:
                r['margin'] = m
                count += 1
            time.sleep(0.3)
    save_json(user_key, 'portfolio', data)
    return jsonify({'ok': True, 'fetched': count, 'data': data})


@app.route('/api/<user_key>/portfolio/pattern-data', methods=['POST'])
def api_pattern_data(user_key):
    """批量获取历史模式识别"""
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_json(user_key, 'portfolio')
    count = 0
    for r in data['results']:
        if not r.get('pattern') and r.get('technical'):
            # 重新获取K线用于模式识别（需要原始收盘价序列）
            klines = fetch_kline_tencent(r['code'], days=120)
            if klines and len(klines) >= 30:
                closes = [k['close'] for k in klines]
                p = run_pattern_recognition(r['code'], closes)
                if p:
                    r['pattern'] = p
                    count += 1
            time.sleep(0.3)
    save_json(user_key, 'portfolio', data)
    return jsonify({'ok': True, 'fetched': count, 'data': data})


@app.route('/api/<user_key>/portfolio/refresh-enriched', methods=['POST'])
def api_refresh_enriched(user_key):
    """一次性刷新所有三维数据（财务+两融+模式识别+DeepSeek AI）"""
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_json(user_key, 'portfolio')
    results = {'financial': 0, 'margin': 0, 'pattern': 0, 'ai': 0}
    
    # 财务 + 两融 + 模式识别（串行，每个股票一次过）
    for r in data['results']:
        code = r['code']
        name = r['name']
        if not r.get('financial'):
            fin = fetch_financial_data(code, name)
            if any(fin.values()):
                r['financial'] = fin
                results['financial'] += 1
        if not r.get('margin'):
            m = fetch_margin_data(code, name)
            if m:
                r['margin'] = m
                results['margin'] += 1
        if not r.get('pattern') and r.get('technical'):
            klines = fetch_kline_tencent(code, days=120)
            if klines and len(klines) >= 30:
                closes = [k['close'] for k in klines]
                p = run_pattern_recognition(code, closes)
                if p:
                    r['pattern'] = p
                    results['pattern'] += 1
        time.sleep(0.3)
    
    # DeepSeek AI 批量
    to_analyze = [r for r in data['results'] if r.get('technical')]
    ai_results = generate_deepseek_ai_batch(to_analyze)
    for i, r in enumerate(to_analyze):
        if i < len(ai_results):
            ai = ai_results[i]
            r['ai_deepseek'] = {
                'operation_advice': ai['advice'],
                'sentiment_score': ai['sentiment'],
                'analysis_summary': ai['summary'],
                'analysis_detailed': ai['detailed'],
                'target_price': str(ai['target']),
                'stop_loss': str(ai['stop']),
                'confidence_level': ai['confidence'],
            }
            results['ai'] += 1
    
    save_json(user_key, 'portfolio', data)
    return jsonify({'ok': True, 'results': results, 'data': data})



@app.route('/api/<user_key>/portfolio/update-stock', methods=['POST'])
def api_update_stock(user_key):
    """修改持仓的成本价和持股数量"""
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(force=True)
    code = data.get('code', '').strip()
    cost = data.get('cost')
    qty = data.get('qty')
    if not code:
        return jsonify({'error': '缺少股票代码'}), 400
    if cost is None and qty is None:
        return jsonify({'error': '请至少提供成本价或持股数量'}), 400
    try:
        if cost is not None:
            cost = float(cost)
        if qty is not None:
            qty = int(qty)
    except (ValueError, TypeError):
        return jsonify({'error': '成本价或持股数量格式不正确'}), 400

    pf = load_json(user_key, 'portfolio')
    found = None
    for r in pf.get('results', []):
        if r['code'] == code:
            r['cost'] = cost if cost is not None else r.get('cost', 0)
            r['qty'] = qty if qty is not None else r.get('qty', 0)
            r['position_cost'] = round(r['cost'] * r['qty'], 2)
            cur = r.get('current', 0) or 0
            r['pnl'] = round((cur - r['cost']) * r['qty'], 2)
            r['pnl_pct'] = round((cur - r['cost']) / r['cost'] * 100, 2) if r['cost'] > 0 else 0
            found = r
            break
    if not found:
        return jsonify({'error': '未找到该股票'}), 404
    # 重新计算持仓总览
    total_cost = sum(x.get('position_cost', x.get('cost',0) * x.get('qty',0)) for x in pf['results'])
    total_value = sum((x.get('current',0) or 0) * x.get('qty',0) for x in pf['results'])
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    pf['total_cost'] = round(total_cost, 2)
    pf['total_value'] = round(total_value, 2)
    pf['total_pnl'] = round(total_pnl, 2)
    pf['total_pnl_pct'] = round(total_pnl_pct, 2)

    save_json(user_key, 'portfolio', pf)
    return jsonify({'ok': True, 'data': pf})


# ===== KOL 荐股跟踪 API =====

@app.route('/api/<user_key>/kol/sources', methods=['GET'])
def api_kol_sources(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_sources()
    return jsonify(data)

@app.route('/api/<user_key>/kol/sources', methods=['POST'])
def api_kol_add_source(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_sources()
    source = request.json.get('source', {})
    if not source.get('id'):
        source['id'] = 'custom_' + str(data.get('last_id', 0) + 1)
        data['last_id'] = data.get('last_id', 0) + 1
    if 'priority' not in source:
        source['priority'] = 'normal'
    if 'active' not in source:
        source['active'] = True
    source.setdefault('platform', '其他')
    data['sources'].append(source)
    save_sources(data)
    return jsonify({'ok': True, 'data': data})

@app.route('/api/<user_key>/kol/sources/<source_id>', methods=['DELETE'])
def api_kol_del_source(user_key, source_id):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_sources()
    data['sources'] = [s for s in data['sources'] if s['id'] != source_id]
    save_sources(data)
    return jsonify({'ok': True, 'data': data})

@app.route('/api/<user_key>/kol/recommendations', methods=['GET'])
def api_kol_recs(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_recs()
    return jsonify(data)

@app.route('/api/<user_key>/kol/recommendations', methods=['POST'])
def api_kol_add_rec(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_recs()
    rec = request.json.get('rec', {})
    code = rec.get('stock_code', '').strip()
    name = rec.get('stock_name', '').strip()
    if not name:
        return jsonify({'error': '请输入股票名称'}), 400
    # 只有代码、没有名称时，从行情API获取
    if not name and code:
        quotes = _fetch_quote([code])
        if quotes and code in quotes:
            rec['stock_name'] = quotes[code].get('name', name)
    # 名称必填，代码选填
    rec['stock_code'] = code
    if not rec.get('id'):
        data['last_id'] = data.get('last_id', 0) + 1
        rec['id'] = 'rec_' + str(data['last_id'])
    rec.setdefault('status', 'tracking')
    rec.setdefault('tracking', {})
    data['recommendations'].append(rec)
    save_recs(data)
    return jsonify({'ok': True, 'data': data})

@app.route('/api/<user_key>/kol/recommendations/<rec_id>', methods=['DELETE'])
def api_kol_del_rec(user_key, rec_id):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_recs()
    data['recommendations'] = [r for r in data['recommendations'] if r['id'] != rec_id]
    save_recs(data)
    return jsonify({'ok': True, 'data': data})

@app.route('/api/<user_key>/kol/recommendations/<rec_id>', methods=['PATCH'])
def api_kol_update_rec(user_key, rec_id):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = load_recs()
    edits = request.json.get('edits', {})
    for r in data['recommendations']:
        if r['id'] == rec_id:
            r.update(edits)
            break
    save_recs(data)
    return jsonify({'ok': True, 'data': data})

@app.route('/api/<user_key>/kol/refresh', methods=['POST'])
def api_kol_refresh(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    updated = update_all_tracking()
    return jsonify({'ok': True, 'updated': updated})

@app.route('/api/<user_key>/kol/stats', methods=['GET'])
def api_kol_stats(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    stats = recalc_stats()
    return jsonify(stats)

@app.route('/api/<user_key>/kol/summarize', methods=['POST'])
def api_kol_summarize(user_key):
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    text = request.json.get('text', '')
    source = request.json.get('source', '')
    if not text:
        return jsonify({'error': 'no text'}), 400
    print(f"[kol summarize] source={source}, text_len={len(text)}")
    import threading
    result_container = [None]
    error_container = [None]
    def do_summarize():
        try:
            result_container[0] = summarize_article(text, source)
        except Exception as e:
            error_container[0] = str(e)
    t = threading.Thread(target=do_summarize)
    t.start()
    t.join(timeout=300)  # 5分钟超时
    if error_container[0]:
        print(f"[kol summarize error] {error_container[0]}")
        return jsonify({'error': 'LLM调用异常: ' + error_container[0]}), 500
    if t.is_alive():
        print("[kol summarize timeout] LLM 响应超时(300s)")
        return jsonify({'error': 'LLM 响应超时，文章可能太长，请分段发送'}), 504
    if result_container[0]:
        return jsonify({'ok': True, 'result': result_container[0]})
    return jsonify({'error': 'LLM 返回空结果，请重试'}), 500

@app.route('/api/<user_key>/portfolio/refresh-stock', methods=['POST'])
def api_refresh_single_stock(user_key):
    """刷新单只股票的全部数据（行情+技术指标+资金流向+财务+模式识别+AI）"""
    if user_key not in USERS:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json(force=True)
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'error': '缺少股票代码'}), 400
    pf = load_json(user_key, 'portfolio')
    r = None
    for item in pf['results']:
        if item['code'] == code:
            r = item
            break
    if not r:
        return jsonify({'error': '未找到该股票'}), 404

    # 刷新实时行情
    quotes = fetch_realtime_quote([code])
    time.sleep(0.3)
    q = quotes.get(code)
    if q:
        r['current'] = q['price']
        r['day_change'] = round(q['change_pct'], 2)
        r['position_value'] = round(q['price'] * r.get('qty', 100))
        cost = r.get('position_cost', r.get('cost', 0) * r.get('qty', 100))
        r['position_cost'] = cost
        r['pnl'] = round(r['position_value'] - cost, 2)
        r['pnl_pct'] = round(r['pnl'] / cost * 100, 2) if cost > 0 else 0
        r['turnover'] = q.get('turnover', 0)
        r['amount_wan'] = q.get('amount_wan', 0)

    # 刷新K线+技术指标
    klines = fetch_kline_tencent(code, days=70)
    if klines:
        tech = compute_indicators(klines)
        if tech:
            r['technical'] = tech

    # 资金流向
    r['money_flow'] = fetch_money_flow(code, r.get('name', ''))

    # 盘口
    if q:
        r['order_book'] = {'bids': q.get('bids', []), 'asks': q.get('asks', [])}

    # 财务
    if not r.get('financial'):
        fin = fetch_financial_data(code, r.get('name', ''))
        if any(fin.values()):
            r['financial'] = fin

    # 两融
    if not r.get('margin'):
        m = fetch_margin_data(code, r.get('name', ''))
        if m:
            r['margin'] = m

    # 模式识别
    if r.get('technical') and not r.get('pattern'):
        pk_lines = fetch_kline_tencent(code, days=120)
        if pk_lines and len(pk_lines) >= 30:
            closes = [k['close'] for k in pk_lines]
            p = run_pattern_recognition(code, closes)
            if p:
                r['pattern'] = p

    # StockHolmes评分
    tech = r.get('technical', {})
    if tech:
        r['stockholmes'] = stockholmes_rules(tech,
            money_flow=r.get('money_flow'), order_book=r.get('order_book'),
            financial=r.get('financial'), pattern=r.get('pattern'),
            turnover=r.get('turnover'), amount_wan=r.get('amount_wan'), day_change=r.get('day_change'))

    # DeepSeek AI
    to_analyze = [r]
    ai_results = generate_deepseek_ai_batch(to_analyze)
    if ai_results:
        ai = ai_results[0]
        r['ai_deepseek'] = {
            'operation_advice': ai['advice'],
            'sentiment_score': ai['sentiment'],
            'analysis_summary': ai['summary'],
            'analysis_detailed': ai['detailed'],
            'target_price': str(ai['target']),
            'stop_loss': str(ai['stop']),
            'confidence_level': ai['confidence'],
        }

    # 重新计算总额
    pf['total_cost'] = sum(x.get('position_cost', 0) for x in pf['results'])
    pf['total_value'] = sum(x.get('position_value', 0) for x in pf['results'])
    pf['total_pnl'] = round(pf['total_value'] - pf['total_cost'], 2)
    pf['total_pnl_pct'] = round(pf['total_pnl'] / pf['total_cost'] * 100, 2) if pf['total_cost'] > 0 else 0
    save_json(user_key, 'portfolio', pf)
    return jsonify({'ok': True, 'data': pf})


if __name__ == '__main__':
    print("StockHolmes Interactive Dashboard v2")
    print(f"  Port: 8082")
    print(f"  天天: http://0.0.0.0:8082/tiantian/")
    print(f"  波波: http://0.0.0.0:8082/bobo/")
    print(f"  Report Center (old): http://0.0.0.0:8081/")
    app.run(host='0.0.0.0', port=8082, debug=False, threaded=True)
