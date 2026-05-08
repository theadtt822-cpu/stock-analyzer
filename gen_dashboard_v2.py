#!/usr/bin/env python3
"""生成增强版持仓仪表盘 HTML（含MA数值标注 + 术语解释 + 新增持仓）"""
import json
import os
import re
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
BOSS_DIR = os.path.join(OUTPUT_DIR, 'boss')

def get_timestamp():
    """生成文件时间戳: YYYYMMDD_HHMM"""
    return datetime.now().strftime("%Y%m%d_%H%M")

def get_date_str():
    """生成日期字符串: YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")

# 术语解释
GLOSSARY = """
<h2 class="st" id="glossary">📖 指标与术语解释（新手友好版）</h2>
<div class="tw" style="margin-bottom:28px">
<table>
<thead><tr><th style="text-align:left">术语</th><th style="text-align:left">白话解释</th><th style="text-align:left">怎么看</th></tr></thead>
<tbody>
<tr><td><b>MA5</b>（5日均线）</td><td>最近5个交易日收盘价的平均值，代表<strong>短期趋势</strong></td><td>股价在MA5上方=短期强势；下方=短期弱势</td></tr>
<tr><td><b>MA10</b>（10日均线）</td><td>最近10个交易日收盘价的平均值，代表<strong>短中期趋势</strong></td><td>股价在MA10上方=中期向好；跌破MA10=中期转弱</td></tr>
<tr><td><b>MA20</b>（20日均线）</td><td>最近20个交易日（约一个月）收盘价的平均，代表<strong>月度趋势</strong></td><td>股价站稳MA20=月度趋势向上</td></tr>
<tr><td><b>MA60</b>（60日均线）</td><td>最近60个交易日（约三个月）的平均，代表<strong>季度/中长期趋势</strong></td><td>股价在MA60上方=中长期牛市格局</td></tr>
<tr><td><b>多头排列</b></td><td>MA5 > MA10 > MA20 > MA60，均线从上到下排列。意思是<strong>短期到长期都在涨</strong></td><td>✅ 好信号，趋势向上</td></tr>
<tr><td><b>空头排列</b></td><td>MA5 < MA10 < MA20 < MA60，均线从下到上排列。意思是<strong>短期到长期都在跌</strong></td><td>❌ 危险信号，趋势向下</td></tr>
<tr><td><b>MACD金叉</b></td><td>DIF线上穿DEA线，代表<strong>上涨动能开始增强</strong></td><td>✅ 看涨信号</td></tr>
<tr><td><b>MACD死叉</b></td><td>DIF线下穿DEA线，代表<strong>下跌动能开始增强</strong></td><td>❌ 看跌信号</td></tr>
<tr><td><b>RSI</b>（相对强弱指数）</td><td>衡量股票涨跌力度的指标，范围0-100。<strong>越高说明涨得越猛，越低说明跌得越狠</strong></td><td>RSI>70=超买（可能回调）；RSI<30=超卖（可能反弹）；30-70=正常区间</td></tr>
<tr><td><b>乖离率(BIAS)</b></td><td>股价偏离均线的百分比。<strong>偏离越大，越可能回归均线</strong></td><td>乖离率>5%=离均线太远，有回落风险；< -5%=可能超跌反弹</td></tr>
<tr><td><b>量比/量能</b></td><td>今天的成交量和过去5天平均成交量的比值。<strong>反映资金活跃度</strong></td><td>量比>1.5=放量（资金活跃）；<0.5=缩量（没人交易）</td></tr>
<tr><td><b>目标价</b></td><td>AI 分析后认为未来可能到达的<strong>合理价格</strong>，基于技术面和趋势判断推算</td><td>达到目标价可以考虑止盈，但不保证一定到</td></tr>
<tr><td><b>止损价</b></td><td>如果跌破这个价格，说明趋势可能坏了，<strong>应该考虑卖出控制亏损</strong></td><td>设好止损=给自己的投资上保险</td></tr>
<tr><td><b>StockHolmes评分</b></td><td>原版规则算法给出的技术面评分（0-100分）。分数越高=技术面越好</td><td>>60分偏看多；40-60分中性；<40分偏看空</td></tr>
<tr><td><b>AI评分</b></td><td>阿里云百炼AI结合技术面+新闻资讯+市场情绪给出的综合评分（0-100分）</td><td>>70分偏看多；50-70分中性；<50分偏看空</td></tr>
</tbody>
</table>
</div>

