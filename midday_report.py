#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
午间复盘 & 财经简报 v2
交易日 11:35 自动触发，替换旧午间新闻

数据源：
- 大盘指数/个股行情：腾讯 API (qt.gtimg.cn)
- 昨日成交额对比：腾讯 K-line API
- 涨跌家数/涨停跌停/板块排行：mx-xuangu
- 资金流向/龙虎榜：mx-xuangu + capital_flow.py
- 北向资金/盘中消息：mx-search
- 持仓数据：dashboard JSON + extra_holdings.json

用法：
    python3 midday_report.py --user boss
    python3 midday_report.py --user boyfriend
"""
import sys, json, os, re, urllib.request, time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

BASE = '/home/admin/.openclaw/workspace/daily_stock_analysis'
sys.path.insert(0, BASE)
sys.path.insert(0, BASE + '/../skills/mx-xuangu')
sys.path.insert(0, BASE + '/../skills/mx-search')

from mx_xuangu import MXSelectStock
mx = MXSelectStock()

try:
    from capital_flow import _parse_float, _gv
except ImportError:
    def _parse_float(v):
        if isinstance(v, (int, float)): return v
        if isinstance(v, str):
            v = v.strip().replace(',', '').replace('元', '').replace('亿', 'e8').replace('亿', 'e8').replace('万', 'e4').replace('手', '')
            try:
                if 'e' in v.lower(): return float(v)
                return float(v)
            except: return 0.0
        return 0.0

    def _gv(row, hint, default='0'):
        for k in row:
            if hint in k: return row[k]
        return default

# -------- 缓存 --------
_cache_capital_inflow = None
_cache_news = None

# ========== 数据收集 ==========

def fetch_tencent(code: str) -> Dict[str, str]:
    url = f"https://qt.gtimg.cn/q={code}"
    try:
        r = urllib.request.urlopen(url, timeout=10)
        raw = r.read().decode('gbk', errors='replace')
        parts = raw.split('~')
        return {i: parts[i] if i < len(parts) else '' for i in range(50)}
    except:
        return {}


def get_yesterday_index() -> Dict[str, float]:
    """昨日指数数据（成交额对比用）"""
    codes = [('sh000001', '上证'), ('sz399001', '深证'), ('sz399006', '创业板'), ('sh000688', '科创50')]
    result = {}
    for mc, name in codes:
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mc},day,,,2,qfq"
        try:
            r = urllib.request.urlopen(url, timeout=10)
            data = json.loads(r.read())
            klines = data.get('data', {}).get(mc, {}).get('qfqday', [])
            if len(klines) >= 2:
                # kline format: [date, open, close, high, low, volume, amount]
                yesterday = klines[-2]
                yest_amount = _parse_float(yesterday[6]) if len(yesterday) > 6 else 0
                result[name] = {'close': _parse_float(yesterday[2]), 'amount': yest_amount}
            elif len(klines) >= 1:
                today = klines[-1]
                today_amount = _parse_float(today[6]) if len(today) > 6 else 0
                result[name] = {'close': _parse_float(today[2]), 'amount': today_amount}
        except:
            result[name] = {'close': 0, 'amount': 0}
    return result


def search_mx(query: str, limit: int = 50) -> List[Dict]:
    try:
        r = mx.search(query)
        rows, src, err = mx.extract_data(r)
        return rows[:limit] if rows else []
    except:
        return []


def get_market_overview() -> Dict[str, Any]:
    """大盘概况"""
    codes = {'上证': 'sh000001', '深证': 'sz399001', '创业板': 'sz399006', '科创50': 'sh000688'}
    result = {}
    for name, code in codes.items():
        d = fetch_tencent(code)
        raw_vol = _parse_float(d.get(37, '0'))
        vol_yuan = raw_vol * 10000  # Tencent returns 万元 for indices
        change_v = d.get(31, '0')
        try:
            change_v = float(change_v) if change_v else 0
        except:
            change_v = 0
        result[name] = {
            'price': d.get(3, '0'),
            'pct': d.get(32, '0'),
            'change': change_v,
            'volume': vol_yuan,
            'high': d.get(33, '0'),
            'low': d.get(34, '0'),
            'name': name,
        }
    return result


def get_market_stats() -> Dict[str, Any]:
    """涨跌家数/涨停跌停/炸板率"""
    stats = {}
    up_count = search_mx("今日涨幅大于0 的A股", 1000)
    stats['上涨家数'] = len(up_count)
    down_count = search_mx("今日涨幅小于0 的A股", 1000)
    stats['下跌家数'] = len(down_count)
    
    up_limit = search_mx("今日涨停 的A股", 500)
    stats['涨停家数'] = len(up_limit)
    
    down_limit = search_mx("今日跌停 的A股", 500)
    stats['跌停家数'] = len(down_limit)
    
    touched = search_mx("今日曾涨停 的A股", 500)
    stats['曾涨停家数'] = len(touched)
    
    from_limits = len(touched)
    actual_up = stats['涨停家数']
    stats['炸板家数'] = max(0, from_limits - actual_up)
    stats['炸板率'] = round((from_limits - actual_up) / from_limits * 100, 1) if from_limits > 0 else 0
    
    return stats


def get_northbound() -> Dict[str, Any]:
    """北向资金（从mx-search获取）"""
    try:
        # Try mx-search for northbound data
        from mx_search import MXSearch
        s = MXSearch()
        r = s.search("北向资金 今日净流入")
        return {'data': str(r)[:200] if r else '暂无北向数据'}
    except:
        return {'data': '暂无数据'}


def get_sector_ranking() -> Tuple[List, List]:
    up = search_mx("今日板块涨幅排名前10", 10)
    down = search_mx("今日板块涨幅排名后10", 10)
    return up, down


def get_sector_fund_flow() -> List[Dict]:
    """板块资金流向"""
    return search_mx("今日主力资金净流入排名前20的行业板块", 10)


def get_dragon_tiger() -> List[Dict]:
    """龙虎榜"""
    rows = search_mx("龙虎榜 今日", 50)
    result = []
    for r in rows:
        result.append({
            'name': _gv(r, '名称'), 'code': _gv(r, '代码'),
            'pct': _parse_float(_gv(r, '涨跌幅')),
            'reason': _gv(r, '龙虎榜上榜原因'),
            'price': _parse_float(_gv(r, '最新价')),
            'buy_inst': _parse_float(_gv(r, '机构买入')),
            'sell_inst': _parse_float(_gv(r, '机构卖出')),
        })
    return result


def search_news_query(query: str, max_items: int = 5) -> List[Dict]:
    """盘中消息搜索"""
    global _cache_news
    if _cache_news:
        return _cache_news[:max_items]
    
    try:
        from mx_search import MXSearch
        s = MXSearch()
        r = s.search(query)
        if isinstance(r, list):
            _cache_news = r[:10]
            return r[:max_items]
        if isinstance(r, dict):
            items = r.get('results', r.get('data', r.get('items', [])))
            if isinstance(items, list):
                _cache_news = items[:10]
                return items[:max_items]
        return []
    except:
        return []


def get_stock_realtime(codes: List[str]) -> Dict[str, Dict]:
    """批量获取个股实时行情"""
    if not codes:
        return {}
    codes_dedup = list(set(codes))
    qstr = ','.join([f'{c[:2]}{c[2:]}' for c in codes_dedup])
    url = f"https://qt.gtimg.cn/q={qstr}"
    try:
        r = urllib.request.urlopen(url, timeout=10)
        raw = r.read().decode('gbk', errors='replace')
    except:
        return {}
    
    result = {}
    for line in raw.strip().split('\n'):
        parts = line.split('~')
        if len(parts) < 40:
            continue
        code_full = parts[2] if len(parts) > 2 else ''
        code_prefix = 'sh' if code_full.startswith('6') else ('bj' if code_full.startswith('9') else 'sz')
        code_with_market = f'{code_prefix}{code_full}'
        name = parts[1]
        result[code_with_market] = {
            'name': name,
            'price': _parse_float(parts[3] if len(parts) > 3 else '0'),
            'pct': _parse_float(parts[32] if len(parts) > 32 else '0'),
            'volume': _parse_float(parts[37] if len(parts) > 37 else '0'),
            'turnover': _parse_float(parts[38] if len(parts) > 38 else '0'),
            'high': _parse_float(parts[33] if len(parts) > 33 else '0'),
            'low': _parse_float(parts[34] if len(parts) > 34 else '0'),
            'open': _parse_float(parts[5] if len(parts) > 5 else '0'),
            'pre_close': _parse_float(parts[4] if len(parts) > 4 else '0'),
        }
    return result


def get_cached_capital_inflow():
    global _cache_capital_inflow
    if _cache_capital_inflow is None:
        try:
            from capital_flow import get_full_day_capital_flow
            _cache_capital_inflow = get_full_day_capital_flow("inflow", 5, "all")
        except:
            pass
    return _cache_capital_inflow or []


# ========== 持仓数据 ==========

def load_holdings(user_key: str) -> List[Dict]:
    holdings = []
    if user_key == 'boss':
        path = f'{BASE}/output/boss/portfolio_dashboard.json'
        if os.path.exists(path):
            with open(path) as f:
                d = json.load(f)
            holdings = d.get('results', [])
    else:
        dash = f'{BASE}/output/boyfriend/portfolio_dashboard.json'
        if os.path.exists(dash):
            with open(dash) as f:
                d = json.load(f)
            holdings = d.get('results', [])
        old = f'{BASE}/output/portfolio_data.json'
        if os.path.exists(old):
            with open(old) as f:
                d = json.load(f)
            existing = {h['code'] for h in holdings}
            for r in d.get('results', []):
                if r['code'] not in existing:
                    holdings.append(r)
    
    # extra holdings
    extra = f'{BASE}/output/{user_key}/extra_holdings.json'
    if os.path.exists(extra):
        with open(extra) as f:
            extras = json.load(f)
        existing = {h['code'] for h in holdings}
        for e in extras:
            if e['code'] not in existing:
                holdings.append({'code': e['code'], 'name': e['name'], 'cost': e.get('cost', 0), 'from_extra': True})
    return holdings


def load_watchlist(user_key: str) -> List[Dict]:
    if user_key != 'boss':
        return []
    path = f'{BASE}/output/boss/portfolio_dashboard.json'
    if os.path.exists(path):
        with open(path) as f:
            d = json.load(f)
        return d.get('watchlist', [])
    return []


# ========== 持仓分析 ==========

def analyze_holdings(holdings: List[Dict], overview: Dict, dragon: List[Dict] = None) -> List[Dict]:
    codes = [f"sz{h['code']}" if not h['code'].startswith('6') else f"sh{h['code']}" for h in holdings]
    codes_dedup = list(set(codes))
    quotes = get_stock_realtime(codes_dedup)
    
    results = []
    for h in holdings:
        code = h['code']
        # Handle bj stocks
        mkt_code = f"sh{code}" if code.startswith('6') else (f"sz{code}" if not code.startswith('9') else f"bj{code}")
        q = quotes.get(mkt_code, {})
        
        pct = q.get('pct', 0)
        cost = h.get('cost', 0)
        price = q.get('price', 0)
        pnl_pct = ((price - cost) / cost * 100) if cost > 0 else 0
        
        sh_pct = _parse_float(overview.get('上证', {}).get('pct', '0'))
        beat_market = "跑赢" if pct > sh_pct else ("跑输" if pct < sh_pct else "持平")
        
        # 板块对比
        sector = h.get('sector', h.get('板块名称', ''))
        
        # 盘中异动信号
        high = q.get('high', 0)
        low = q.get('low', 0)
        pre_close = q.get('pre_close', 0)
        amplitude = ((high - low) / pre_close * 100) if pre_close > 0 else 0
        turnover = q.get('turnover', 0)
        
        signals = []
        if amplitude > 5:
            signals.append("⚠️ 振幅较大")
        if turnover > 15:
            signals.append("放量活跃")
        if turnover < 1 and abs(pct) < 1:
            signals.append("缩量横盘")
        if pct > 5:
            signals.append("强势拉升")
        if pct < -4:
            signals.append("大幅回调")
        
        # 龙虎榜交叉匹配
        cross_dragon = []
        if dragon:
            for d in dragon:
                if d.get('code') == code or d.get('name') in h.get('name', ''):
                    cross_dragon.append(d)
        
        if cross_dragon:
            for d in cross_dragon:
                signals.append(f"📋 龙虎榜: {d.get('reason','')[:20]}")
        
        # 操作建议
        advice = "持有"
        reasons = []
        
        if pct > 3 and pnl_pct > 8:
            advice = "可考虑止盈部分"
            reasons.append(f"涨幅{pct:.1f}%且浮盈{pnl_pct:.1f}%已可观")
        elif pct < -3 and pnl_pct < -8:
            advice = "⚠️ 注意止损"
            reasons.append(f"跌破{pct:.1f}%且浮亏{pnl_pct:.1f}%")
        elif pct < -2:
            advice = "观望，不急于加仓"
            reasons.append(f"下跌趋势中，等待企稳")
        elif pct > 2 and pnl_pct < -3:
            advice = "反弹中，持有观察"
            reasons.append(f"今日反弹{pct:.1f}%但尚未回本")
        elif turnover > 12 and pct > 0:
            advice = "量价齐升，持有"
            reasons.append(f"换手率{turnover:.1f}%，量能充足")
        elif pnl_pct > 0:
            advice = "浮盈持有"
            reasons.append("趋势向上")
        else:
            reasons.append("窄幅震荡，等待方向")
        
        results.append({
            'name': h['name'], 'code': code, 'cost': cost,
            'price': price, 'pct': pct, 'pnl_pct': pnl_pct,
            'volume': q.get('volume', 0), 'turnover': turnover,
            'beat_market': beat_market, 'signals': signals,
            'advice': advice, 'reasons': reasons,
            'amplitude': amplitude, 'sector': sector,
            'from_extra': h.get('from_extra', False),
        })
    
    return results


def analyze_watchlist(watchlist: List[Dict], quotes: Dict) -> List[Dict]:
    """自选股信号分析"""
    results = []
    for w in watchlist:
        code = w['code']
        mkt_code = f"sh{code}" if code.startswith('6') else f"sz{code}"
        q = quotes.get(mkt_code, {})
        if not q.get('price'):
            continue
        
        pct = q.get('pct', 0)
        pre_close = q.get('pre_close', 0)
        price = q.get('price', 0)
        high = q.get('high', 0)
        low = q.get('low', 0)
        amplitude = ((high - low) / pre_close * 100) if pre_close > 0 else 0
        turnover = q.get('turnover', 0)
        
        signals = []
        if pct > 3:
            signals.append("📈 强势上涨")
        if pct < -3:
            signals.append("📉 明显回调")
        if amplitude > 5:
            signals.append("⚠️ 振幅较大")
        if turnover > 10:
            signals.append("🔥 放量活跃")
        if 0 < pct < 1:
            signals.append("➡️ 窄幅震荡")
        
        results.append({
            'name': w.get('name', w.get('股票名称', '')), 'code': code,
            'price': price, 'pct': pct, 'turnover': turnover,
            'amplitude': amplitude, 'signals': signals,
        })
    
    results.sort(key=lambda x: abs(x['pct']), reverse=True)
    return results


# ========== 格式化工具 ==========

def fmt_vol(v: float) -> str:
    if v >= 100000000:
        return f"{v/100000000:.0f}亿"
    if v >= 10000:
        return f"{v/10000:.0f}万"
    return f"{v:.0f}"

def fmt_pct(v: float) -> str:
    if v >= 0.005: return f"+{v:.2f}%"
    if v <= -0.005: return f"{v:.2f}%"
    return "0.00%"

def fmt_emoji_pct(v: float) -> str:
    if v > 3: return f"🟢 {v:+.2f}%"
    if v > 0: return f"🟢 {v:+.2f}%"
    if v > -3: return f"🔴 {v:+.2f}%"
    return f"⛔ {v:+.2f}%"


# ========== 文本报告生成 ==========

def gen_text_report(user_key: str) -> str:
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d %H:%M')
    holder_name = "天天" if user_key == "boss" else "波波"
    sec_nums = ['一','二','三','四','五','六','七','八','九','十']
    sec = 0
    
    lines = [
        f"📊 **午间复盘 | {today_str}**",
        "─" * 40, "",
    ]
    
    # ===== 一、大盘与市场 =====
    sec += 1
    lines.append(f"**{sec_nums[sec-1]}、大盘与市场**")
    overview = get_market_overview()
    yest = get_yesterday_index()
    
    for name in ['上证', '深证', '创业板', '科创50']:
        d = overview.get(name, {})
        pct = _parse_float(d.get('pct', '0'))
        vol = d.get('volume', 0)
        y_vol = yest.get(name, {}).get('amount', 0)
        vol_diff = ((vol - y_vol) / y_vol * 100) if y_vol > 0 else 0
        vol_ind = "📈放量" if vol_diff > 10 else ("📉缩量" if vol_diff < -10 else "持平")
        lines.append(f"  **{name}**: {d.get('price','?')} ({fmt_pct(pct)}) 成交{fmt_vol(vol)} | {vol_ind}({fmt_pct(vol_diff)})")
    
    # 两市总成交
    sh_vol = overview.get('上证', {}).get('volume', 0)
    sz_vol = overview.get('深证', {}).get('volume', 0)
    total_vol = sh_vol + sz_vol
    sh_y = yest.get('上证', {}).get('amount', 0)
    sz_y = yest.get('深证', {}).get('amount', 0)
    total_y = sh_y + sz_y
    total_diff = ((total_vol - total_y) / total_y * 100) if total_y > 0 else 0
    lines.append(f"  💰 两市合计: {fmt_vol(total_vol)} | 较昨日{fmt_pct(total_diff)}")
    lines.append("")
    
    # 情绪指标
    stats = get_market_stats()
    lines.append(f"  **市场情绪**")
    lines.append(f"  📈 上涨{stats.get('上涨家数','?')}家 📉 下跌{stats.get('下跌家数','?')}家")
    lines.append(f"  ⬆ 涨停{stats.get('涨停家数',0)}家 ⬇ 跌停{stats.get('跌停家数',0)}家 💥 炸板{stats.get('炸板家数',0)}家 (炸板率{stats.get('炸板率',0)}%)")
    lines.append("")
    
    # ===== 二、市场主线 =====
    sec += 1
    lines.append(f"**{sec_nums[sec-1]}、市场主线**")
    up_sectors, down_sectors = get_sector_ranking()
    
    if up_sectors:
        lines.append("  **领涨板块**:")
        for r in up_sectors[:3]:
            n = _gv(r, '名称'); p = _parse_float(_gv(r, '涨跌幅'))
            lines.append(f"    📈 {n} {fmt_pct(p)}")
    if down_sectors:
        lines.append("  **领跌板块**:")
        for r in down_sectors[:3]:
            n = _gv(r, '名称'); p = _parse_float(_gv(r, '涨跌幅'))
            lines.append(f"    📉 {n} {fmt_pct(p)}")
    
    # 板块资金流向
    sector_fund = get_sector_fund_flow()
    if sector_fund:
        lines.append("  **板块资金流入**:")
        for r in sector_fund[:3]:
            n = _gv(r, '名称'); net = _parse_float(_gv(r, '主力净额'))
            lines.append(f"    🟢 {n} {fmt_vol(net)}")
    lines.append("")
    
    # 北向资金
    nb = get_northbound()
    if nb.get('data') and '暂无' not in nb['data']:
        lines.append(f"  **北向资金**: {nb['data'][:100]}")
    else:
        lines.append("  🌐 北向数据暂不可用")
    lines.append("")
    
    # ===== 三、持仓复盘 =====
    sec += 1
    lines.append(f"**{sec_nums[sec-1]}、{holder_name}持仓复盘**")
    
    holdings = load_holdings(user_key)
    dragon = get_dragon_tiger()
    
    if holdings:
        results = analyze_holdings(holdings, overview, dragon)
        
        # 先总计
        up_count = sum(1 for r in results if r['pct'] > 0)
        down_count = sum(1 for r in results if r['pct'] < 0)
        total_pnl = sum(r['pnl_pct'] for r in results if r['cost'] > 0)
        avg_pnl = total_pnl / len([r for r in results if r['cost'] > 0]) if any(r['cost'] > 0 for r in results) else 0
        lines.append(f"  仓位{len(results)}只 | 上涨{up_count}只 下跌{down_count}只 | 平均浮盈{avg_pnl:+.1f}%")
        lines.append("")
        
        for r in results:
            tag = "📈" if r['pct'] >= 0 else "📉"
            lines.append(f"  **{r['name']}({r['code']})** {tag} {fmt_pct(r['pct'])}")
            lines.append(f"  现价{r['price']:.2f} | 浮盈{r['pnl_pct']:+.1f}% | {r['beat_market']}大盘 | 换手{r['turnover']:.1f}%")
            if r['signals']:
                for s in r['signals']:
                    lines.append(f"  {s}")
            lines.append(f"  💡 **建议**: {r['advice']}")
            for reason in r['reasons']:
                lines.append(f"  · {reason}")
            lines.append("")
    else:
        lines.append("  （暂无持仓数据）")
    
    # ===== 四、自选股跟踪（天天）=====
    if user_key == "boss":
        sec += 1
        lines.append(f"**{sec_nums[sec-1]}、自选股跟踪**")
        wl = load_watchlist(user_key)
        if wl:
            wl_codes = [f"sz{w['code']}" if not w['code'].startswith('6') else f"sh{w['code']}" for w in wl]
            wl_quotes = get_stock_realtime(wl_codes)
            wl_analyzed = analyze_watchlist(wl, wl_quotes)
            
            if wl_analyzed:
                lines.append(f"  自选{len(wl_analyzed)}只 | 异动跟踪:")
                for w in wl_analyzed[:8]:
                    lines.append(f"  **{w['name']}({w['code']})** {fmt_emoji_pct(w['pct'])} 换手{w['turnover']:.1f}%")
                    for s in w['signals']:
                        lines.append(f"    {s}")
            else:
                lines.append("  （自选股无实时数据）")
        else:
            lines.append("  （暂无自选股数据）")
        lines.append("")
    
    # ===== 五、龙虎榜 & 资金流向 =====
    sec += 1
    lines.append(f"**{sec_nums[sec-1]}、龙虎榜 & 资金流向**")
    
    if dragon:
        # 机构买入重点
        inst_buy = [d for d in dragon if d.get('buy_inst', 0) > 0][:3]
        if inst_buy:
            lines.append("  🏦 **机构买入**:")
            for d in inst_buy:
                lines.append(f"    {d['name']}({d['code']}) {fmt_pct(d['pct'])} | 买入{d['buy_inst']:.1f}万")
        lines.append("  📋 **龙虎榜重点**:")
        for d in dragon[:3]:
            lines.append(f"    {d['name']}({d['code']}) {fmt_pct(d['pct'])} | {d.get('reason','')[:25]}")
    else:
        lines.append("  📋 龙虎榜数据暂不可用")
    
    inflow = get_cached_capital_inflow()
    if inflow:
        lines.append("  🟢 **主力净流入TOP3**:")
        for r in inflow[:3]:
            lines.append(f"    {r['name']}({r['code']}) +{r['main_net']:.2f}亿 | {r['pct']:+.1f}%")
    lines.append("")
    
    # ===== 六、午间简报（盘中消息） =====
    sec += 1
    lines.append(f"**{sec_nums[sec-1]}、午间简报**")
    
    news_queries = [
        "今日盘中 重大新闻 政策",
        "今日盘中 行业板块 消息",
    ]
    news_found = False
    for q in news_queries:
        news = search_news_query(q, 3)
        if news:
            news_found = True
            break
    
    if news_found:
        for n in news:
            if isinstance(n, dict):
                title = n.get('title', n.get('name', str(n)))[:60]
                content = n.get('content', n.get('description', ''))[:100]
                lines.append(f"  📰 {title}")
                if content and content != title:
                    lines.append(f"    {content}")
    else:
        # 备选：从板块数据推断
        if up_sectors:
            top_n = _gv(up_sectors[0], '名称')
            lines.append(f"  📰 **{top_n}** 领涨")
        if down_sectors:
            bot_n = _gv(down_sectors[0], '名称')
            lines.append(f"  📰 **{bot_n}** 领跌")
    lines.append("")
    
    # ===== 七、下午提示 =====
    sec += 1
    lines.append(f"**{sec_nums[sec-1]}、下午交易提示**")
    
    sh_pct = _parse_float(overview.get('上证', {}).get('pct', '0'))
    up_c = stats.get('上涨家数', 0)
    dn_c = stats.get('下跌家数', 0)
    zt = stats.get('涨停家数', 0)
    dt = stats.get('跌停家数', 0)
    
    tips = []
    if sh_pct < -1:
        tips.append(("⚠️", "大盘跌幅较大，控制仓位，谨慎操作"))
    elif sh_pct > 1:
        tips.append(("✅", "大盘强势，持股为主，关注尾盘能否守住涨幅"))
    else:
        tips.append(("👀", "大盘窄幅震荡，关注下午方向选择"))
    
    if up_c > 0 and dn_c > 0:
        ratio = up_c / dn_c if dn_c > 0 else 0
        if ratio > 1.5:
            tips.append(("🔥", "涨跌比偏暖，市场赚钱效应较好"))
        elif ratio < 0.7:
            tips.append(("⚠️", "涨跌比偏冷，市场赚钱效应差"))
    
    if zt > 100:
        tips.append(("🔥", f"涨停{zt}只，短线情绪活跃"))
    if dt > 20:
        tips.append(("⚠️", f"跌停{dt}只，注意风险标的"))
    
    # 持仓专属风险
    if holdings and results:
        risk_stocks = [r for r in results if r['pct'] < -3 or r['pnl_pct'] < -8]
        if risk_stocks:
            tips.append(("⚠️", "持仓风险: " + ", ".join([f"{r['name']}({fmt_pct(r['pct'])})" for r in risk_stocks[:3]])))
    
    for icon, text in tips:
        lines.append(f"  {icon} {text}")
    
    lines.append("")
    lines.extend([
        "─" * 40,
        "⚠️ 仅供参考，不构成投资建议",
        f"🕵️‍♂️ StockHolmes · 午间复盘报告"
    ])
    
    return "\n".join(lines)


# ========== HTML报告生成 ==========

def gen_html_report(user_key: str) -> str:
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    holder_name = "邓天天" if user_key == "boss" else "波波"
    
    overview = get_market_overview()
    stats = get_market_stats()
    up_sectors, down_sectors = get_sector_ranking()
    holdings = load_holdings(user_key)
    dragon = get_dragon_tiger()
    yest = get_yesterday_index()
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>午间复盘 | {today_str}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f5f6fa;color:#333;padding:16px;max-width:800px;margin:0 auto}}
.header{{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;border-radius:12px;padding:20px;margin-bottom:16px}}
.header h1{{font-size:20px;margin-bottom:4px}}
.header .sub{{font-size:13px;color:#8899cc}}
.section{{background:#fff;border-radius:10px;padding:16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.section h2{{font-size:16px;color:#1a1a2e;margin:0 0 12px;padding:0 0 8px;border-bottom:2px solid #e8e8e8}}
.index-row{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:8px}}
.index-item{{background:#f8f9ff;border-radius:8px;padding:10px 14px;flex:1;min-width:120px}}
.index-item .name{{font-size:12px;color:#666}}
.index-item .price{{font-size:20px;font-weight:700}}
.index-item .pct{{font-size:13px}}
.index-item .vol{{font-size:11px;color:#888}}
.pct-up{{color:#e74c3c}}
.pct-down{{color:#27ae60}}
.stat-box{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px}}
.stat-item{{background:#f8f9ff;border-radius:8px;padding:8px 12px;text-align:center;flex:1;min-width:70px}}
.stat-item .num{{font-size:18px;font-weight:700}}
.stat-item .label{{font-size:11px;color:#888}}
.holding-card{{border:1px solid #eee;border-radius:8px;padding:12px;margin-bottom:8px}}
.holding-card .top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}}
.holding-card .name{{font-size:15px;font-weight:600}}
.holding-card .pct{{font-size:14px}}
.holding-card .detail{{font-size:13px;color:#555;line-height:1.8}}
.holding-card .signals{{font-size:12px;margin:4px 0}}
.advice{{display:inline-block;background:#3498db;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px}}
.advice.warn{{background:#e67e22}}
.advice.danger{{background:#e74c3c}}
.advice.good{{background:#2ecc71}}
.sector-bar{{display:flex;gap:8px;flex-wrap:wrap}}
.sector-col{{flex:1;min-width:140px}}
.sector-item{{background:#f8f9ff;border-radius:6px;padding:8px 12px;margin-bottom:4px}}
.sector-item .sname{{font-size:13px;font-weight:600}}
.news-item{{padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:13px;line-height:1.5}}
.news-item:last-child{{border-bottom:none}}
.tag{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:11px;margin:0 2px}}
.tag-red{{background:#ffe0e0;color:#e74c3c}}
.tag-green{{background:#d4edda;color:#27ae60}}
.tag-blue{{background:#dbe9f4;color:#2980b9}}
.tag-orange{{background:#ffe8cc;color:#e67e22}}
.footer{{text-align:center;font-size:12px;color:#999;padding:16px 0}}
.fund-row{{display:flex;justify-content:space-between;padding:4px 0;font-size:13px;border-bottom:1px solid #f5f5f5}}
</style>
</head>
<body>
<div class="header">
  <h1>📊 午间复盘 | {today_str}</h1>
  <div class="sub">{now.strftime('%H:%M')} 生成 · {holder_name} · 🕵️ StockHolmes</div>
</div>
"""
    
    # 一、大盘
    html += '<div class="section"><h2>一、大盘与市场</h2><div class="index-row">'
    for name in ['上证', '深证', '创业板', '科创50']:
        d = overview.get(name, {})
        pct = _parse_float(d.get('pct', '0'))
        cls = 'pct-up' if pct >= 0 else 'pct-down'
        vol = fmt_vol(d.get('volume', 0))
        yd = yest.get(name, {})
        y_vol = fmt_vol(yd.get('amount', 0))
        html += f'<div class="index-item"><div class="name">{name}</div><div class="price">{d.get("price","?")}</div><div class="pct {cls}">{fmt_pct(pct)}</div><div class="vol">成交{vol} (昨{y_vol})</div></div>'
    html += '</div>'
    
    sh_vol = overview.get('上证', {}).get('volume', 0)
    sz_vol = overview.get('深证', {}).get('volume', 0)
    total = fmt_vol(sh_vol + sz_vol)
    html += f'<div style="text-align:right;font-size:13px;color:#666;margin-bottom:8px">两市合计: {total}</div>'
    
    up_c = stats.get('上涨家数', 0); dn_c = stats.get('下跌家数', 0)
    zt = stats.get('涨停家数', 0); dt = stats.get('跌停家数', 0)
    zp = stats.get('炸板家数', 0); zpl = stats.get('炸板率', 0)
    html += f'<div class="stat-box">'
    html += f'<div class="stat-item"><div class="num" style="color:#e74c3c">{up_c}</div><div class="label">上涨</div></div>'
    html += f'<div class="stat-item"><div class="num" style="color:#27ae60">{dn_c}</div><div class="label">下跌</div></div>'
    html += f'<div class="stat-item"><div class="num" style="color:#e74c3c">{zt}</div><div class="label">涨停</div></div>'
    html += f'<div class="stat-item"><div class="num" style="color:#27ae60">{dt}</div><div class="label">跌停</div></div>'
    html += f'<div class="stat-item"><div class="num" style="color:#e67e22">{zp}</div><div class="label">炸板({zpl}%)</div></div>'
    html += '</div></div>'
    
    # 二、市场主线
    html += '<div class="section"><h2>二、市场主线</h2><div class="sector-bar">'
    if up_sectors:
        html += '<div class="sector-col"><div style="font-size:13px;font-weight:600;margin-bottom:6px;color:#e74c3c">📈 领涨板块</div>'
        for r in up_sectors[:5]:
            n = _gv(r, '名称'); p = _parse_float(_gv(r, '涨跌幅'))
            html += f'<div class="sector-item"><div class="sname">{n}</div><div class="pct-up">{fmt_pct(p)}</div></div>'
        html += '</div>'
    if down_sectors:
        html += '<div class="sector-col"><div style="font-size:13px;font-weight:600;margin-bottom:6px;color:#27ae60">📉 领跌板块</div>'
        for r in down_sectors[:5]:
            n = _gv(r, '名称'); p = _parse_float(_gv(r, '涨跌幅'))
            html += f'<div class="sector-item"><div class="sname">{n}</div><div class="pct-down">{fmt_pct(p)}</div></div>'
        html += '</div>'
    html += '</div>'
    
    # 板块资金
    sector_fund = get_sector_fund_flow()
    if sector_fund:
        html += '<div style="margin-top:10px;font-size:13px"><b>🟢 板块资金流入TOP5:</b></div>'
        for r in sector_fund[:5]:
            n = _gv(r, '名称'); net = _parse_float(_gv(r, '主力净额'))
            html += f'<div class="fund-row"><span>{n}</span><span style="color:#e74c3c">{fmt_vol(net)}</span></div>'
    html += '</div>'
    
    # 三、持仓复盘
    sec_label = "三"
    html += f'<div class="section"><h2>{sec_label}、{holder_name}持仓复盘</h2>'
    if holdings:
        results = analyze_holdings(holdings, overview, dragon)
        up_c2 = sum(1 for r in results if r['pct'] > 0)
        dn_c2 = sum(1 for r in results if r['pct'] < 0)
        avg_pnl = sum(r['pnl_pct'] for r in results if r['cost'] > 0) / len([r for r in results if r['cost'] > 0]) if any(r['cost'] > 0 for r in results) else 0
        html += f'<div style="font-size:13px;margin-bottom:10px;color:#666">持仓{len(results)}只 | 涨{up_c2}跌{dn_c2} | 平均浮盈{avg_pnl:+.1f}%</div>'
        
        for r in results:
            pct_cls = 'pct-up' if r['pct'] >= 0 else 'pct-down'
            pnl_cls = 'pct-up' if r['pnl_pct'] >= 0 else 'pct-down'
            advice_cls = 'good' if '持有' in r['advice'] else ('danger' if '止损' in r['advice'] else 'warn')
            html += f'''
<div class="holding-card">
  <div class="top">
    <span class="name">{r['name']}({r['code']})</span>
    <span class="pct {pct_cls}">{fmt_pct(r['pct'])}</span>
  </div>
  <div class="detail">
    现价: {r['price']:.2f} | 成本: {r['cost']:.2f} | 浮盈: <span class="{pnl_cls}">{r['pnl_pct']:+.1f}%</span>
    <br>换手: {r['turnover']:.1f}% | {r['beat_market']}大盘
  </div>'''
            if r['signals']:
                html += f'<div class="signals">{" | ".join(r["signals"])}</div>'
            html += f'<div style="margin-top:4px"><span class="advice {advice_cls}">💡 {r["advice"]}</span>'
            if r['reasons']:
                html += f'<span style="font-size:12px;color:#888;margin-left:6px">{" ".join(r["reasons"])}</span>'
            html += '</div></div>'
    else:
        html += '<p style="color:#999">暂无持仓数据</p>'
    html += '</div>'
    
    # 四、自选股（天天）
    if user_key == "boss":
        sec_label = "四" if user_key == "boss" else ""
        html += '<div class="section"><h2>四、自选股跟踪</h2>'
        wl = load_watchlist(user_key)
        if wl:
            wl_codes = [f"sz{w['code']}" if not w['code'].startswith('6') else f"sh{w['code']}" for w in wl]
            wl_quotes = get_stock_realtime(wl_codes)
            wl_analyzed = analyze_watchlist(wl, wl_quotes)
            
            for w in wl_analyzed[:10]:
                pct_cls = 'pct-up' if w['pct'] >= 0 else 'pct-down'
                html += f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:14px">'
                html += f'<span>{w["name"]}({w["code"]})</span>'
                html += f'<span class="{pct_cls}">{fmt_pct(w["pct"])} 换手{w["turnover"]:.1f}%</span>'
                html += '</div>'
                if w['signals']:
                    html += f'<div style="font-size:12px;color:#666;margin:-2px 0 4px;padding-left:0">{" ".join(w["signals"])}</div>'
        else:
            html += '<p style="color:#999">暂无自选股数据</p>'
        html += '</div>'
    
    # 五、龙虎榜
    html += '<div class="section"><h2>五、龙虎榜 & 资金流向</h2>'
    inst_buy = [d for d in dragon if d.get('buy_inst', 0) > 0][:3] if dragon else []
    if inst_buy:
        html += '<div style="font-size:14px;font-weight:600;margin-bottom:6px">🏦 机构买入重点</div>'
        for d in inst_buy:
            html += f'<div class="news-item">{d["name"]}({d["code"]}) | 买入{d["buy_inst"]:.1f}万</div>'
    if dragon:
        html += '<div style="font-size:14px;font-weight:600;margin:8px 0 4px">📋 龙虎榜TOP5</div>'
        for d in dragon[:5]:
            pct_cls = 'pct-up' if d['pct'] >= 0 else 'pct-down'
            html += f'<div class="news-item">{d["name"]}({d["code"]}) <span class="{pct_cls}">{fmt_pct(d["pct"])}</span><br><span style="color:#666;font-size:12px">{d.get("reason","")[:30]}</span></div>'
    else:
        html += '<p style="color:#999">龙虎榜数据暂不可用</p>'
    
    inflow = get_cached_capital_inflow()
    if inflow:
        html += '<div style="font-size:14px;font-weight:600;margin:8px 0 4px">🟢 主力净流入TOP5</div>'
        for r in inflow[:5]:
            pct_cls = 'pct-up' if r['pct'] >= 0 else 'pct-down'
            html += f'<div class="fund-row"><span>{r["name"]}({r["code"]})</span><span><span class="{pct_cls}">{fmt_pct(r["pct"])}</span> +{r["main_net"]:.2f}亿</span></div>'
    html += '</div>'
    
    # 六、午间简报
    html += '<div class="section"><h2>六、午间简报</h2>'
    news = search_news_query("今日盘中 热点 板块", 5)
    if news:
        for n in news:
            if isinstance(n, dict):
                title = n.get('title', n.get('name', str(n)))[:60]
                html += f'<div class="news-item">📰 {title}</div>'
    elif up_sectors:
        for r in up_sectors[:3]:
            n = _gv(r, '名称'); p = _parse_float(_gv(r, '涨跌幅'))
            html += f'<div class="news-item">📰 板块活跃: <b>{n}</b> {fmt_pct(p)}</div>'
    else:
        html += '<p style="color:#999">暂无可用的盘中消息</p>'
    html += '</div>'
    
    # 七、下午提示
    html += '<div class="section"><h2>七、下午交易提示</h2>'
    sh_pct = _parse_float(overview.get('上证', {}).get('pct', '0'))
    tips = []
    if sh_pct < -1:
        tips.append(('⚠️', '#e74c3c', '大盘跌幅较大，控制仓位'))
    elif sh_pct > 1:
        tips.append(('✅', '#2ecc71', '大盘强势，持股为主'))
    else:
        tips.append(('👀', '#3498db', '窄幅震荡，关注方向选择'))
    if up_c > dn_c and dn_c > 0:
        ratio = up_c / dn_c
        if ratio > 1.5:
            tips.append(('🔥', '#e67e22', '涨跌比偏暖'))
    if zt > 100:
        tips.append(('🔥', '#e67e22', f'短线情绪活跃(涨停{zt}只)'))
    if dt > 20:
        tips.append(('⚠️', '#e74c3c', f'跌停{dt}只，注意风险'))
    
    for icon, color, text in tips:
        html += f'<div style="padding:4px 0;font-size:14px"><span style="color:{color}">{icon} {text}</span></div>'
    html += '</div>'
    
    html += '<div class="footer">⚠️ 仅供参考，不构成投资建议 | 🕵️ StockHolmes · 午间复盘报告</div>'
    html += '</body></html>'
    return html


