#!/usr/bin/env python3.11
"""
妖股盯盘监控 - 可进场信号检测 & 飞书推送

交易日定时执行：
    09:28 集合竞价后看开板机会
    09:40 开盘10分钟信号
    10:30 盘中信号
    11:15 午前信号
    13:05 下午开盘信号
    14:00 尾盘信号

用法：
    python yaogu_alert.py                    # 检测并推送飞书
    python yaogu_alert.py --v                # 仅打印不上推送
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime

# ======== 监控标的 ========
WATCH_LIST = [
    # 连板梯队
    ("603278", "大业股份", "3连板，机器人+商业航天双题材龙头"),
    ("603618", "杭电股份", "3连板，光通信概念"),
    ("002031", "巨轮智能", "2连板，低价小盘机器人，情绪标杆"),
    ("002552", "宝鼎科技", "2连板，PCB概念"),
    # 首板潜力
    ("301028", "鼎熔岩", "创业板20cm机器人，首板放量"),
    ("920270", "天铭科技", "北交所30cm机器人，流通16亿"),
    ("301387", "光大同创", "创业板，换手22%科技属性"),
    ("300840", "酷特智能", "创业板，换手30%量比4.3"),
    ("301696", "三瑞智能", "创业板，换手51%极致活跃"),
    ("688096", "京源环保", "科创板，换手17%量比6.3"),
]

# ======== 腾讯实时行情 ========
def fetch_realtime(code):
    market = "sh" if code.startswith("6") else "sz"
    url = f"http://qt.gtimg.cn/q={market}{code}"
    try:
        raw = urllib.request.urlopen(url, timeout=5).read().decode("gbk")
        m = re.search(r'"(.*?)"', raw)
        if not m: return None
        f = m.group(1).split("~")
        if len(f) < 47: return None
        return {
            "code": f[2], "name": f[1],
            "open": sf(f[5]), "prev": sf(f[4]), "price": sf(f[3]),
            "high": sf(f[33]), "low": sf(f[34]),
            "volume": sf(f[6]), "amount": sf(f[37]),
            "buy1": sf(f[10]), "sell1": sf(f[20]),
            "turnover": sf(f[38]), "pe": sf(f[39]),
            "amplitude": sf(f[43]), "mkt_cap": sf(f[44]),
        }
    except:
        return None

def sf(v):
    try:
        return float(v)
    except:
        return 0.0

def calc_chg(q):
    return round((q["price"] - q["prev"]) / q["prev"] * 100, 2) if q["prev"] > 0 else 0

# ======== 进场信号检测 ========
def check_signal(q, name, logic):
    if not q or q["prev"] == 0:
        return None
    chg = calc_chg(q)
    p = q["price"]
    prev = q["prev"]
    limit_up = round(prev * 1.1, 2)
    signals = []

    # 核心信号
    if chg >= 9.5 and q["sell1"] > 50:
        signals.append(f"🟡 涨停未封死！卖一还有{q['sell1']:.0f}手，可博弈回封")
    if q["high"] >= limit_up * 0.99 and p < limit_up * 0.99:
        signals.append(f"🔴 涨停炸板！最高{limit_up}，现{p}（{chg}%），等回封信号")
    if 1.5 <= chg <= 5 and q["open"] >= prev * 1.03:
        signals.append(f"🟢 高开回踩！开{q['open']}，现{p}（{chg}%），企稳可进")
    if 2 <= chg <= 7 and q["turnover"] >= 8:
        signals.append(f"⚡ 放量异动！涨{chg}% 换手{q['turnover']}%")

    if not signals:
        return None

    # 判断推荐等级
    if any("涨停未封" in s for s in signals):
        level = "🔥🔥" if chg < 10 else "🔥"
    elif any("炸板" in s for s in signals):
        level = "⚠️"
    elif any("回踩" in s for s in signals):
        level = "✅"
    else:
        level = "👀"

    return {
        "level": level,
        "name": name,
        "code": q["code"],
        "price": p,
        "chg": chg,
        "turnover": q["turnover"],
        "signals": signals,
        "logic": logic,
    }

# ======== 飞书推送 ========
CONFIG_PATH = "/home/admin/.openclaw/gateway.json"
BOBO_OPEN_ID = "ou_cc19d62ec1cb5c5db18c13bc61efce53"

def get_tenant_token():
    try:
        cfg_path = "/home/admin/.openclaw/openclaw.json"
        with open(cfg_path) as f:
            cfg = json.load(f)
        bobo = cfg.get("channels", {}).get("feishu", {}).get("accounts", {}).get("bobo", {})
        app_id, secret = bobo.get("appId"), bobo.get("appSecret")
        if not app_id or not secret:
            return None
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            data=json.dumps({"app_id": app_id, "app_secret": secret}).encode(),
            headers={"Content-Type": "application/json"}
        )
        return json.loads(urllib.request.urlopen(req, timeout=5).read()).get("tenant_access_token")
    except Exception as e:
        print(f"⚠️ get_tenant_token: {e}")
        return None

def send_to_feishu(token, text, open_id=BOBO_OPEN_ID):
    try:
        content = json.dumps({"text": text})
        req = urllib.request.Request(
            f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            data=json.dumps({"receive_id": open_id, "msg_type": "text", "content": content}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
        return resp.get("code", -1) == 0
    except:
        return False

# ======== 主函数 ========
def main(verbose=False):
    all_signals = []
    for code, name, logic in WATCH_LIST:
        q = fetch_realtime(code)
        sig = check_signal(q, name, logic)
        if sig:
            all_signals.append(sig)
        time.sleep(0.3)

    if not all_signals:
        msg = f"[{datetime.now().strftime('%H:%M')}] 妖股监控：当前无进场信号"
        if verbose:
            print(msg)
        with open("/home/admin/.openclaw/workspace/mx_data/output/yaogu_signal_latest.txt", "w") as f:
            f.write(msg)
        return

    # 排序：按信号等级
    order = {"🔥🔥": 0, "🔥": 1, "✅": 2, "👀": 3, "⚠️": 4}
    all_signals.sort(key=lambda x: order.get(x["level"], 9))

    lines = [
        "🕵️‍♂️ **妖股进场信号**",
        f"⏰ {datetime.now().strftime('%m-%d %H:%M')}",
        "",
    ]
    for s in all_signals:
        lines.append(f"▸ {s['level']} **{s['name']}** ({s['code']}) | {s['chg']:+.1f}% | 换手{s['turnover']}%")
        for sig in s["signals"]:
            lines.append(f"  {sig}")
        lines.append("")

    msg = "\n".join(lines)
    msg += "⚠️ 脚本自动监控 · 不构成投资建议"

    # 保存文件
    os.makedirs("/home/admin/.openclaw/workspace/mx_data/output", exist_ok=True)
    with open("/home/admin/.openclaw/workspace/mx_data/output/yaogu_signal_latest.txt", "w") as f:
        f.write(msg)

    if verbose:
        print(msg)
        return

    # 推送飞书
    token = get_tenant_token()
    if token:
        ok = send_to_feishu(token, msg)
        print(f"Feishu推送: {'✅成功' if ok else '❌失败'}")
    else:
        print("❌ 获取飞书token失败")

if __name__ == "__main__":
    main(verbose="--v" in sys.argv)