<h3 style="color:#6b7b8d;font-size:13px;margin-bottom:12px">💡 操作建议对照表</h3>
<div class="tw" style="margin-bottom:28px">
<table>
<thead><tr><th>建议</th><th>含义</th><th>你应该怎么做</th></tr></thead>
<tbody>
<tr><td><span class="tag tg">买入</span></td><td>技术面+基本面都好，趋势向上，有上涨空间</td><td>可以考虑加仓或建仓</td></tr>
<tr><td><span class="tag tg">持有</span></td><td>趋势还在向上，但价格已经偏高或RSI接近超买</td><td>继续拿着，设好止盈，不急加仓</td></tr>
<tr><td><span class="tag ty">观望</span></td><td>信号不明确，或存在风险因素，需要等待更明确的信号</td><td>先别动，等趋势明朗再说</td></tr>
<tr><td><span class="tag tr">卖出</span></td><td>趋势明显转坏，风险大于机会</td><td>考虑减仓或清仓</td></tr>
</tbody>
</table>
</div>
"""

def score_tag(score, color_class=None):
    if score is None:
        return '<span class="tag tp">--</span>'
    if score >= 70:
        return f'<span class="tag tg">{score}</span>'
    elif score >= 50:
        return f'<span class="tag ty">{score}</span>'
    else:
        return f'<span class="tag tr">{score}</span>'

def advice_tag(advice):
    if not advice or advice == '待补充':
        return '<span class="tag tp">--</span>'
    m = {'买入': 'tg', '持有': 'ty', '观望': 'ty', '卖出': 'tr'}
    cls = m.get(advice, 'ty')
    return f'<span class="tag {cls}">{advice}</span>'

def ma_display(ma_val, label):
    """显示MA数值，带具体数字"""
    if ma_val is None:
        return f'<div class="i"><div class="l">{label}</div><div class="value" style="color:#6b7b8d">待补充</div></div>'
    return f'<div class="i"><div class="l">{label}</div><div class="value">{ma_val}</div></div>'

def consistency(sh_advice, ai_advice):
    if not sh_advice or not ai_advice or sh_advice == '待补充':
        return '<span class="tag tb">--</span>'
    sh_a = sh_advice.replace(' ', '')
    ai_a = ai_advice.replace(' ', '')
    if sh_a == ai_a == '买入':
        return '<span class="tag tg">✅ 一致看多</span>'
    elif sh_a == ai_a:
        return '<span class="tag ty">⚪ 都观望</span>'
    elif (sh_a in ('买入','持有') and ai_a in ('买入','持有')) or \
         (sh_a in ('观望','持有') and ai_a in ('观望','持有')):
        return '<span class="tag tb">🔵 接近</span>'
    else:
        return '<span class="tag tr">⚠️ 分歧</span>'

def gen_card(r, idx):
    tech = r.get('technical', {})
    sh = r.get('stockholmes', {})
    ai = r.get('ai_analysis', {})
    news = r.get('news', {})
    
    sh_advice = sh.get('buy_signal', '') if sh else ''
    sh_score = r.get('rule_score') or sh.get('signal_score')
    ai_advice = ai.get('operation_advice', '') if ai else ''
    ai_score = ai.get('sentiment_score')
    
    # MA行 - 显示具体数值
    ma_html = ''
    ma_html += ma_display(tech.get('ma5'), 'MA5')
    ma_html += ma_display(tech.get('ma10'), 'MA10')
    ma_html += ma_display(tech.get('ma20'), 'MA20')
    ma_html += ma_display(tech.get('ma60'), 'MA60')
    
    # 趋势等
    trend = tech.get('trend', '待补充') or '待补充'
    vol_status = '量能正常'
    macd_status = tech.get('macd_signal', '待补充') or '待补充'
    rsi_val = tech.get('rsi')
    if rsi_val is not None:
        if rsi_val > 70:
            rsi_status = '超买'
        elif rsi_val > 50:
            rsi_status = '强势'
        elif rsi_val > 30:
            rsi_status = '中性'
        else:
            rsi_status = '弱势'
    else:
        rsi_status = '待补充'
    
    # 新闻/资讯区域 - 失败时降级显示行情概况
    news_html = ''
    news_title = news.get('title', '') if news else ''
    news_summary = news.get('summary', '') if news else ''
    if news_title and news_title != '查询失败':
        summary_clean = re.sub(r'\s+', ' ', news_summary).strip()[:150]
        news_html = f'<div class="news"><div class="nt">📰 {news_title}</div><div class="ns">{summary_clean}...</div></div>'
    else:
        # 降级：显示行情概况
        chg_val = r.get('day_change', 0)
        chg_cls = 'r' if chg_val >= 0 else 'g'
        chg_sign = '+' if chg_val > 0 else ''
        ma5_v = tech.get('ma5')
        ma10_v = tech.get('ma10')
        ma20_v = tech.get('ma20')
        rsi_v = tech.get('rsi')
        macd_v = tech.get('macd_signal', '待补充') or '待补充'
        trend_v = tech.get('trend', '待补充') or '待补充'
        ma_status = ''
        if ma5_v is not None and ma10_v is not None and ma20_v is not None:
            arr = '多头排列' if ma5_v > ma10_v > ma20_v else ('空头排列' if ma5_v < ma10_v < ma20_v else '交织')
            ma_status = f'均线{arr}'
        parts = [trend_v, macd_v]
        if ma_status:
            parts.append(ma_status)
        if rsi_v is not None:
            if rsi_v > 70: parts.append('RSI超买')
            elif rsi_v < 30: parts.append('RSI超卖')
            else: parts.append(f'RSI {rsi_v:.0f}')
        fallback_text = ' | '.join(parts) if parts else '暂无数据'
        news_html = f'<div class="news" style="border-left-color:#6b7b8d"><div class="nt" style="color:#6b7b8d">📊 行情概况</div><div class="ns" style="color:#8b949e">当日{chg_sign}{chg_val}% · {fallback_text}</div></div>'
    
    # 双版本
    sh_reasons = sh.get('signal_reasons', []) if sh else []
    sh_risks = sh.get('risk_factors', []) if sh else []
    sh_detail = '<br>'.join(sh_reasons[:3]) if sh_reasons else ''
    sh_trend_detail = sh.get('ma_alignment', '') if sh else ''
    bias = tech.get('bias5')
    bias_str = f'乖离:{bias}%' if bias is not None else '乖离:待补充'
    vol_detail = tech.get('vol_ratio')
    vol_str = f'量比:{vol_detail}' if vol_detail is not None else ''
    
    sh_box = f'''<div class="box" style="border-left-color:#00d4ff">
<div class="bl" style="color:#00d4ff">📐 StockHolmes规则 ({score_tag(sh_score)})</div>
<div class="bd"><b>{sh_advice or '待补充'}</b><br>{sh_trend_detail}<br>{bias_str} {vol_str}<br>{sh_detail}</div></div>'''
    
    ai_summary = ai.get('analysis_summary', '') if ai else ''
    target = ai.get('target_price', '') if ai else ''
    stop = ai.get('stop_loss', '') if ai else ''
    confidence = ai.get('confidence_level', '') if ai else ''
    ai_box = f'''<div class="box" style="border-left-color:#bb86fc">
<div class="bl" style="color:#bb86fc">🤖 AI分析 ({score_tag(ai_score)})</div>
<div class="bd"><b>{ai_advice or '待补充'}</b> · 信心:{confidence or '中'}<br>{ai_summary}<br>目标:{target or '--'} 止损:{stop or '--'}</div></div>'''
    
    pnl_val = r.get('pnl', 0)
    pnl_pct = r.get('pnl_pct', 0)
    pnl_cls = 'r' if pnl_val >= 0 else 'g'
    day_change = r.get('day_change', 0)
    day_cls = 'r' if day_change >= 0 else 'g'
    day_str = f'+{day_change}%' if day_change > 0 else f'{day_change}%'
    
    note = tech.get('price_note', '')
    note_html = f'<div style="color:#faad14;font-size:9px;margin-top:4px">{note}</div>' if note else ''
    
    sector = r.get('sector', '--')
    return f'''<div class="acard">
<div class="top"><span class="name">{r['name']} <span style="color:#6b7b8d;font-size:11px">{r['code']} {sector}</span></span>
<span style="font-size:12px;font-weight:600">{consistency(sh_advice, ai_advice)}</span></div>
<div class="price-row">
<div class="price-box"><div class="pl">成本价</div><div class="value">{r['cost']:.2f}</div></div>
<div class="price-box"><div class="pl">现价</div><div class="value {pnl_cls}">{r['current']:.2f}</div></div>
<div class="price-box"><div class="pl">当日涨跌</div><div class="value {day_cls}">{day_str}</div></div>
<div class="price-box"><div class="pl">持仓盈亏</div><div class="value {pnl_cls}">{pnl_val:+,.0f} ({pnl_pct:+.1f}%)</div></div>
</div>
<div class="m">{ma_html}
<div class="i"><div class="l">趋势</div><div class="value">{trend}</div></div>
<div class="i"><div class="l">量</div><div class="value">{vol_status}</div></div>
<div class="i"><div class="l">MACD</div><div class="value">{macd_status}</div></div>
<div class="i"><div class="l">RSI</div><div class="value">{rsi_status}</div></div>
</div>
{note_html}
{news_html}
<div class="dual">{sh_box}{ai_box}</div>
</div>'''

def gen_table_row(r, idx):
    tech = r.get('technical', {})
    sh = r.get('stockholmes', {})
    ai = r.get('ai_analysis', {})
    
    sh_advice = sh.get('buy_signal', '') if sh else ''
    sh_score = r.get('rule_score') or sh.get('signal_score')
    ai_advice = ai.get('operation_advice', '') if ai else ''
    ai_score = ai.get('sentiment_score')
    
    pnl_val = r.get('pnl', 0)
    pnl_pct = r.get('pnl_pct', 0)
    pnl_cls = 'r' if pnl_val >= 0 else 'g'
    day_change = r.get('day_change', 0)
    day_cls = 'r' if day_change >= 0 else 'g'
    day_str = f'+{day_change}%' if day_change > 0 else f'{day_change}%'
    
    target = ai.get('target_price', '--') if ai else '--'
    stop = ai.get('stop_loss', '--') if ai else '--'
    
    # MA5/MA10数值加入表格
    ma5 = tech.get('ma5', '--') if tech else '--'
    ma10 = tech.get('ma10', '--') if tech else '--'
    ma5_str = str(ma5) if ma5 is not None else '--'
    ma10_str = str(ma10) if ma10 is not None else '--'
    
    sector = r.get('sector', '--')
    return f'''<tr><td>{idx}</td><td class="sn">{r['name']}</td><td>{sector}</td>
<td>{r['cost']:.2f}</td><td>{r['current']:.2f}</td>
<td class="{day_cls}">{day_str}</td>
<td class="{pnl_cls}">{pnl_val:+,.0f}</td><td class="{pnl_cls}">{pnl_pct:+.1f}%</td>
<td>{score_tag(sh_score)}</td>
<td><span style="font-size:9px;color:#6b7b8d">MA5:{ma5_str}<br>MA10:{ma10_str}</span><br>{advice_tag(sh_advice)}</td>
<td>{advice_tag(ai_advice)}</td>
<td>{consistency(sh_advice, ai_advice)}</td>
<td>{target}</td><td>{stop}</td></tr>'''

def generate(data, report_time=None):
    results = sorted(data['results'], key=lambda x: x.get('pnl_pct', 0) or 0, reverse=True)
    total_cost = data['total_cost']
    total_value = data['total_value']
    total_pnl = data['total_pnl']
    total_pnl_pct = data['total_pnl_pct']
    n = len(results)
    
    win = sum(1 for r in results if r.get('pnl', 0) >= 0)
    lose = n - win
    win_rate = round(win / n * 100) if n > 0 else 0
    
    sh_buy = sum(1 for r in results if r.get('stockholmes', {}).get('buy_signal') == '买入')
    ai_buy = sum(1 for r in results if r.get('ai_analysis', {}).get('operation_advice') == '买入')
    
    table_rows = '\n'.join(gen_table_row(r, i+1) for i, r in enumerate(results))
    cards = '\n'.join(gen_card(r, i) for i, r in enumerate(results))
    
    pnl_cls = 'r' if total_pnl >= 0 else 'g'
    pnl_sign = '+' if total_pnl >= 0 else ''
    
    date_str = get_date_str()
    time_display = report_time or datetime.now().strftime("%Y-%m-%d %H:%M")
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StockHolmes 持仓仪表盘 - {date_str}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#0a0e17;color:#e0e6ed;font-family:-apple-system,'Microsoft YaHei',sans-serif;padding:20px}}.container{{max-width:1500px;margin:0 auto}}.header{{text-align:center;padding:20px 0 30px;border-bottom:1px solid #1e2a3a;margin-bottom:30px}}.header h1{{font-size:28px;color:#00d4ff;margin-bottom:8px}}.header .time{{color:#6b7b8d;font-size:13px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:28px}}.card{{background:linear-gradient(135deg,#111827,#1a2332);border:1px solid #1e2a3a;border-radius:12px;padding:18px;text-align:center}}.card .label{{color:#6b7b8d;font-size:12px;margin-bottom:6px}}.card .value{{font-size:22px;font-weight:700}}.r{{color:#ff4d4f}}.g{{color:#52c41a}}.b{{color:#00d4ff}}.y{{color:#faad14}}.card .sub{{color:#6b7b8d;font-size:11px;margin-top:3px}}.st{{font-size:16px;color:#00d4ff;margin:28px 0 14px;padding-left:10px;border-left:3px solid #00d4ff}}.tw{{overflow-x:auto;margin-bottom:28px;border-radius:12px;border:1px solid #1e2a3a}}table{{width:100%;border-collapse:collapse;font-size:11px}}thead{{background:#111827}}th{{padding:9px 5px;text-align:center;color:#6b7b8d;font-weight:500;border-bottom:2px solid #1e2a3a;white-space:nowrap}}td{{padding:7px 5px;text-align:center;border-bottom:1px solid #1e2a3a;white-space:nowrap}}tr:hover td{{background:#1a2332}}.sn{{color:#00d4ff;font-weight:600}}.tag{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:600}}.tg{{background:#1a3a2a;color:#52c41a}}.ty{{background:#3a2a1a;color:#faad14}}.tr{{background:#3a1a1a;color:#ff4d4f}}.tp{{background:#2a1a3a;color:#bb86fc}}.tb{{background:#1a2a3a;color:#00d4ff}}.ac{{display:grid;grid-template-columns:repeat(auto-fill,minmax(500px,1fr));gap:14px;margin-bottom:28px}}.acard{{background:linear-gradient(135deg,#111827,#1a2332);border:1px solid #1e2a3a;border-radius:12px;padding:16px}}.acard .top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}.acard .top .name{{font-size:14px;font-weight:700;color:#00d4ff}}.acard .price-row{{display:flex;gap:12px;margin-bottom:10px;flex-wrap:wrap}}.acard .price-box{{background:#0a0e17;border-radius:6px;padding:6px 10px;flex:1;min-width:80px;text-align:center}}.acard .price-box .pl{{font-size:9px;color:#6b7b8d}}.acard .price-box .pv{{font-size:13px;font-weight:700}}.acard .m{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:5px;margin-bottom:10px}}.acard .m .i{{text-align:center}}.acard .m .i .l{{font-size:9px;color:#6b7b8d}}.acard .m .i .v{{font-size:12px;font-weight:600}}.acard .news{{background:#0d1117;border-radius:5px;padding:7px 9px;margin-bottom:10px;border-left:2px solid #30363d}}.acard .news .nt{{font-size:10px;color:#58a6ff;margin-bottom:2px;font-weight:600}}.acard .news .ns{{font-size:9px;color:#8b949e;line-height:1.4}}.dual{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}}.dual .box{{background:#0a0e17;border-radius:6px;padding:8px 10px;border-left:3px solid}}.dual .box .bl{{font-size:9px;font-weight:700;margin-bottom:3px}}.dual .box .bd{{font-size:10px;color:#c0c8d4;line-height:1.4}}.risk{{background:#1a1a0a;border:1px solid #3a3a1a;border-radius:12px;padding:18px;margin-bottom:28px}}.ri{{padding:6px 0;border-bottom:1px solid #2a2a1a;font-size:12px}}.ri:last-child{{border:none}}.src{{background:#0a0e17;border:1px solid #1e2a3a;border-radius:12px;padding:18px;margin-bottom:28px}}.src h3{{color:#00d4ff;margin-bottom:10px}}.si{{padding:4px 0;font-size:11px;color:#6b7b8d}}.si span{{color:#c0c8d4}}.dc{{text-align:center;color:#3a4a5a;font-size:10px;padding:18px 0;border-top:1px solid #1e2a3a}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>🕵️ StockHolmes 持仓仪表盘</h1>
<div class="time">{time_display} | 增强版：MA数值标注 + 术语解释 + {n}只持仓 | <a href="#glossary" style="color:#faad14">📖 查看术语解释</a></div>
</div>
<div class="cards">
<div class="card"><div class="label">总投入</div><div class="value b">¥{total_cost:,.2f}</div><div class="sub">{n}只</div></div>
<div class="card"><div class="label">总市值</div><div class="value b">¥{total_value:,.2f}</div><div class="sub">按用户现价</div></div>
<div class="card"><div class="label">总盈亏</div><div class="value {pnl_cls}">¥{pnl_sign}{total_pnl:,.2f}</div><div class="sub">{pnl_sign}{total_pnl_pct:.1f}%</div></div>
<div class="card"><div class="label">盈利/亏损</div><div class="value g">{win} / {lose}</div><div class="sub">胜率{win_rate}%</div></div>
<div class="card"><div class="label">StockHolmes买入</div><div class="value y">{sh_buy}只</div><div class="sub">原版规则</div></div>
<div class="card"><div class="label">AI买入</div><div class="value y">{ai_buy}只</div><div class="sub">百炼AI</div></div>
</div>

<h2 class="st">📊 持仓总表（含MA5/MA10数值 + 双版本建议）</h2>
<div class="tw"><table>
<thead><tr><th>排名</th><th>股票</th><th>板块</th><th>成本</th><th>现价</th><th>当日</th><th>盈亏</th><th>收益率</th><th>均线/StockHolmes</th><th>AI建议</th><th>一致?</th><th>AI目标</th><th>AI止损</th></tr></thead>
<tbody>{table_rows}</tbody></table></div>

<h2 class="st">📋 个股详情（MA数值已标注，含术语解释）</h2>
<div class="ac">{cards}</div>

{GLOSSARY}

<h2 class="st">📚 数据来源与工具</h2>
<div class="src"><h3>工具链</h3>
<div class="si">1. <span>持仓数据</span> — 用户输入（成本/现价/数量）</div>
<div class="si">2. <span>日K线</span> — <b>Skill: tushare-finance</b>（Tushare Pro）+ 腾讯 API 备选</div>
<div class="si">3. <span>实时行情</span> — 东方财富 push2 API，获取当日涨跌幅</div>
<div class="si">4. <span>StockHolmes规则</span> — <b>Skill: stock-daily-analysis</b>（原版分析器），MA/MACD/RSI/乖离率/量能综合分析</div>
<div class="si">5. <span>最新资讯</span> — <b>Skill: mx-search</b>（东方财富妙想），新闻/公告/研报</div>
<div class="si">6. <span>AI分析</span> — <b>Skill: stock-daily-analysis</b> → 阿里云百炼 qwen3.5-plus</div>
<div class="si">7. <span>双版本对比</span> — 原版规则偏技术面信号，AI偏综合研判，一致时信号更强</div>
</div>

<div class="dc">
⚠️ 免责声明：本报告仅供学习研究，不构成投资建议。股市有风险，投资需谨慎。<br>
StockHolmes 🕵️ | {time_display}
</div>
</div></body></html>'''
    return html

def generate_for_user(user, data_file, out_dir):
    """为指定用户生成持仓仪表盘"""
    if not os.path.exists(data_file):
        print(f"⚠️ 数据文件不存在: {data_file}")
        return
    
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    html = generate(data)
    os.makedirs(out_dir, exist_ok=True)
    ts = get_timestamp()
    out_path = os.path.join(out_dir, f'持仓仪表盘_{ts}.html')
    with open(out_path, 'w') as f:
        f.write(html)
    latest_path = os.path.join(out_dir, '持仓仪表盘_最新.html')
    with open(latest_path, 'w') as f:
        f.write(html)
    print(f"✅ {user} 仪表盘已生成")
    print(f"   时间戳版本: {out_path}")
    print(f"   最新版本: {latest_path}")
    print(f"   文件大小: {len(html):,} bytes")
    print(f"   股票数量: {len(data['results'])}只")

if __name__ == '__main__':
    import sys
    # 支持命令行参数: python gen_dashboard_v2.py [boss|boyfriend|all]
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'
    
    BOYFRIEND_DIR = os.path.join(OUTPUT_DIR, 'boyfriend')
    
    if target in ('all', 'boss'):
        generate_for_user('老板(邓天天)', os.path.join(BOSS_DIR, 'portfolio_dashboard.json'), BOSS_DIR)
    
    if target in ('all', 'boyfriend'):
        generate_for_user('波波', os.path.join(OUTPUT_DIR, 'portfolio_data.json'), BOYFRIEND_DIR)
