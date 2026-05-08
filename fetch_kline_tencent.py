#!/usr/bin/env python3
"""
腾讯股票API数据获取（东方财富K线API不可用时的备选方案）

东方财富 push2his API 从本服务器完全不通（空响应），
腾讯 API 可以正常获取K线数据。

用法：
    python fetch_kline_tencent.py 002222 603773
    python fetch_kline_tencent.py --all  # 从 portfolio_dashboard.json 读取所有股票
"""
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

# 腾讯财经API - K线数据
# 格式: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=市场代码,day,开始日期,结束日期,数量,qfq
# 深圳: sz + 代码, 上海: sh + 代码

def get_market_prefix(code):
    """根据股票代码判断市场前缀"""
    if code.startswith('6'):
        return 'sh'
    else:
        return 'sz'

def fetch_kline(code, days=65, start_date=None):
    """
    获取K线数据
    code: 股票代码（纯数字）
    days: 获取天数
    start_date: 开始日期 YYYY-MM-DD，默认65天前
    """
    market = get_market_prefix(code)
    full_code = f"{market}{code}"
    
    if start_date is None:
        from datetime import timedelta
        end_date = datetime.now()
        start_date = (end_date - timedelta(days=days*2)).strftime("%Y-%m-%d")  # 多取一些，因为有非交易日
    
    end_date_str = datetime.now().strftime("%Y-%m-%d")
    
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={full_code},day,{start_date},{end_date_str},{days},qfq"
    
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        req.add_header('Referer', 'https://stockapp.finance.qq.com/')
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        # 解析数据
        stock_data = data.get('data', {}).get(full_code, {})
        klines = stock_data.get('qfqday', [])
        
        if not klines:
            # 尝试其他格式
            klines = stock_data.get('day', [])
        
        result = []
        for k in klines:
            result.append({
                'date': k[0],
                'open': float(k[1]),
                'close': float(k[2]),
                'high': float(k[3]),
                'low': float(k[4]),
                'volume': float(k[5]),
            })
        
        return result
    
    except Exception as e:
        print(f"  ❌ {code} 获取失败: {e}")
        return []

def compute_indicators(klines):
    """根据K线数据计算技术指标"""
    import pandas as pd
    
    if len(klines) < 60:
        return None
    
    df = pd.DataFrame(klines)
    closes = df['close']
    volumes = df['volume']
    
    # 均线
    ma5 = round(closes.tail(5).mean(), 2)
    ma10 = round(closes.tail(10).mean(), 2)
    ma20 = round(closes.tail(20).mean(), 2)
    ma60 = round(closes.tail(60).mean(), 2)
    
    # MACD
    ema12 = closes.ewm(span=12).mean()
    ema26 = closes.ewm(span=26).mean()
    dif = round(ema12.iloc[-1] - ema26.iloc[-1], 2)
    dea = round((ema12 - ema26).ewm(span=9).mean().iloc[-1], 2)
    macd_bar = round(2 * (dif - dea), 3)
    
    # RSI
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).tail(14).mean()
    loss = (-delta.where(delta < 0, 0)).tail(14).mean()
    rs = gain / loss if loss != 0 else 100
    rsi = round(100 - (100 / (1 + rs)), 1)
    
    # 量比
    vol_5avg = volumes.tail(5).mean()
    vol_ratio = round(volumes.iloc[-1] / vol_5avg, 2) if vol_5avg > 0 else 1.0
    
    # 5日涨跌
    if len(closes) >= 6:
        change_5d = round((closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100, 2)
    else:
        change_5d = 0
    
    # 20日高低
    high_20 = round(closes.tail(20).max(), 2)
    low_20 = round(closes.tail(20).min(), 2)
    
    # 趋势判断
    if ma5 > ma10 > ma20:
        trend = '多头排列'
    elif ma5 < ma10 < ma20:
        trend = '空头排列'
    elif ma5 < ma10:
        trend = 'MA5回落'
    else:
        trend = '震荡'
    
    # 乖离率
    last_close = closes.iloc[-1]
    bias5 = round((last_close - ma5) / ma5 * 100, 2)
    bias20 = round((last_close - ma20) / ma20 * 100, 2)
    
    return {
        'ma5': ma5,
        'ma10': ma10,
        'ma20': ma20,
        'ma60': ma60,
        'dif': dif,
        'dea': dea,
        'macd_bar': macd_bar,
        'macd_signal': '金叉' if macd_bar > 0 else '死叉',
        'rsi': rsi,
        'vol_ratio': vol_ratio,
        'change_5d': change_5d,
        'high_20': high_20,
        'low_20': low_20,
        'tushare_close': round(last_close, 2),
        'trend': trend,
        'bias5': bias5,
        'bias20': bias20,
    }

if __name__ == '__main__':
    import sys
    import os
    
    sys.path.insert(0, os.path.dirname(__file__))
    
    codes = []
    
    if '--all' in sys.argv:
        # 从 portfolio_dashboard.json 读取所有股票
        data_file = os.path.join(os.path.dirname(__file__), 'output', 'boss', 'portfolio_dashboard.json')
        if not os.path.exists(data_file):
            data_file = os.path.join(os.path.dirname(__file__), 'output', 'portfolio_dashboard.json')
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        codes = [(r['code'], r['name']) for r in data['results']]
        print(f"从 portfolio_dashboard.json 读取到 {len(codes)} 只股票")
    else:
        # 从命令行参数读取
        for arg in sys.argv[1:]:
            if arg == '--all':
                continue
            codes.append((arg, arg))
    
    if not codes:
        print("用法: python fetch_kline_tencent.py 002222 603773")
        print("   或: python fetch_kline_tencent.py --all")
        sys.exit(1)
    
    results = {}
    
    for code, name in codes:
        print(f"\n📈 获取 {name} ({code})...")
        klines = fetch_kline(code, days=70)
        
        if klines:
            indicators = compute_indicators(klines)
            if indicators:
                results[code] = indicators
                print(f"  ✅ 获取 {len(klines)} 条K线")
                print(f"  最新收盘: {indicators['tushare_close']}")
                print(f"  MA5: {indicators['ma5']}  MA10: {indicators['ma10']}")
                print(f"  趋势: {indicators['trend']}")
                print(f"  RSI: {indicators['rsi']}  MACD: {indicators['macd_signal']}")
            else:
                print(f"  ⚠️ K线数据不足 ({len(klines)} 条)")
        else:
            print(f"  ❌ 获取失败")
        
        time.sleep(0.5)  # 避免太快被限流
    
    # 输出结果
    output_file = '/tmp/tencent_kline_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 结果已保存到 {output_file}")
    print(f"   成功: {len(results)}/{len(codes)}")
