#!/usr/bin/env python3
"""
KOL 荐股跟踪系统
- 记录小红书/公众号博主的推荐股票
- 跟踪推荐后走势，计算胜率
- LLM 自动摘要长文
- rice 付费内容专项分析
"""

import os
import json
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'output' / 'boss' / 'kol_tracker'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ===== 本地 LLM 配置 =====
LLM_URL = 'http://localhost:15126/v1/chat/completions'
LLM_TOKEN = 'a425fdf94a7567401179a00d3eade5e2'
LLM_MODEL = 'openclaw'

# ===== 预设 KOL 来源 =====
DEFAULT_SOURCES = [
    {"id": "xhs_tianying", "name": "天盈", "platform": "小红书", "priority": "normal", "active": True},
    {"id": "xhs_jinmao", "name": "金猫理财", "platform": "小红书", "priority": "normal", "active": True},
    {"id": "xhs_qinglong", "name": "擒龙青鹰", "platform": "小红书", "priority": "normal", "active": True},
    {"id": "xhs_sunge", "name": "趋势孙哥", "platform": "小红书", "priority": "normal", "active": True},
    {"id": "xhs_qiudao", "name": "求道作手", "platform": "小红书", "priority": "normal", "active": True},
    {"id": "xhs_guanchao", "name": "观潮", "platform": "小红书", "priority": "normal", "active": True},
    {"id": "rice", "name": "rice", "platform": "公众号付费", "priority": "high", "active": True},
]

# ===== 数据文件路径 =====
def _sources_path():
    return DATA_DIR / 'kol_sources.json'

def _recs_path():
    return DATA_DIR / 'kol_recommendations.json'

def _stats_path():
    return DATA_DIR / 'kol_stats.json'

def load_sources():
    p = _sources_path()
    if not p.exists():
        data = {"sources": DEFAULT_SOURCES, "last_id": 7}
        save_sources(data)
        return data
    with open(p) as f:
        return json.load(f)

