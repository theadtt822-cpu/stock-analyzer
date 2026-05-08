"""
开盘前预测报告生成器
"""
import html
from datetime import datetime

_REPORT_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'Microsoft YaHei', 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; padding: 16px; }
.container { max-width: 900px; margin: 0 auto; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 16px; padding: 20px; }
h2 { font-size: 16px; color: #333; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px; margin-bottom: 16px; }
.header { background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; border-radius: 12px; padding: 24px; margin-bottom: 16px; }
.header h1 { font-size: 22px; margin-bottom: 4px; }
.header .date { font-size: 13px; opacity: 0.7; }
.footer { text-align: center; padding: 16px; color: #999; font-size: 12px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-positive { background: #ffebee; color: #DC143C; }
.badge-negative { background: #e8f5e9; color: #008000; }
.badge-high { background: #DC143C; color: #fff; }
.badge-medium { background: #FF8C00; color: #fff; }
.badge-low { background: #888; color: #fff; }
.verdict-box { text-align: center; padding: 20px; }
.verdict-circle { width: 120px; height: 120px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 0 auto 16px; border: 4px solid; }
.verdict-text { font-size: 28px; font-weight: bold; }
.verdict-label { font-size: 13px; margin-top: 4px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-top: 16px; }
.stat-item { background: rgba(255,255,255,0.1); border-radius: 8px; padding: 10px; }
.stat-label { font-size: 12px; opacity: 0.6; margin-bottom: 4px; }
.stat-value { font-size: 16px; font-weight: 500; }
@media (max-width: 600px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
"""


class PremarketReportGenerator:
    """开盘前预测报告生成器"""

    def __init__(self, date_str: str):
        self.date_str = date_str

    def generate_html(self, data: dict, save_path: str) -> str:
        h = html.escape

        # 隔夜外盘
        overnight = data.get('overnight_us', {})
        us_indices = overnight.get('indices', [])
        us_summary = overnight.get('summary', '')

        us_cards = ""
        for idx in us_indices:
            is_up = '+' in idx.get('pct_change', '')
            chg_color = "#DC143C" if is_up else "#008000"
            us_cards += f"""
            <div class="stat-item">
                <div class="stat-label">{h(idx.get('name',''))}</div>
                <div class="stat-value">{h(idx.get('close',''))}</div>
                <div style="color:{chg_color};font-size:13px;font-weight:600">{h(idx.get('pct_change',''))}</div>
            </div>"""

        hk = data.get('hk_market', {})
        hk_is_up = '+' in hk.get('pct_change', '') if hk.get('pct_change') else True
        hk_color = "#DC143C" if hk_is_up else "#008000"

        # 期货
        futures = data.get('futures', [])
        fut_rows = ""
        for f in futures:
            is_up = '+' in f.get('pct_change', '')
            chg_color = "#DC143C" if is_up else "#008000"
            fut_rows += f"""
            <div class="indicator-row" style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f5f5f5">
                <span>{h(f.get('name',''))}</span>
                <span style="color:{chg_color};font-weight:600">{h(f.get('pct_change',''))}</span>
            </div>"""

        # 政策消息
        policies = data.get('policy_news', [])
        pol_rows = ""
        for p in policies:
            level = p.get('impact_level', 'medium')
            badge_cls = 'badge-high' if level == 'high' else ('badge-medium' if level == 'medium' else 'badge-low')
            level_label = '高' if level == 'high' else ('中' if level == 'medium' else '低')
            pol_rows += f"""
            <div style="background:#f8f9fa;border-radius:8px;padding:14px;margin-bottom:10px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                    <span style="font-weight:600;font-size:14px">{h(p.get('title',''))}</span>
                    <span class="badge {badge_cls}">{level_label}影响</span>
                </div>
                <div style="font-size:13px;color:#555">{h(p.get('summary',''))}</div>
            </div>"""

        # 板块预测
        sector = data.get('sector_forecast', {})
        bullish = sector.get('bullish', [])
        bearish = sector.get('bearish', [])

        bull_items = "".join(f"""
            <div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #f5f5f5">
                <span style="color:#DC143C;margin-right:8px">▲</span>
                <div style="flex:1">
                    <span style="font-weight:600;font-size:14px">{h(s.get('sector',''))}</span>
                    <div style="font-size:12px;color:#888">{h(s.get('reason',''))}</div>
                </div>
            </div>""" for s in bullish)

        bear_items = "".join(f"""
            <div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #f5f5f5">
                <span style="color:#008000;margin-right:8px">▼</span>
                <div style="flex:1">
                    <span style="font-weight:600;font-size:14px">{h(s.get('sector',''))}</span>
                    <div style="font-size:12px;color:#888">{h(s.get('reason',''))}</div>
                </div>
            </div>""" for s in bearish)

        # 综合研判
        verdict = data.get('overall_verdict', {})
        v_direction = verdict.get('direction', '震荡')
        v_confidence = verdict.get('confidence', '中')
        v_reasoning = verdict.get('reasoning', '')

        if '看多' in v_direction or '涨' in v_direction:
            v_color = "#DC143C"
            v_bg = "#fff5f5"
            v_border = "#DC143C"
        elif '看空' in v_direction or '跌' in v_direction:
            v_color = "#008000"
            v_bg = "#f5fff5"
            v_border = "#008000"
        else:
            v_color = "#888"
            v_bg = "#f5f5f5"
            v_border = "#888"

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>开盘前预测 - {h(self.date_str)}</title>
<style>{_REPORT_CSS}
.indicator-row {{ display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid #f5f5f5; gap: 12px; }}
</style>
</head>
<body>
<div class="container">
<div class="header">
    <h1>开盘前预测</h1>
    <div class="date">{h(self.date_str)}</div>
</div>

<div class="card verdict-box">
    <h2>综合研判</h2>
    <div class="verdict-circle" style="border-color:{v_color}">
        <span class="verdict-text" style="color:{v_color}">{h(v_direction)}</span>
        <span class="verdict-label" style="color:{v_color}">置信度:{h(v_confidence)}</span>
    </div>
    <div style="font-size:14px;color:#555;max-width:500px;margin:0 auto">{h(v_reasoning)}</div>
</div>

<div class="card">
    <h2>隔夜外盘</h2>
    <div class="stats-grid">{us_cards}</div>
    <div style="margin-top:12px;font-size:13px;color:#555">{h(us_summary)}</div>
    <div style="margin-top:16px;padding-top:12px;border-top:1px solid #f0f0f0">
        <div style="font-weight:600;margin-bottom:8px">港股恒生指数</div>
        <span style="font-size:18px">{h(hk.get('close',''))}</span>
        <span style="color:{hk_color};margin-left:8px;font-weight:600">{h(hk.get('pct_change',''))}</span>
        <div style="font-size:13px;color:#888;margin-top:4px">{h(hk.get('summary',''))}</div>
    </div>
    <div style="margin-top:16px;padding-top:12px;border-top:1px solid #f0f0f0">
        <div style="font-weight:600;margin-bottom:8px">股指期货</div>
        {fut_rows}
    </div>
</div>

<div class="card">
    <h2>政策消息</h2>
    {pol_rows if pol_rows else '<div style="color:#999;padding:12px">暂无重要政策消息</div>'}
</div>

<div class="card">
    <h2>板块预测</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
            <div style="font-weight:600;color:#DC143C;margin-bottom:8px">可能领涨</div>
            {bull_items if bull_items else '<div style="color:#999;font-size:13px">暂无数据</div>'}
        </div>
        <div>
            <div style="font-weight:600;color:#008000;margin-bottom:8px">可能领跌</div>
            {bear_items if bear_items else '<div style="color:#999;font-size:13px">暂无数据</div>'}
        </div>
    </div>
</div>

<div class="footer">
    本预测基于公开数据和市场分析，仅供参考，不构成投资建议
    <br>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>
</div>
</body>
</html>"""

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return save_path
