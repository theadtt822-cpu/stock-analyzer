#!/usr/bin/env python3.11
"""检查价格告警并发送飞书提醒（由cron定时执行）"""
import os, subprocess

FLAG_DIR = "/tmp/stock_alerts"
alert_file = "/tmp/stock_alerts/pending.msg"

if os.path.exists(alert_file):
    with open(alert_file) as f:
        msg = f.read().strip()
    os.remove(alert_file)
    # 用openclaw gateway发送飞书消息给邓天天
    # 先写到一个临时文件，让openclaw agent读取并发送
    notif_file = "/tmp/openclaw/notifications/price_alert.txt"
    os.makedirs(os.path.dirname(notif_file), exist_ok=True)
    with open(notif_file, 'w') as f:
        f.write(msg)
    print(f"Alert saved: {msg}")
else:
    print("No alerts")
