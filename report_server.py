#!/usr/bin/env python3
"""
StockHolmes 报告服务器
提供报告文件的 Web 访问界面
每个用户有独立的带密钥路径，互不可见
"""
import os
import glob
import re
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote, urlparse
import json

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')

USERS = {
    'tiantian_reports_8k3m': {
        'label': '天天', 'emoji': '👑', 'dir': os.path.join(OUTPUT_DIR, 'boss'), 'key': 'tiantian_reports_8k3m'
    },
    'bobo_reports_9x7n': {
        'label': '波波', 'emoji': '💑', 'dir': os.path.join(OUTPUT_DIR, 'boyfriend'), 'key': 'bobo_reports_9x7n'
    },
}

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockHolmes 报告中心 - {user_label}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, 'Microsoft YaHei', 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; padding: 16px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; border-radius: 10px; padding: 18px; margin-bottom: 14px; }}
        .header h1 {{ font-size: 20px; margin-bottom: 6px; }}
        .header p {{ font-size: 13px; opacity: 0.8; }}
        .section {{ background: #fff; border-radius: 10px; padding: 14px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
        .section h2 {{ font-size: 15px; color: #333; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 2px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center; }}
        .section h2 .count {{ font-size: 12px; color: #999; font-weight: normal; }}
        .report-list {{ display: flex; flex-direction: column; gap: 8px; }}
        .report-item {{ background: #fafafa; border-radius: 6px; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; font-size: 13px; }}
        .report-item:hover {{ background: #f0f0f0; }}
        .report-info h3 {{ font-size: 14px; margin-bottom: 2px; }}
        .report-info p {{ font-size: 11px; color: #999; }}
        .report-link {{ background: #4a90d9; color: #fff; padding: 5px 12px; border-radius: 5px; text-decoration: none; font-size: 12px; font-weight: 500; white-space: nowrap; }}
        .report-link:hover {{ background: #357abd; }}
        .empty {{ text-align: center; padding: 24px; color: #999; font-size: 13px; }}
        .badge {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; margin-left: 6px; }}
        .badge-pre {{ background: #e3f2fd; color: #1976d2; }}
        .badge-news {{ background: #fff3e0; color: #f57c00; }}
        .badge-post {{ background: #e8f5e9; color: #388e3c; }}
        .badge-stock {{ background: #fce4ec; color: #c2185b; }}
        .badge-dashboard {{ background: #ede7f6; color: #5e35b1; }}
        .badge-latest {{ background: #c8e6c9; color: #2e7d32; font-weight: bold; }}
        .badge-watchlist {{ background: #f3e5f5; color: #7b1fa2; }}
        .badge-three-d {{ background: #e0f7fa; color: #00838f; }}
        .badge-midday {{ background: #fff3e0; color: #e65100; }}
        .more-toggle {{ background: none; border: 1px solid #ddd; color: #666; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; margin-top: 6px; display: block; width: 100%; text-align: center; }}
        .more-toggle:hover {{ background: #f5f5f5; border-color: #ccc; }}
        .more-content {{ display: none; }}
        .more-content.show {{ display: block; }}
        .ft {{ text-align: center; padding: 16px; color: #999; font-size: 11px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 StockHolmes 报告中心</h1>
            <p>{user_emoji} {user_label} · 你的炒股龙虾 · 自动生成报告</p>
        </div>

        {sections}

        <div class="ft">
            <p>🕵️‍♂️ StockHolmes · 报告自动生成</p>
        </div>
    </div>
<script>
function toggleMore(id) {{
    var el = document.getElementById(id);
    var btn = document.getElementById(id + '-btn');
    if (el.classList.contains('show')) {{
        el.classList.remove('show');
        btn.textContent = btn.textContent.replace('收起', '更多');
    }} else {{
        el.classList.add('show');
        btn.textContent = btn.textContent.replace('更多', '收起');
    }}
}}
</script>
</body>
</html>
"""

MAX_SHOW = 10

def classify_report(filename):
    if filename.startswith('premarket_'):
        return {'type': 'daily', 'label': '盘前预测', 'badge': 'badge-pre'}
    if filename.startswith('news_'):
        return {'type': 'daily', 'label': '午间新闻', 'badge': 'badge-news'}
    if filename.startswith('postmarket_'):
        return {'type': 'daily', 'label': '收盘复盘', 'badge': 'badge-post'}
    if filename.startswith('财经日报'):
        if '_最新' in filename:
            return {'type': 'daily', 'label': '财经日报（最新）', 'badge': 'badge-latest'}
        match = re.search(r'(\d{8})', filename)
        if match:
            ts = match.group(1)
            label = f"财经日报 {ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            return {'type': 'daily', 'label': label, 'badge': 'badge-news'}
        return {'type': 'daily', 'label': '财经日报', 'badge': 'badge-news'}
    if '持仓仪表盘' in filename:
        if '_最新' in filename:
            return {'type': 'dashboard', 'label': '持仓仪表盘（最新）', 'badge': 'badge-latest'}
        match = re.search(r'(\d{8}_\d{4})', filename)
        if match:
            ts = match.group(1)
            label = f"持仓仪表盘 {ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}"
            return {'type': 'dashboard', 'label': label, 'badge': 'badge-dashboard'}
        return {'type': 'dashboard', 'label': '持仓仪表盘', 'badge': 'badge-dashboard'}
    if filename.startswith('三维分析报告'):
        if '_最新' in filename:
            return {'type': 'three_d', 'label': '三维分析报告（最新）', 'badge': 'badge-latest'}
        match = re.search(r'(\d{8})', filename)
        if match:
            ts = match.group(1)
            label = f"三维分析 {ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            return {'type': 'three_d', 'label': label, 'badge': 'badge-three-d'}
        return {'type': 'three_d', 'label': '三维分析报告', 'badge': 'badge-three-d'}
    if filename.startswith('午间复盘'):
        if '_最新' in filename or '_latest' in filename:
            return {'type': 'midday', 'label': '午间复盘（最新）', 'badge': 'badge-latest'}
        match = re.search(r'(\d{8})', filename)
        if match:
            ts = match.group(1)
            label = f"午间复盘 {ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            return {'type': 'midday', 'label': label, 'badge': 'badge-midday'}
        return {'type': 'midday', 'label': '午间复盘', 'badge': 'badge-midday'}
    if filename.startswith('盘后预测'):
        if '_最新' in filename:
            return {'type': 'postmarket', 'label': '盘后预测（最新）', 'badge': 'badge-latest'}
        match = re.search(r'(\d{8}_\d{4})', filename)
        if match:
            ts = match.group(1)
            label = f"盘后预测 {ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}"
            return {'type': 'postmarket', 'label': label, 'badge': 'badge-post'}
        return {'type': 'postmarket', 'label': '盘后预测', 'badge': 'badge-post'}
    if filename.startswith('自选股分析'):
        if '_最新' in filename:
            return {'type': 'watchlist', 'label': '自选股分析（最新）', 'badge': 'badge-latest'}
        match = re.search(r'(\d{8}_\d{4})', filename)
        if match:
            ts = match.group(1)
            label = f"自选股分析 {ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}"
            return {'type': 'watchlist', 'label': label, 'badge': 'badge-watchlist'}
        return {'type': 'watchlist', 'label': '自选股分析', 'badge': 'badge-watchlist'}
    match_report = re.match(r'^(sh|sz)(\d+)_(.+?)_report(_\d{8}_\d{4})?\.html$', filename)
    if match_report:
        code = match_report.group(1) + match_report.group(2)
        stock_name = match_report.group(3)
        label = f"{stock_name} ({code})"
        ts_match = re.search(r'_report_(\d{8}_\d{4})', filename)
        if ts_match:
            ts = ts_match.group(1)
            label += f" {ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}"
        return {'type': 'stock', 'label': label, 'badge': 'badge-stock'}
    return None

def extract_date(filename):
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match: return match.group(1)
    match = re.search(r'(\d{8})', filename)
    if match:
        ts = match.group(1)
        return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
    return ''

def extract_timestamp(filename):
    if '_最新' in filename: return (1, '99999999_9999')
    match = re.search(r'(\d{8})_(\d{4})', filename)
    if match: return (0, match.group(0))
    match = re.search(r'(\d{8})', filename)
    if match: return (0, match.group(1) + '_0000')
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
    if match: return (0, match.group(1) + match.group(2) + match.group(3) + '_0000')
    return (-1, filename)

def generate_report_html(filename, info, user_key):
    from urllib.parse import quote
    date = extract_date(filename)
    link_path = f"{user_key}/{quote(filename, safe='')}"
    return f"""
        <div class="report-item">
            <div class="report-info">
                <h3>{info['label']} <span class="badge {info['badge']}">{date}</span></h3>
                <p>{filename}</p>
            </div>
            <a href="/{link_path}" class="report-link" target="_blank">查看</a>
        </div>
    """

def render_section(title, icon, reports, section_id):
    """Render a section with max 10 visible + collapsible more"""
    total = len(reports)
    if total == 0:
        return f"""<div class="section"><h2>{icon} {title}</h2><div class="empty">暂无报告</div></div>"""
    
    shown = reports[:MAX_SHOW]
    more = reports[MAX_SHOW:]
    
    html = f'<div class="section"><h2>{icon} {title} <span class="count">共{total}份</span></h2>'
    html += '<div class="report-list">'
    html += ''.join(shown)
    if more:
        more_id = f'more-{section_id}'
        html += f'<div class="more-content" id="{more_id}">'
        html += ''.join(more)
        html += '</div>'
        html += f'<button class="more-toggle" id="{more_id}-btn" onclick="toggleMore(\'{more_id}\')">更多 ▼ ({len(more)})</button>'
    html += '</div></div>'
    return html

def scan_html_files(directory):
    if not os.path.isdir(directory): return []
    files = glob.glob(os.path.join(directory, '*.html'))
    return [(os.path.basename(f), directory) for f in files]

def generate_index(user_key):
    if user_key not in USERS: return None
    uinfo = USERS[user_key]
    target_dir = uinfo['dir']
    os.makedirs(target_dir, exist_ok=True)
    
    base_files = scan_html_files(target_dir)
    watchlist_dir = os.path.join(target_dir, 'watchlist')
    watchlist_files = scan_html_files(watchlist_dir)
    zixuan_dir = os.path.join(target_dir, 'zixuan')
    zixuan_files = scan_html_files(zixuan_dir)
    
    seen = set()
    files = []
    for fname, fdir in base_files + watchlist_files + zixuan_files:
        if fname not in seen:
            seen.add(fname)
            files.append((fname, fdir if fdir else target_dir))
    
    daily = []; stock = []; watchlist = []; dashboard = []; three_d = []; midday = []; postmarket = []
    for f, fdir in sorted(files, key=lambda x: extract_timestamp(x[0]), reverse=True):
        info = classify_report(f)
        if info:
            html = generate_report_html(f, info, user_key)
            if info['type'] == 'daily': daily.append(html)
            elif info['type'] == 'watchlist': watchlist.append(html)
            elif info['type'] == 'dashboard': dashboard.append(html)
            elif info['type'] == 'three_d': three_d.append(html)
            elif info['type'] == 'midday': midday.append(html)
            elif info['type'] == 'postmarket': postmarket.append(html)
            else: stock.append(html)
    
    # Order: 持仓仪表盘, 每日定时, 盘后预测, 自选股, 三维分析, 个股报告(最后)
    sections = ''
    sections += render_section('持仓仪表盘', '📊', dashboard, 'dashboard')
    sections += render_section('每日定时报告', '📈', daily, 'daily')
    sections += render_section('盘后预测 & 次日预测', '🔮', postmarket, 'postmarket')
    sections += render_section('自选股分析报告', '👀', watchlist, 'watchlist')
    sections += render_section('三维分析报告', '🕵️‍♂️', three_d, 'three_d')
    sections += render_section('午间复盘报告', '📊', midday, 'midday')
    sections += render_section('个股分析报告', '🔍', stock, 'stock')
    
    return INDEX_TEMPLATE.format(
        user_label=uinfo['label'], user_emoji=uinfo['emoji'], sections=sections
    )

class ReportHandler(SimpleHTTPRequestHandler):
    def _serve_file(self, filepath):
        self.send_response(200)
        if filepath.endswith('.html'):
            self.send_header('Content-type', 'text/html; charset=utf-8')
        elif filepath.endswith(('.png', '.jpg', '.jpeg')):
            self.send_header('Content-type', 'image/jpeg')
        else:
            self.send_header('Content-type', 'application/octet-stream')
        self.end_headers()
        with open(filepath, 'rb') as f:
            self.wfile.write(f.read())

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.strip('/')
        if not path:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
            return
        if path in USERS:
            idx = generate_index(path)
            if idx:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(idx.encode('utf-8'))
                return
        for key, uinfo in USERS.items():
            if path.startswith(key + '/'):
                rel = unquote(path[len(key)+1:])
                filepath = os.path.join(uinfo['dir'], rel)
                if os.path.exists(filepath):
                    self._serve_file(filepath)
                    return
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b'Not Found')

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8081), ReportHandler)
    print('StockHolmes Report Server running on port 8081')
    server.serve_forever()
