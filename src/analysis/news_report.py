"""
每日投资新闻汇总报告生成器
"""
import html
from datetime import datetime

# 共用 CSS 样式（与 report_generator.py 一致）
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
.status-red { color: #DC143C; }
.status-green { color: #008000; }
.status-orange { color: #FF8C00; }
.status-gray { color: #888; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-positive { background: #ffebee; color: #DC143C; }
.badge-negative { background: #e8f5e9; color: #008000; }
.badge-neutral { background: #f5f5f5; color: #888; }
.badge-high { background: #DC143C; color: #fff; }
.badge-medium { background: #FF8C00; color: #fff; }
.badge-low { background: #888; color: #fff; }
@media (max-width: 600px) { .advice-grid { grid-template-columns: 1fr; } }
"""


class NewsReportGenerator:
    """每日投资新闻汇总报告生成器"""

    def __init__(self, date_str: str):
        self.date_str = date_str

    def generate_html(self, data: dict, save_path: str) -> str:
        h = html.escape

        a_stock_news = data.get('a_stock_news', [])
        us_stock_news = data.get('us_stock_news', [])
        economic_indicators = data.get('economic_indicators', [])
        investment_views = data.get('investment_views', [])

        a_rows = ""
        for n in a_stock_news:
            impact = n.get('impact', 'neutral')
            badge_cls = 'badge-positive' if impact == 'positive' else ('badge-negative' if impact == 'negative' else 'badge-neutral')
            impact_label = '利好' if impact == 'positive' else ('利空' if impact == 'negative' else '中性')
            a_rows += f"""
            <div class="indicator-row">
                <span class="badge {badge_cls}">{impact_label}</span>
                <div style="flex:1">
                    <div style="font-weight:600;font-size:14px;margin-bottom:4px">{h(n.get('title',''))}</div>
                    <div style="font-size:12px;color:#666">{h(n.get('summary',''))}</div>
                </div>
                <span style="font-size:11px;color:#aaa;white-space:nowrap">{h(n.get('source',''))}</span>
            </div>"""

        us_rows = ""
        for n in us_stock_news:
            impact = n.get('impact', 'neutral')
            badge_cls = 'badge-positive' if impact == 'positive' else ('badge-negative' if impact == 'negative' else 'badge-neutral')
            impact_label = '利好' if impact == 'positive' else ('利空' if impact == 'negative' else '中性')
            us_rows += f"""
            <div class="indicator-row">
                <span class="badge {badge_cls}">{impact_label}</span>
                <div style="flex:1">
                    <div style="font-weight:600;font-size:14px;margin-bottom:4px">{h(n.get('title',''))}</div>
                    <div style="font-size:12px;color:#666">{h(n.get('summary',''))}</div>
                </div>
                <span style="font-size:11px;color:#aaa;white-space:nowrap">{h(n.get('source',''))}</span>
            </div>"""

        eco_rows = ""
        for ind in economic_indicators:
            eco_rows += f"""
            <div class="indicator-row">
                <span class="ind-name">{h(ind.get('name',''))}</span>
                <span class="ind-value">{h(str(ind.get('value','')))}</span>
                <span class="ind-status status-{ind.get('change_color','gray')}">{h(str(ind.get('change','')))}</span>
                <span class="ind-desc">{h(ind.get('interpretation',''))}</span>
            </div>"""

        view_rows = ""
        for v in investment_views:
            dir_color = '#DC143C' if v.get('direction') == 'bullish' else ('#008000' if v.get('direction') == 'bearish' else '#888')
            dir_label = '看多' if v.get('direction') == 'bullish' else ('看空' if v.get('direction') == 'bearish' else '中性')
            view_rows += f"""
            <div style="background:#f8f9fa;border-radius:8px;padding:14px;margin-bottom:10px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                    <span style="font-weight:600;font-size:14px">{h(v.get('firm',''))}</span>
                    <span style="color:{dir_color};font-weight:600;font-size:13px">{dir_label}</span>
                </div>
                <div style="font-size:13px;color:#555">{h(v.get('view',''))}</div>
            </div>"""

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投资新闻汇总 - {h(self.date_str)}</title>
<style>{_REPORT_CSS}
.indicator-row {{ display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid #f5f5f5; gap: 12px; }}
.indicator-row:last-child {{ border-bottom: none; }}
.ind-name {{ width: 80px; font-weight: 500; color: #666; font-size: 14px; }}
.ind-value {{ width: 160px; font-size: 13px; color: #888; font-family: 'SF Mono', monospace; }}
.ind-status {{ width: 80px; font-size: 13px; font-weight: 600; }}
.ind-desc {{ flex: 1; font-size: 13px; color: #555; }}
</style>
</head>
<body>
<div class="container">
<div class="header">
    <h1>投资新闻汇总</h1>
    <div class="date">{h(self.date_str)}</div>
</div>

<div class="card">
    <h2>A股要闻</h2>
    {a_rows if a_rows else '<div style="color:#999;padding:12px">暂无数据</div>'}
</div>

<div class="card">
    <h2>美股要闻</h2>
    {us_rows if us_rows else '<div style="color:#999;padding:12px">暂无数据</div>'}
</div>

<div class="card">
    <h2>国际经济指标</h2>
    {eco_rows if eco_rows else '<div style="color:#999;padding:12px">暂无数据</div>'}
</div>

<div class="card">
    <h2>知名投行观点</h2>
    {view_rows if view_rows else '<div style="color:#999;padding:12px">暂无数据</div>'}
</div>

<div class="footer">
    以上内容来源于公开新闻和投行研报，仅供参考，不构成投资建议
    <br>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>
</div>
</body>
</html>"""

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return save_path
