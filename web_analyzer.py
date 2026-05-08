#!/usr/bin/env python3
"""
StockHolmes 网页分析入口
支持多人使用，各自独立目录
"""
import os
import sys
import json
import subprocess
import shutil
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, quote

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(SCRIPT_DIR, '.venv', 'bin', 'python')
BATCH_SCRIPT = os.path.join(SCRIPT_DIR, 'batch_analyze.py')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')

USERS = {
    'boss': {'name': '天天', 'emoji': '👑'},
    'boyfriend': {'name': '波波', 'emoji': '💑'}
}

HTML_INDEX = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StockHolmes 网页分析</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, 'Microsoft YaHei', 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px; text-align: center; }
        .header h1 { font-size: 24px; margin-bottom: 8px; }
        .header p { font-size: 14px; opacity: 0.8; }
        .card { background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .card h2 { font-size: 16px; margin-bottom: 16px; color: #333; }
        label { display: block; font-size: 14px; color: #666; margin-bottom: 8px; }
        input[type="text"] { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; margin-bottom: 12px; }
        input[type="text"]:focus { outline: none; border-color: #4a90d9; }
        .btn { background: #4a90d9; color: #fff; border: none; padding: 12px 24px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; }
        .btn:hover { background: #357abd; }
        .btn:disabled { background: #ccc; cursor: not-allowed; }
        .result { margin-top: 16px; padding: 16px; border-radius: 8px; display: none; }
        .result.success { background: #e8f5e9; border: 1px solid #4caf50; }
        .result.error { background: #ffebee; border: 1px solid #f44336; }
        .result a { color: #4a90d9; text-decoration: none; font-weight: bold; }
        .hint { font-size: 12px; color: #999; margin-bottom: 12px; }
        .user-select { display: flex; gap: 12px; margin-bottom: 16px; }
        .user-btn { flex: 1; padding: 16px; border: 2px solid #ddd; border-radius: 8px; text-align: center; cursor: pointer; transition: all 0.2s; background: #fff; }
        .user-btn:hover { border-color: #4a90d9; }
        .user-btn.active { border-color: #4a90d9; background: #e3f2fd; }
        .user-btn .emoji { font-size: 32px; margin-bottom: 8px; }
        .user-btn .name { font-size: 14px; font-weight: bold; }
        .loading { text-align: center; padding: 20px; display: none; }
        .loading .spinner { display: inline-block; width: 40px; height: 40px; border: 4px solid #ddd; border-top-color: #4a90d9; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .progress-text { color: #4a90d9; font-size: 14px; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🕵️‍♂️ StockHolmes</h1>
            <p>股市神探 · 个股分析</p>
        </div>

        <div class="card">
            <h2>选择使用者</h2>
            <div class="user-select">
                <button type="button" class="user-btn active" onclick="selectUser('boss')" id="btn-boss">
                    <div class="emoji">👑</div>
                    <div class="name">天天</div>
                </button>
                <button type="button" class="user-btn" onclick="selectUser('boyfriend')" id="btn-boyfriend">
                    <div class="emoji">💑</div>
                    <div class="name">波波</div>
                </button>
            </div>
        </div>

        <div class="card">
            <h2>输入要分析的股票</h2>
            <label>股票代码或名称（多个用逗号分隔）</label>
            <div class="hint">例如：贵州茅台 或 sh600519 或 神剑股份,东山精密</div>
            <input type="text" id="stocks" placeholder="输入股票代码或名称..." onkeydown="if(event.key==='Enter')analyze()">
            <button class="btn" id="analyzeBtn" onclick="analyze()">🔍 开始分析</button>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p class="progress-text" id="progressText">正在分析中，请稍候...</p>
        </div>

        <div class="result" id="result"></div>
    </div>

    <script>
        let currentUser = 'boss';

        function selectUser(user) {
            currentUser = user;
            document.querySelectorAll('.user-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('btn-' + user).classList.add('active');
        }

        async function analyze() {
            const input = document.getElementById('stocks').value.trim();
            if (!input) {
                alert('请输入股票代码或名称');
                return;
            }

            const btn = document.getElementById('analyzeBtn');
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');
            const progressText = document.getElementById('progressText');

            btn.disabled = true;
            loading.style.display = 'block';
            result.style.display = 'none';

            const msgs = ['正在获取数据...', '正在计算指标...', '正在生成报告...'];
            let msgIdx = 0;
            const interval = setInterval(() => {
                msgIdx = (msgIdx + 1) % msgs.length;
                progressText.textContent = msgs[msgIdx];
            }, 15000);

            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user: currentUser,
                        stocks: input
                    })
                });
                clearInterval(interval);
                const data = await response.json();

                if (data.success) {
                    result.className = 'result success';
                    let links = data.reports.map(r =>
                        `<div style="margin:8px 0"><a href="${r.url}" target="_blank">${r.name}</a></div>`
                    ).join('');
                    result.innerHTML = `<strong>✅ 分析完成！</strong>${links}`;
                } else {
                    result.className = 'result error';
                    result.innerHTML = `<strong>❌ 分析失败</strong><br>${data.message}`;
                }
            } catch (e) {
                clearInterval(interval);
                result.className = 'result error';
                result.innerHTML = `<strong>❌ 请求失败</strong><br>${e.message}`;
            } finally {
                btn.disabled = false;
                loading.style.display = 'none';
                result.style.display = 'block';
            }
        }
    </script>
</body>
</html>
"""


STOCK_CACHE_PATH = os.path.join(os.path.dirname(__file__), 'src', 'stock_codes.json')
STOCK_CACHE_TIMESTAMP_PATH = os.path.join(os.path.dirname(__file__), 'src', 'stock_codes_timestamp.json')

def get_cache_age_hours():
    """获取缓存年龄（小时）"""
    try:
        with open(STOCK_CACHE_TIMESTAMP_PATH) as f:
            ts = json.load(f).get('timestamp', 0)
        return (time.time() - ts) / 3600
    except:
        return 999

def load_stock_cache():
    """加载本地股票代码缓存"""
    try:
        with open(STOCK_CACHE_PATH) as f:
            return json.load(f)
    except:
        return {}

def refresh_stock_cache():
    """刷新股票代码缓存（后台线程，使用venv的python+akshare）"""
    try:
        import subprocess
        result = subprocess.run(
            [VENV_PYTHON, '-c', '''
import akshare as ak
import json
df = ak.stock_info_a_code_name()
mapping = {}
for _, row in df.iterrows():
    code = row['code']
    name = row['name']
    prefix = "sh" if code.startswith("6") else "sz"
    mapping[f"{prefix}{code}"] = name
    mapping[code] = name
    mapping[name] = f"{prefix}{code}"
import time
with open("''' + STOCK_CACHE_PATH + '''", "w") as f:
    json.dump(mapping, f, ensure_ascii=False)
with open("''' + STOCK_CACHE_TIMESTAMP_PATH + '''", "w") as f:
    json.dump({"timestamp": time.time()}, f)
print(f"OK:{len(mapping)}")
'''],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output.startswith('OK:'):
                count = int(output[3:])
                print(f"[缓存刷新] 成功，{count} 条记录")
            else:
                print(f"[缓存刷新] 输出异常: {output}")
        else:
            print(f"[缓存刷新] 失败: {result.stderr[:200]}")
    except Exception as e:
        print(f"[缓存刷新] 异常: {e}")

def start_cache_auto_refresh():
    """启动缓存自动刷新：检查是否超过24小时，是则刷新"""
    age = get_cache_age_hours()
    print(f"[缓存检查] 当前缓存年龄: {age:.1f} 小时")
    if age > 24:
        print("[缓存检查] 缓存已过期，开始刷新...")
        refresh_stock_cache()
    
    # 每天定时刷新
    def _daily_refresh():
        while True:
            time.sleep(86400)  # 24小时
            refresh_stock_cache()
    
    t = threading.Thread(target=_daily_refresh, daemon=True)
    t.start()
    print("[缓存检查] 自动刷新线程已启动（每24小时）")

def resolve_stocks(stocks_input):
    """解析输入，返回 (symbols, stock_names)"""
    cache = load_stock_cache()
    
    raw = [s.strip() for s in stocks_input.replace('，', ',').split(',') if s.strip()]
    symbols = []
    stock_names = {}
    
    for item in raw:
        if item.startswith(('sh', 'sz')):
            # 直接输入了代码，如 sh600519
            symbols.append(item)
            stock_names[item] = cache.get(item, item)
        else:
            # 输入了名称或纯数字代码
            if item.isdigit():
                # 纯数字代码
                symbol_sh = f'sh{item}'
                symbol_sz = f'sz{item}'
                if symbol_sh in cache:
                    symbols.append(symbol_sh)
                    stock_names[symbol_sh] = cache[symbol_sh]
                elif symbol_sz in cache:
                    symbols.append(symbol_sz)
                    stock_names[symbol_sz] = cache[symbol_sz]
                else:
                    symbols.append(symbol_sh)  # fallback
                    stock_names[symbol_sh] = item
            elif item in cache:
                # 名称直接匹配
                symbol = cache[item]
                symbols.append(symbol)
                stock_names[symbol] = item
            else:
                # 模糊匹配名称
                found = False
                search = item[:3]
                for key, name in cache.items():
                    if key.startswith(('sh', 'sz')) and search in name:
                        symbols.append(key)
                        stock_names[key] = name
                        found = True
                        break
                if not found:
                    symbols.append(item)
                    stock_names[item] = item
    
    return symbols, stock_names


def run_analysis(user, stocks_input):
    """运行分析"""
    symbols, stock_names = resolve_stocks(stocks_input)
    
    if not symbols:
        return {'success': False, 'message': '未找到有效的股票代码'}
    
    user_dir = os.path.join(OUTPUT_DIR, user)
    os.makedirs(user_dir, exist_ok=True)
    
    env = os.environ.copy()
    env['PYTHONPATH'] = SCRIPT_DIR
    
    cmd = [VENV_PYTHON, BATCH_SCRIPT] + symbols
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR, env=env, timeout=180)
    
    if result.returncode != 0:
        return {'success': False, 'message': f'分析失败: {result.stderr[:200]}'}
    
    # 将报告从 output/ 复制到用户目录，加时间戳
    reports = []
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    for symbol in symbols:
        name = stock_names.get(symbol, symbol)
        for fname in [f"{symbol}_{name}_report.html", f"{symbol}_report.html"]:
            src = os.path.join(OUTPUT_DIR, fname)
            if os.path.exists(src):
                # 文件名加时间戳，如 sh600519_贵州茅台_report_20260506_1710.html
                base, ext = os.path.splitext(fname)
                ts_fname = f"{base}_{ts}{ext}"
                dst = os.path.join(user_dir, ts_fname)
                shutil.copy2(src, dst)
                reports.append({
                    'name': f"{name} ({symbol})",
                    'url': f'/reports/{user}/{quote(ts_fname, safe="")}'
                })
                break
    
    if not reports:
        return {'success': False, 'message': '未生成报告文件'}
    
    return {'success': True, 'reports': reports}


class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.send_html(200, HTML_INDEX)
        elif self.path.startswith('/reports/'):
            # URL: /reports/boss/xxx.html -> file: output/boss/xxx.html
            rel = unquote(self.path[len('/reports/'):])
            full_path = os.path.join(OUTPUT_DIR, rel)
            if os.path.isfile(full_path):
                with open(full_path, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
        else:
            self.send_error(404)
    
    def do_POST(self):
        if self.path == '/api/analyze':
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length).decode('utf-8'))
            
            user = data.get('user', 'boss')
            stocks = data.get('stocks', '')
            
            if user not in USERS:
                user = 'boss'
            
            result = run_analysis(user, stocks)
            self.send_json(200, result)
        else:
            self.send_error(404)
    
    def send_html(self, code, html):
        body = html.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def log_message(self, fmt, *args):
        print(f"[{self.command}] {args[0]}")


if __name__ == '__main__':
    # 启动缓存自动刷新（检查并更新股票代码表）
    start_cache_auto_refresh()
    
    port = 8082
    server = HTTPServer(('0.0.0.0', port), WebHandler)
    server.request_queue_size = 32
    print(f"🕵️‍♂️ StockHolmes 网页分析已启动")
    print(f"   访问地址: http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.server_close()
