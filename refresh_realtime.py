#!/usr/bin/env python3
"""盘中实时刷新持仓仪表盘 - 用腾讯API获取实时行情更新现价"""
import json
import os
import re
import time
import urllib.request
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
BOSS_DIR = os.path.join(DATA_DIR, 'boss')

def get_market_prefix(code):
    if code.startswith('6'):
        return 'sh'
    return 'sz'

def fetch_realtime(codes):
    """从腾讯API获取实时行情"""
    params = ','.join(f'{get_market_prefix(c)}{c}' for c in codes)
    url = f'https://qt.gtimg.cn/q={params}'
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode('GBK')
        
        results = {}
        for line in text.strip().split(';'):
            line = line.strip()
            if not line:
                continue
            # v_sh600103="...";
            m = re.match(r'v_(\w+)="(.*)"', line)
            if not m:
                continue
            full_code = m.group(1)
            parts = m.group(2).split('~')
            if len(parts) < 45:
                continue
            
            code = full_code[2:]  # remove sh/sz
            current = float(parts[3])      # 现价
            prev_close = float(parts[4])   # 昨收
            open_price = float(parts[5])   # 今开
            volume = float(parts[6])       # 成交量(手)
            change_pct = float(parts[32])  # 涨跌幅%
            high = float(parts[33])        # 最高
            low = float(parts[34])         # 最低
            amount = float(parts[37]) if len(parts) > 37 else 0  # 成交额(万)
            
            results[code] = {
                'current': current,
                'pre_close': prev_close,
                'open': open_price,
                'high': high,
                'low': low,
                'change_pct': change_pct,
                'volume': volume,
                'amount': amount,
            }
        
        return results
    except Exception as e:
        print(f'❌ 实时行情获取失败: {e}')
        return {}

def refresh():
    data_file = os.path.join(BOSS_DIR, 'portfolio_dashboard.json')
    if not os.path.exists(data_file):
        data_file = os.path.join(DATA_DIR, 'portfolio_dashboard.json')
    
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    codes = [r['code'] for r in data['results']]
    print(f'📡 获取 {len(codes)} 只实时行情...')
    quotes = fetch_realtime(codes)
    
    if not quotes:
        print('❌ 获取失败，退出')
        return
    
    total_cost = 0
    total_value = 0
    
    for r in data['results']:
        code = r['code']
        q = quotes.get(code)
        if q:
            old_current = r.get('_user_current', r['current'])
            r['_user_current'] = old_current  # 保留用户设定的现价作为成本参考
            r['current'] = q['current']       # 更新为实时现价
            r['pre_close'] = q['pre_close']
            r['day_change'] = q['change_pct']
            
            # 更新盈亏
            r['pnl'] = (q['current'] - r['cost']) * r['qty']
            r['pnl_pct'] = round((q['current'] - r['cost']) / r['cost'] * 100, 2)
            r['position_value'] = q['current'] * r['qty']
            
            total_cost += r['position_cost']
            total_value += r['position_value']
            
            print(f"  {r['name']:>6s} ({code}) 实时: {q['current']:.2f}  涨跌: {q['change_pct']:+.2f}%  盈亏: {r['pnl']:+,.0f} ({r['pnl_pct']:+.1f}%)")
        else:
            total_cost += r['position_cost']
            total_value += r['current'] * r['qty']
            print(f"  {r['name']:>6s} ({code}) ⚠️ 未获取到实时数据")
    
    data['total_cost'] = total_cost
    data['total_value'] = total_value
    data['total_pnl'] = total_value - total_cost
    data['total_pnl_pct'] = round((total_value - total_cost) / total_cost * 100, 2)
    
    now = datetime.now()
    data['date'] = now.strftime('%Y-%m-%d')
    data['report_time'] = now.strftime('%Y-%m-%d %H:%M') + ' 盘中实时'
    
    # 保存更新后的JSON
    with open(data_file, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f'\n✅ 实时数据已更新 (截至 {data["report_time"]})')
    print(f'   总盈亏: {data["total_pnl"]:+,.0f} ({data["total_pnl_pct"]:+.1f}%)')
    
    # 生成仪表盘HTML
    from gen_dashboard_v2 import generate
    
    html = generate(data, report_time=data['report_time'])
    
    ts = now.strftime("%Y%m%d_%H%M")
    out_path = os.path.join(BOSS_DIR, f'持仓仪表盘_{ts}.html')
    with open(out_path, 'w') as f:
        f.write(html)
    
    latest_path = os.path.join(BOSS_DIR, '持仓仪表盘_最新.html')
    with open(latest_path, 'w') as f:
        f.write(html)
    
    main_path = os.path.join(DATA_DIR, 'portfolio_dashboard.html')
    with open(main_path, 'w') as f:
        f.write(html)
    
    print(f'   📊 报告已生成: {out_path}')
    print(f'   📊 文件大小: {len(html):,} bytes')

if __name__ == '__main__':
    refresh()
