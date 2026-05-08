#!/usr/bin/env python3.11
"""价格监控告警脚本：检测触发价位后发送飞书提醒"""
import urllib.request, json, os, sys

FLAG_DIR = "/tmp/stock_alerts"
os.makedirs(FLAG_DIR, exist_ok=True)

def get_price(code):
    prefix = "sh" if code.startswith("6") else "sz"
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    raw = urllib.request.urlopen(url, timeout=5).read().decode('gbk')
    p = raw.split('~')
    return float(p[3]), float(p[32])

checks = [
    {"name": "天通股份", "code": "600330",
     "triggers": [
         {"id": "tt_down285", "cond": lambda p: p <= 28.5, "msg": "🔴 天通股份跌破28.5！建议减仓1/3！"},
         {"id": "tt_up295", "cond": lambda p: p >= 29.5, "msg": "🟡 天通股份反弹到29.5！建议减仓！"},
     ]},
    {"name": "沃格光电", "code": "603773",
     "triggers": [
         {"id": "wg_up74", "cond": lambda p: p >= 74.0, "msg": "🟡 沃格光电冲上74！建议减仓更多！"},
         {"id": "wg_down70", "cond": lambda p: p <= 70.0, "msg": "🔴 沃格光电跌破70！注意止损！"},
     ]},
]

alerts = []
for stock in checks:
    try:
        price, pct = get_price(stock["code"])
        for t in stock["triggers"]:
            flag = f"{FLAG_DIR}/{t['id']}.done"
            if t["cond"](price) and not os.path.exists(flag):
                alerts.append(f"【{stock['name']}】现价{price:.2f}（{pct:+.1f}%）→ {t['msg']}")
                open(flag, 'w').close()
            elif not t["cond"](price) and os.path.exists(flag):
                os.remove(flag)
    except Exception as e:
        alerts.append(f"⚠️ {stock['name']} 数据获取失败: {e}")

if alerts:
    print("ALERT_FOUND")
    print("\n".join(alerts))
else:
    print("NO_ALERT")
