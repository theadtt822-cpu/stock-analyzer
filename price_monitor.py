#!/usr/bin/env python3.11
"""盘中价格监控脚本：检查天通股份和沃格光电是否触发预警价位"""
import urllib.request, json, sys, os

FLAG_DIR = "/tmp/stock_alerts"
os.makedirs(FLAG_DIR, exist_ok=True)

stocks = {
    "天通股份": {
        "code": "600330",
        "secid": "1.600330",
        "triggers": {
            "跌破28.5": {"condition": lambda p: p <= 28.5, "msg": "🔴 天通股份跌破28.5（现价{}），建议减仓1/3！"},
            "反弹到29.5": {"condition": lambda p: p >= 29.5, "msg": "🟡 天通股份反弹到29.5（现价{}），建议减仓！"},
        }
    },
    "沃格光电": {
        "code": "603773",
        "secid": "1.603773",
        "triggers": {
            "冲上74": {"condition": lambda p: p >= 74.0, "msg": "🟡 沃格光电冲上74（现价{}），建议减仓更多！"},
            "跌破70": {"condition": lambda p: p <= 70.0, "msg": "🔴 沃格光电跌破70（现价{}），注意止损！"},
        }
    }
}

alerts = []
for name, cfg in stocks.items():
    try:
        url = f"https://qt.gtimg.cn/q=sz{cfg['code']}" if cfg['code'].startswith('0') or cfg['code'].startswith('3') else f"https://qt.gtimg.cn/q=sh{cfg['code']}"
        raw = urllib.request.urlopen(url, timeout=5).read().decode('gbk')
        p = raw.split('~')
        price = float(p[3])
        
        for tname, tcfg in cfg['triggers'].items():
            flag_file = f"{FLAG_DIR}/{name}_{tname}.flag"
            if tcfg["condition"](price) and not os.path.exists(flag_file):
                # Trigger hit and not yet alerted
                alerts.append(tcfg["msg"].format(f"{price:.2f}"))
                # Create flag to prevent duplicate alerts
                open(flag_file, 'w').close()
            elif not tcfg["condition"](price):
                # Price moved back, clear flag
                if os.path.exists(flag_file):
                    os.remove(flag_file)
    except Exception as e:
        alerts.append(f"⚠️ {name} 数据获取失败: {e}")

if alerts:
    print("ALERT")
    for a in alerts:
        print(a)
else:
    print("OK")
