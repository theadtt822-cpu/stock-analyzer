#!/usr/bin/env python3.11
"""价格监控：检查天通和沃格是否触发预警价位，触发则发飞书提醒"""
import urllib.request, json, os, sys, subprocess

FLAG_DIR = "/tmp/stock_alerts"
os.makedirs(FLAG_DIR, exist_ok=True)

def get_price(code):
    prefix = "sh" if code.startswith("6") else "sz"
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    raw = urllib.request.urlopen(url, timeout=5).read().decode('gbk')
    p = raw.split('~')
    return float(p[3]), float(p[32])

def get_feishu_token():
    """获取飞书tenant_access_token"""
    try:
        cfg_path = "/home/admin/.openclaw/gateway.json"
        with open(cfg_path) as f:
            cfg = json.load(f)
        acc = cfg.get('channels', {}).get('feishu', {}).get('accounts', {}).get('tiantian', {})
        app_id = acc.get('appId', '')
        app_secret = acc.get('appSecret', '')
        if not app_id or not app_secret:
            return None
        
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
            headers={"Content-Type": "application/json"}
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
        return resp.get('tenant_access_token', '')
    except:
        return None

def send_feishu_msg(token, msg_text):
    """发送飞书消息给邓天天"""
    try:
        content = json.dumps({"text": msg_text})
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            data=json.dumps({
                "receive_id": "ou_0b30fb807b98f8f5c18865912b8975cf",
                "msg_type": "text",
                "content": content
            }).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read())
        return result.get('code', -1) == 0
    except Exception as e:
        print(f"飞书发送失败: {e}")
        return False

# 监控配置
checks = [
    {"name": "天通股份", "code": "600330",
     "triggers": [
         {"id": "tt_down285", "cond": lambda p: p <= 28.5, "msg": "🔴 天通股份跌破28.5！现价{}，建议减仓1/3！"},
         {"id": "tt_up295", "cond": lambda p: p >= 29.5, "msg": "🟡 天通股份反弹到29.5！现价{}，建议减仓！"},
     ]},
    {"name": "沃格光电", "code": "603773",
     "triggers": [
         {"id": "wg_up74", "cond": lambda p: p >= 74.0, "msg": "🟡 沃格光电冲上74！现价{}，建议减仓更多！"},
         {"id": "wg_down70", "cond": lambda p: p <= 70.0, "msg": "🔴 沃格光电跌破70！现价{}，注意止损！"},
     ]},
]

alerts = []
for stock in checks:
    try:
        price, pct = get_price(stock["code"])
        for t in stock["triggers"]:
            flag = f"{FLAG_DIR}/{t['id']}.done"
            if t["cond"](price) and not os.path.exists(flag):
                alerts.append(f"【{stock['name']}】现价{price:.2f}（{pct:+.1f}%）→ {t['msg'].format(f'{price:.2f}')}")
                open(flag, 'w').close()
            elif not t["cond"](price) and os.path.exists(flag):
                os.remove(flag)
    except Exception as e:
        alerts.append(f"⚠️ {stock['name']} 数据获取失败: {e}")

if alerts:
    token = get_feishu_token()
    if token:
        full_msg = "🕵️‍♂️ 股价预警\n\n" + "\n\n".join(alerts) + "\n\n— StockHolmes"
        if send_feishu_msg(token, full_msg):
            print(f"Alert sent: {len(alerts)} alerts")
        else:
            print("Alert send failed")
    else:
        print("No feishu token")
else:
    print("No alerts")