# ========== 主函数 ==========

def main():
    import argparse
    parser = argparse.ArgumentParser(description='午间复盘 & 财经简报 v2')
    parser.add_argument('--user', choices=['boss', 'boyfriend'], default='boss')
    args = parser.parse_args()
    
    user_key = args.user
    start = time.time()
    print(f"\n{'='*50}")
    print(f"📊 午间复盘 & 财经简报 | {datetime.now().strftime('%Y-%m-%d %H:%M')} 用户={user_key}")
    print('='*50)
    
    print("\n🔄 收集数据中...")
    text = gen_text_report(user_key)
    
    output_dir = f'{BASE}/output/{user_key}'
    os.makedirs(output_dir, exist_ok=True)
    
    # 文本摘要
    summary_path = f'{output_dir}/午间复盘_summary_latest.txt'
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"✅ 文本摘要: {summary_path}")
    
    # HTML报告
    print("🔄 生成HTML报告...")
    html = gen_html_report(user_key)
    date_str = datetime.now().strftime('%Y%m%d')
    html_path = f'{output_dir}/午间复盘_{date_str}.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ HTML报告: {html_path}")
    
    elapsed = time.time() - start
    print(f"\n⏱️ 耗时: {elapsed:.1f}s")
    print(f"\n{'='*50}")
    print(text[:200])
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
