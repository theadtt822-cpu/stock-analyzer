#!/usr/bin/env python3
"""生成自选股合并报告（整合多只股票到单个HTML）"""
import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
BOSS_DIR = os.path.join(OUTPUT_DIR, 'boss')
ZIXUAN_DIR = os.path.join(BOSS_DIR, 'watchlist')

os.makedirs(ZIXUAN_DIR, exist_ok=True)

# 自选股列表
ZIXUAN_STOCKS = [
    {'code': '002192', 'name': '融捷股份', 'market': 'sz'},
    {'code': '600105', 'name': '永鼎股份', 'market': 'sh'},
    {'code': '002497', 'name': '雅化集团', 'market': 'sz'},
    {'code': '600246', 'name': '万通发展', 'market': 'sh'},
]

def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M")

def get_date_str():
    return datetime.now().strftime("%Y-%m-%d")

def parse_stock_report(filepath):
    """解析个股分析报告HTML，提取关键数据"""
    if not os.path.isfile(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
    except:
        return None
    
    data = {}
    
    # 提取股票名称和价格
    header = soup.find('div', class_='header')
    if header:
        h1 = header.find('h1')
        if h1:
            data['name'] = h1.get_text(strip=True)
        
        price_el = header.find('span', class_='price')
        if price_el:
            data['price'] = price_el.get_text(strip=True)
        
        chg_el = header.find('span', class_='chg')
        if chg_el:
            data['change'] = chg_el.get_text(strip=True)
    
    # 提取评分
    score_circles = soup.find_all('div', class_='score-circle')
    if len(score_circles) >= 2:
        # StockHolmes评分
        holmes_num = score_circles[0].find('span', class_='score-num')
        holmes_label = score_circles[0].find('span', class_='score-label')
        if holmes_num:
            data['holmes_score'] = holmes_num.get_text(strip=True)
        if holmes_label:
            data['holmes_signal'] = holmes_label.get_text(strip=True)
        
        # AI评分
        ai_num = score_circles[1].find('span', class_='score-num')
        ai_label = score_circles[1].find('span', class_='score-label')
        if ai_num:
            data['ai_score'] = ai_num.get_text(strip=True)
        if ai_label:
            data['ai_signal'] = ai_label.get_text(strip=True)
    
    # 提取指标
    ind_rows = soup.find_all('div', class_='indicator-row')
    indicators = []
    for row in ind_rows:
        ind_name = row.find('div', class_='ind-name')
        ind_value = row.find('div', class_='ind-value')
        ind_status = row.find('div', class_='ind-status')
        ind_desc = row.find('div', class_='ind-desc')
        if ind_name and ind_value:
            indicators.append({
                'name': ind_name.get_text(strip=True),
                'value': ind_value.get_text(strip=True),
                'status': ind_status.get_text(strip=True) if ind_status else '',
                'desc': ind_desc.get_text(strip=True) if ind_desc else '',
            })
    data['indicators'] = indicators
    
    # 提取操作建议
    advice_grid = soup.find('div', class_='advice-grid')
    if advice_grid:
        advice_boxes = advice_grid.find_all('div', class_='advice-box')
        if len(advice_boxes) >= 2:
            data['rule_advice'] = advice_boxes[0].get_text(strip=True)
            data['ai_advice'] = advice_boxes[1].get_text(strip=True)
    
    # 提取策略关键信息
    strategy = soup.find('div', class_='strategy-section')
    if strategy:
        data['strategy_html'] = str(strategy)
    
    return data

def generate_zixuan_html(stocks_data, date_str):
    """生成自选股合并HTML报告"""
    
    # 按评分排序（StockHolmes评分降序）
    sorted_stocks = sorted(stocks_data, key=lambda x: int(x.get('holmes_score', 0) or 0), reverse=True)
    
    timestamp = get_timestamp()
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>自选股分析 - {date_str}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Microsoft YaHei', 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; padding: 16px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.card {{ background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 16px; padding: 20px; }}
h2 {{ font-size: 16px; color: #333; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px; margin-bottom: 16px; }}

.header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; border-radius: 12px; padding: 24px; margin-bottom: 16px; }}
.header h1 {{ font-size: 22px; margin-bottom: 4px; }}
.header .date {{ font-size: 13px; opacity: 0.7; }}
.header .subtitle {{ font-size: 14px; opacity: 0.9; margin-top: 8px; }}

/* 排名卡片 */
.ranking {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin-top: 16px; }}
.rank-card {{ background: rgba(255,255,255,0.1); border-radius: 10px; padding: 14px; border-left: 4px solid; }}
.rank-card.gold {{ border-color: #FFD700; }}
.rank-card.silver {{ border-color: #C0C0C0; }}
.rank-card.bronze {{ border-color: #CD7F32; }}
.rank-card.normal {{ border-color: #4a90d9; }}
.rank-num {{ font-size: 28px; font-weight: bold; opacity: 0.8; }}
.rank-name {{ font-size: 18px; font-weight: bold; margin: 4px 0; }}
.rank-price {{ font-size: 20px; font-weight: bold; }}
.rank-score {{ font-size: 14px; margin-top: 4px; }}
.rank-signal {{ font-size: 13px; opacity: 0.9; }}

/* 股票详情 */
.stock-section {{ margin-bottom: 24px; }}
.stock-header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 2px solid #f0f0f0; }}
.stock-badge {{ font-size: 24px; font-weight: bold; color: #4a90d9; min-width: 40px; }}
.stock-name {{ font-size: 20px; font-weight: bold; }}
.stock-code {{ font-size: 14px; color: #888; }}
.stock-price {{ font-size: 28px; font-weight: bold; margin-left: auto; }}
.stock-change {{ font-size: 16px; font-weight: 500; }}

/* 评分对比 */
.dual-score {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }}
.score-box {{ background: #f8f9fa; border-radius: 10px; padding: 14px; text-align: center; border: 2px solid #e8e8e8; }}
.score-box .title {{ font-size: 13px; font-weight: 600; color: #666; margin-bottom: 8px; }}
.score-circle {{ width: 80px; height: 80px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 0 auto; border: 3px solid; }}
.score-num {{ font-size: 28px; font-weight: bold; }}
.score-label {{ font-size: 12px; }}
.signal-text {{ font-size: 13px; color: #333; margin-top: 8px; font-weight: 500; }}

/* 指标表格 */
.ind-table {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; }}
.ind-table th {{ text-align: left; padding: 8px 12px; background: #f8f9fa; font-size: 13px; color: #888; font-weight: 500; border-bottom: 2px solid #e8e8e8; }}
.ind-table td {{ padding: 8px 12px; border-bottom: 1px solid #f5f5f5; font-size: 13px; }}
.ind-table .ind-name-cell {{ font-weight: 500; color: #555; width: 80px; }}
.ind-table .ind-val-cell {{ font-family: 'SF Mono', monospace; color: #333; width: 100px; }}
.ind-table .ind-status-cell {{ font-weight: 600; width: 100px; }}
.ind-table .ind-desc-cell {{ color: #666; }}

/* 建议 */
.advice-box {{ background: linear-gradient(135deg, #f0f4ff, #f8f9fa); border-radius: 10px; padding: 16px; margin-bottom: 12px; }}
.advice-box h4 {{ font-size: 14px; color: #333; margin-bottom: 8px; }}
.advice-box p {{ font-size: 13px; color: #555; line-height: 1.8; white-space: pre-line; }}

.footer {{ text-align: center; padding: 16px; color: #999; font-size: 12px; }}

@media (max-width: 768px) {{
    .ranking {{ grid-template-columns: 1fr 1fr; }}
    .dual-score {{ grid-template-columns: 1fr; }}
    .stock-header {{ flex-wrap: wrap; }}
    .stock-price {{ margin-left: 0; margin-top: 8px; }}
}}
@media (max-width: 480px) {{
    .ranking {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class="container">

<div class="header">
    <h1>📋 自选股分析报告</h1>
    <div class="date">{date_str}</div>
    <div class="subtitle">共 {len(stocks_data)} 只股票 · 按评分排序</div>
    <div class="ranking">"""

    rank_classes = ['gold', 'silver', 'bronze'] + ['normal'] * (len(sorted_stocks) - 3)
    
    for i, stock in enumerate(sorted_stocks):
        rank = i + 1
        rank_class = rank_classes[i] if i < len(rank_classes) else 'normal'
        price_color = '#DC143C' if '▲' in str(stock.get('change', '')) else ('#008000' if '▼' in str(stock.get('change', '')) else '#fff')
        
        html += f"""
        <div class="rank-card {rank_class}">
            <div class="rank-num">#{rank}</div>
            <div class="rank-name">{stock.get('name', '--')}</div>
            <div class="rank-price" style="color: {price_color}">{stock.get('price', '--')}</div>
            <div class="rank-change">{stock.get('change', '--')}</div>
            <div class="rank-score">StockHolmes: {stock.get('holmes_score', '--')}分</div>
            <div class="rank-signal">{stock.get('holmes_signal', '--')}</div>
        </div>"""
    
    html += """
    </div>
</div>"""

    # 个股详情
    for i, stock in enumerate(sorted_stocks):
        html += f"""
<div class="card stock-section">
    <div class="stock-header">
        <span class="stock-badge">#{i+1}</span>
        <span class="stock-name">{stock.get('name', '--')}</span>
        <span class="stock-code">{stock.get('market', '')}{stock.get('code', '')}</span>
        <span class="stock-price" style="color: {'#DC143C' if '▲' in str(stock.get('change', '')) else '#008000'}">{stock.get('price', '--')}</span>
        <span class="stock-change" style="color: {'#DC143C' if '▲' in str(stock.get('change', '')) else '#008000'}">{stock.get('change', '--')}</span>
    </div>
    
    <div class="dual-score">
        <div class="score-box">
            <div class="title">🕵️‍♂️ StockHolmes 规则评分</div>
            <div class="score-circle" style="border-color: {'#DC143C' if int(stock.get('holmes_score', 50) or 50) < 50 else '#008000'}">
                <span class="score-num" style="color: {'#DC143C' if int(stock.get('holmes_score', 50) or 50) < 50 else '#008000'}">{stock.get('holmes_score', '--')}</span>
                <span class="score-label" style="color: {'#DC143C' if int(stock.get('holmes_score', 50) or 50) < 50 else '#008000'}">{stock.get('holmes_signal', '--')}</span>
            </div>
        </div>
        <div class="score-box">
            <div class="title">🤖 AI 分析评分</div>
            <div class="score-circle" style="border-color: {'#DC143C' if int(stock.get('ai_score', 50) or 50) < 50 else '#008000'}">
                <span class="score-num" style="color: {'#DC143C' if int(stock.get('ai_score', 50) or 50) < 50 else '#008000'}">{stock.get('ai_score', '--')}</span>
                <span class="score-label" style="color: {'#DC143C' if int(stock.get('ai_score', 50) or 50) < 50 else '#008000'}">{stock.get('ai_signal', '--')}</span>
            </div>
        </div>
    </div>"""

        # 指标表格
        indicators = stock.get('indicators', [])
        if indicators:
            html += """
    <table class="ind-table">
        <thead><tr><th>指标</th><th>数值</th><th>状态</th><th>解读</th></tr></thead>
        <tbody>"""
            for ind in indicators:
                status_color = ''
                if '✅' in ind.get('status', '') or '多头' in ind.get('status', ''):
                    status_color = 'color: #008000;'
                elif '⚠️' in ind.get('status', '') or '空头' in ind.get('status', '') or '死叉' in ind.get('status', ''):
                    status_color = 'color: #DC143C;'
                elif '偏强' in ind.get('status', '') or '金叉' in ind.get('status', ''):
                    status_color = 'color: #FF8C00;'
                
                html += f"""<tr>
                    <td class="ind-name-cell">{ind['name']}</td>
                    <td class="ind-val-cell">{ind['value']}</td>
                    <td class="ind-status-cell" style="{status_color}">{ind['status']}</td>
                    <td class="ind-desc-cell">{ind['desc']}</td>
                </tr>"""
            html += """</tbody></table>"""

        # 操作建议
        rule_advice = stock.get('rule_advice', '')
        ai_advice = stock.get('ai_advice', '')
        if rule_advice or ai_advice:
            html += """
    <div class="advice-box">
        <h4>📌 操作建议</h4>"""
            if rule_advice:
                html += f"""<p><b>规则建议:</b> {rule_advice}</p>"""
            if ai_advice:
                html += f"""<p><b>AI 建议:</b> {ai_advice}</p>"""
            html += """</div>"""

        html += """</div>"""

    html += f"""
<div class="footer">
    本报告基于公开数据自动生成，仅供参考，不构成投资建议
    <br>生成时间: {date_str} {get_timestamp()[:4]}:{get_timestamp()[4:6]}
    <br>数据来源: Tushare Pro + 腾讯行情API
</div>
</div>
</body>
</html>"""
    
    return html

def main():
    date_str = get_date_str()
    stocks_data = []
    
    for s in ZIXUAN_STOCKS:
        filepath = os.path.join(OUTPUT_DIR, f"{s['market']}{s['code']}_{s['name']}_report.html")
        data = parse_stock_report(filepath)
        if data:
            data['code'] = s['code']
            data['market'] = s['market']
            data['name'] = s['name']
            stocks_data.append(data)
            print(f"  ✅ {s['name']} ({s['code']}): 评分 {data.get('holmes_score', '--')}")
        else:
            print(f"  ⚠️  {s['name']} ({s['code']}): 报告未找到")
    
    if not stocks_data:
        print("❌ 没有可用的数据")
        return
    
    print(f"\n生成合并报告... {len(stocks_data)} 只股票")
    html = generate_zixuan_html(stocks_data, date_str)
    
    # 保存时间戳版本
    ts = get_timestamp()
    filename_ts = f"自选股分析_{ts}.html"
    filepath_ts = os.path.join(ZIXUAN_DIR, filename_ts)
    with open(filepath_ts, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  ✅ {filepath_ts} ({len(html)} bytes)")
    
    # 保存最新版本
    filepath_latest = os.path.join(ZIXUAN_DIR, "自选股分析_最新.html")
    with open(filepath_latest, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  ✅ {filepath_latest}")
    
    print(f"\n🔗 访问: http://47.116.23.182:8081/tiantian_reports_8k3m/")

if __name__ == '__main__':
    main()