def save_sources(data):
    with open(_sources_path(), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_recs():
    p = _recs_path()
    if not p.exists():
        data = {"recommendations": [], "last_id": 0}
        save_recs(data)
        return data
    with open(p) as f:
        return json.load(f)

def save_recs(data):
    with open(_recs_path(), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_stats():
    p = _stats_path()
    if not p.exists():
        data = {}
        save_stats(data)
        return data
    with open(p) as f:
        return json.load(f)

def save_stats(data):
    with open(_stats_path(), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===== 腾讯行情 API =====
def get_market_prefix(code):
    return 'sh' if str(code)[0] in ('6', '9') else 'sz'

def fetch_realtime_quote(codes):
    """获取实时行情"""
    if not codes:
        return {}
    codes_str = ','.join(get_market_prefix(c) + c for c in codes)
    url = f'http://qt.gtimg.cn/q={codes_str}'
    try:
        req = urllib.request.Request(url, headers={'Referer': 'https://finance.qq.com/'})
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read().decode('gbk', errors='ignore')
        results = {}
        for line in text.strip().split('\n'):
            if '~' not in line:
                continue
            parts = line.split('~')
            if len(parts) < 35:
                continue
            code = parts[2]
            results[code] = {
                'name': parts[1],
                'price': float(parts[3]) if parts[3] else 0,
                'prev_close': float(parts[4]) if parts[4] else 0,
                'open': float(parts[5]) if parts[5] else 0,
                'volume': int(parts[6]) if parts[6] else 0,
                'change_pct': float(parts[32]) if parts[32] else 0,
                'high': float(parts[33]) if parts[33] else 0,
                'low': float(parts[34]) if parts[34] else 0,
            }
        return results
    except Exception as e:
        print(f'[quote fetch error] {e}')
        return {}

def fetch_historical_price(code, target_date):
    """获取指定日期的收盘价（用腾讯API）"""
    secid = get_market_prefix(code) + code
    # 用腾讯日K线
    url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={secid},day,{target_date},{target_date},1,qfq'
    try:
        req = urllib.request.Request(url, headers={'Referer': 'https://finance.qq.com/'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        klines = data.get('data', {}).get(secid, {}).get('day', [])
        if not klines:
            klines = data.get('data', {}).get(secid, {}).get('qfqday', [])
        if klines:
            # [date, open, close, high, low, volume]
            return float(klines[0][2])  # 收盘价
    except Exception as e:
        print(f'[historical price error {code} {target_date}] {e}')
    return None

# ===== LLM 文章摘要 =====
def summarize_article(article_text, source_name=""):
    """用本地 LLM 总结长文，提取荐股信息"""
    prompt = f"""你是一位专业的股票分析助手。请帮我总结以下文章，并按 JSON 格式输出：

{{
  "summary": "200字以内的文章核心摘要",
  "stocks": [
    {{"code": "股票代码(6位)", "name": "股票名称", "reason": "推荐理由/逻辑(50字以内)", "operation": "操作建议(如：买入/持有/卖出/仓位X成/目标价XX等)"}}
  ],
  "key_points": ["关键数据或观点1", "关键数据或观点2", "关键数据或观点3"]
}}

文章来源：{source_name}
文章内容：
{article_text[:8000]}

请严格输出 JSON，不要其他内容。如果文章没有推荐具体股票，stocks 为空数组。"""

    try:
        payload = json.dumps({
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 2000,
        }).encode('utf-8')
        req = urllib.request.Request(
            LLM_URL,
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {LLM_TOKEN}',
            },
            method='POST',
        )
        resp = urllib.request.urlopen(req, timeout=300)
        result = json.loads(resp.read().decode('utf-8'))
        content = result['choices'][0]['message']['content']
        # 提取 JSON
        if '```' in content:
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
        return json.loads(content.strip())
    except Exception as e:
        print(f'[LLM summary error] {e}')
        return None

# ===== 跟踪计算 =====
TRACKING_DAYS = [1, 3, 5, 10]

def update_tracking_for_rec(rec):
    """更新单条荐股的跟踪数据"""
    code = rec['stock_code']
    rec_date = rec['recommend_date']  # "2026-05-07"
    
    try:
        base_date = datetime.strptime(rec_date, '%Y-%m-%d')
    except:
        return

    # 获取推荐日收盘价作为基准
    if 'base_price' not in rec or rec.get('base_price') == 0:
        bp = fetch_historical_price(code, rec_date)
        if bp:
            rec['base_price'] = bp
        elif 'recommend_price' in rec and rec['recommend_price']:
            rec['base_price'] = rec['recommend_price']
        else:
            return

    base_price = rec['base_price']
    tracking = rec.get('tracking', {})
    
    for days in TRACKING_DAYS:
        key = f'd{days}'
        if key in tracking and tracking[key].get('price'):
            continue  # 已有数据
        
        target_date = base_date + timedelta(days=days)
        # 跳过周末
        while target_date.weekday() >= 5:
            target_date += timedelta(days=1)
        date_str = target_date.strftime('%Y-%m-%d')
        
        price = fetch_historical_price(code, date_str)
        if price and price > 0:
            pnl_pct = round((price - base_price) / base_price * 100, 2)
            tracking[key] = {
                'date': date_str,
                'price': price,
                'pnl_pct': pnl_pct,
            }
    
    rec['tracking'] = tracking
    
    # 计算最大收益和最大回撤
    all_prices = [v.get('price', 0) for v in tracking.values() if v.get('price')]
    if all_prices:
        rec['max_gain_pct'] = round(max((p - base_price) / base_price * 100 for p in all_prices), 2)
        rec['max_drawdown_pct'] = round(min((p - base_price) / base_price * 100 for p in all_prices), 2)
    
    # 判定最终结果（d10 有数据后判定）
    if 'd10' in tracking and tracking['d10'].get('price') and rec.get('status') == 'tracking':
        pnl = tracking['d10']['pnl_pct']
        if pnl >= 5:
            rec['final_result'] = 'win'
        elif pnl <= -5:
            rec['final_result'] = 'loss'
        else:
            rec['final_result'] = 'breakeven'
        rec['status'] = 'closed'

def update_all_tracking():
    """批量更新所有跟踪中的荐股"""
    recs_data = load_recs()
    updated = 0
    for rec in recs_data['recommendations']:
        if rec.get('status') == 'tracking':
            update_tracking_for_rec(rec)
            updated += 1
            time.sleep(0.3)
    save_recs(recs_data)
    
    # 更新统计
    recalc_stats()
    return updated

def recalc_stats():
    """重新计算所有 KOL 的统计数据"""
    recs_data = load_recs()
    sources_data = load_sources()
    stats = {}
    
    for src in sources_data['sources']:
        sid = src['id']
        recs = [r for r in recs_data['recommendations'] if r.get('source_id') == sid]
        closed = [r for r in recs if r.get('status') == 'closed']
        wins = [r for r in closed if r.get('final_result') == 'win']
        losses = [r for r in closed if r.get('final_result') == 'loss']
        breakeven = [r for r in closed if r.get('final_result') == 'breakeven']
        
        total_recs = len(recs)
        completed = len(closed)
        
        avg_returns = []
        max_gains = []
        max_drawdowns = []
        for r in closed:
            if 'd10' in r.get('tracking', {}):
                avg_returns.append(r['tracking']['d10'].get('pnl_pct', 0))
            if r.get('max_gain_pct') is not None:
                max_gains.append(r['max_gain_pct'])
            if r.get('max_drawdown_pct') is not None:
                max_drawdowns.append(r['max_drawdown_pct'])
        
        stats[sid] = {
            'name': src['name'],
            'platform': src['platform'],
            'priority': src['priority'],
            'total_recs': total_recs,
            'completed': completed,
            'wins': len(wins),
            'losses': len(losses),
            'breakeven': len(breakeven),
            'win_rate': round(len(wins) / len(closed) * 100, 1) if completed > 0 else 0,
            'avg_return': round(sum(avg_returns) / len(avg_returns), 2) if avg_returns else 0,
            'avg_max_gain': round(sum(max_gains) / len(max_gains), 2) if max_gains else 0,
            'avg_max_drawdown': round(sum(max_drawdowns) / len(max_drawdowns), 2) if max_drawdowns else 0,
            'active': src.get('active', True),
        }
    
    save_stats(stats)
    return stats

if __name__ == '__main__':
    print("KOL Tracker initialized")
    print(f"Data dir: {DATA_DIR}")
    load_sources()
    load_recs()
    load_stats()
    print("✅ All data files ready")
