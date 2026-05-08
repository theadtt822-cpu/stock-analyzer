"""
收盘复盘报告生成器
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
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 16px; }
.stat-item { background: rgba(255,255,255,0.1); border-radius: 8px; padding: 10px; }
.stat-label { font-size: 12px; opacity: 0.6; margin-bottom: 4px; }
.stat-value { font-size: 20px; font-weight: bold; }
.stat-change { font-size: 13px; font-weight: 600; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.level-tag { display: inline-block; background: #f0f2f5; padding: 4px 10px; border-radius: 4px; font-size: 13px; margin: 2px 4px 2px 0; }
.verdict-box { text-align: center; padding: 20px; }
.verdict-circle { width: 120px; height: 120px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 0 auto 16px; border: 4px solid; }
.verdict-text { font-size: 28px; font-weight: bold; }
.verdict-label { font-size: 13px; margin-top: 4px; }
@media (max-width: 600px) { .stats-grid { grid-template-columns: 1fr; } }
"""


class PostmarketReportGenerator:
    """收盘复盘报告生成器"""

    def __init__(self, date_str: str):
        self.date_str = date_str

    def generate_html(self, data: dict, save_path: str) -> str:
        h = html.escape

        indices = data.get('indices', [])
        idx_cards = ""
        for idx in indices:
            is_up = '+' in idx.get('pct_change', '')
            chg_color = "#DC143C" if is_up else "#008000"
            idx_cards += f"""
            <div class="stat-item">
                <div class="stat-label">{h(idx.get('name',''))} {h(idx.get('code',''))}</div>
                <div class="stat-value">{h(str(idx.get('close','')))} </div>
                <div class="stat-change" style="color:{chg_color}">{h(idx.get('pct_change',''))}</div>
                <div style="font-size:12px;color:rgba(255,255,255,0.5);margin-top:4px">
                    成交{h(str(idx.get('turnover','')))}  量{h(str(idx.get('volume','')))}
                </div>
            </div>"""

        # 板块涨跌
        sector_rise = data.get('sector_rise', [])
        sector_fall = data.get('sector_fall', [])

        rise_items = "".join(f"""
            <div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #f5f5f5">
                <span style="color:#DC143C;margin-right:8px;font-weight:600">{h(s.get('pct_change',''))}</span>
                <span style="font-size:14px">{h(s.get('sector',''))}</span>
            </div>""" for s in sector_rise)

        fall_items = "".join(f"""
            <div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #f5f5f5">
                <span style="color:#008000;margin-right:8px;font-weight:600">{h(s.get('pct_change',''))}</span>
                <span style="font-size:14px">{h(s.get('sector',''))}</span>
            </div>""" for s in sector_fall)

        # 涨停/跌停
        limit_up = data.get('limit_up', [])
        limit_down = data.get('limit_down', [])

        lu_rows = "".join(f"""
            <tr>
                <td style="padding:8px 12px;border-bottom:1px solid #f5f5f5">{h(s.get('name',''))}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #f5f5f5;color:#888">{h(s.get('code',''))}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #f5f5f5;font-size:13px;color:#666">{h(s.get('reason',''))}</td>
            </tr>""" for s in limit_up)

        ld_rows = "".join(f"""
            <tr>
                <td style="padding:8px 12px;border-bottom:1px solid #f5f5f5">{h(s.get('name',''))}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #f5f5f5;color:#888">{h(s.get('code',''))}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #f5f5f5;font-size:13px;color:#666">{h(s.get('reason',''))}</td>
            </tr>""" for s in limit_down)

        # 技术面分析
        tech = data.get('technical_analysis', {})
        supports = tech.get('support_levels', [])
        resistances = tech.get('resistance_levels', [])

        # 明日展望
        outlook = data.get('tomorrow_outlook', {})
        o_direction = outlook.get('direction', '震荡')
        o_factors = outlook.get('key_factors', [])
        o_strategy = outlook.get('strategy', '')

        if '看多' in o_direction or '涨' in o_direction:
            o_color = "#DC143C"
        elif '看空' in o_direction or '跌' in o_direction:
            o_color = "#008000"
        else:
            o_color = "#888"

        factor_items = "".join(f"<li style='margin:4px 0;font-size:14px;color:#555'>{h(f)}</li>" for f in o_factors)

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>收盘复盘 - {h(self.date_str)}</title>
<style>{_REPORT_CSS}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 8px 12px; border-bottom: 2px solid #f0f0f0; font-size: 13px; color: #888; font-weight: 500; }}
</style>
</head>
<body>
<div class="container">
<div class="header">
    <h1>收盘复盘</h1>
    <div class="date">{h(self.date_str)}</div>
    <div class="stats-grid">{idx_cards}</div>
</div>

<div class="card">
    <h2>板块涨跌排行</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
            <div style="font-weight:600;color:#DC143C;margin-bottom:8px">领涨板块</div>
            {rise_items if rise_items else '<div style="color:#999;font-size:13px">暂无数据</div>'}
        </div>
        <div>
            <div style="font-weight:600;color:#008000;margin-bottom:8px">领跌板块</div>
            {fall_items if fall_items else '<div style="color:#999;font-size:13px">暂无数据</div>'}
        </div>
    </div>
</div>

<div class="card">
    <h2>涨停 / 跌停</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
            <div style="font-weight:600;color:#DC143C;margin-bottom:8px">涨停 ({len(limit_up)}只)</div>
            {f'<table><tbody>{lu_rows}</tbody></table>' if lu_rows else '<div style="color:#999;font-size:13px">暂无数据</div>'}
        </div>
        <div>
            <div style="font-weight:600;color:#008000;margin-bottom:8px">跌停 ({len(limit_down)}只)</div>
            {f'<table><tbody>{ld_rows}</tbody></table>' if ld_rows else '<div style="color:#999;font-size:13px">暂无数据</div>'}
        </div>
    </div>
</div>

<div class="card">
    <h2>技术面分析</h2>
    <div style="margin-bottom:12px">
        <span style="font-weight:600;margin-right:8px">支撑位:</span>
        {''.join(f'<span class="level-tag">{h(s)}</span>' for s in supports)}
    </div>
    <div style="margin-bottom:12px">
        <span style="font-weight:600;margin-right:8px">压力位:</span>
        {''.join(f'<span class="level-tag">{h(r)}</span>' for r in resistances)}
    </div>
    <div style="font-size:14px;color:#555">{h(tech.get('volume_analysis',''))}</div>
    <div style="font-size:14px;color:#555;margin-top:4px">{h(tech.get('key_indicators',''))}</div>
</div>

<div class="card verdict-box">
    <h2>明日展望</h2>
    <div class="verdict-circle" style="border-color:{o_color}">
        <span class="verdict-text" style="color:{o_color}">{h(o_direction)}</span>
    </div>
    <div style="text-align:left;max-width:500px;margin:0 auto">
        <div style="font-weight:600;margin-bottom:8px">关注因素:</div>
        <ul style="padding-left:20px;margin-bottom:12px">{factor_items}</ul>
        <div style="font-weight:600;margin-bottom:4px">策略:</div>
        <div style="font-size:14px;color:#555">{h(o_strategy)}</div>
    </div>
</div>

<div class="footer">
    本报告基于公开数据自动生成，仅供参考，不构成投资建议
    <br>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>
</div>
</body>
</html>"""

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return save_path
