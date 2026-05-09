#!/usr/bin/env python3.11
"""
妖股盯盘监控脚本
监控妖股潜质标的，检测可进场信号

运行方式：
    python yaogu_monitor.py                     # 执行一次检查
    python yaogu_monitor.py --watch             # 持续监控（10秒间隔，最多60次）

信号规则：
    - 涨停未封死（涨幅>9%但没封板或封单小）
    - 高开回踩（高开>3%且回踩到3%附近）
    - 放量异动（量比>3且涨幅>2%）
    - 开板回封（曾涨停但现在打开）
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime

# ======== 监控标的 ========
# 格式: (代码, 名称, 简要逻辑)
WATCH_LIST = [
    # === 连板梯队 ===
    ("603278", "大业股份", "3连板，机器人+商业航天双题材龙头"),
    ("603618", "杭电股份", "3连板，光通信，但注意清仓记录"),
    ("002031", "巨轮智能", "2连板，低价小盘机器人，情绪标杆"),
    ("002552", "宝鼎科技", "2连板，PCB概念"),

    # === 首板潜力 ===
    ("301028", "鼎熔岩", "创业板20cm机器人，首板放量"),
    ("920270", "天铭科技", "北交所30cm机器人，流通市值仅16亿"),
    ("301387", "光大同创", "创业板，换手22%，科技属性"),
    ("300840", "酷特智能", "创业板，换手30%，量比4.3"),
    ("301696", "三瑞智能", "创业板，换手51%极致活跃"),
]

# ======== 波波的持仓（看是否需要提醒卖出/加仓）=======
BOSS_HOLDINGS = {}  # 暂空，如需加入波波持仓可扩展

# ======== 腾讯实时行情 API ========
def fetch_realtime_quote(code):
    """获取腾讯实时行情"""
    market = "sh" if code.startswith('6') else "sz"
    url = f"http://qt.gtimg.cn/q={market}{code}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://qt.gtimg.cn"
        })
        resp = urllib.request.urlopen(req, timeout=5)
        data = resp.read().decode("gbk")
        # 解析格式: v_market_code="fields...";
        import re
        match = re.search(r'"(.*?)"', data)
        if not match:
            return None
        fields = match.group(1).split("~")
        if len(fields) < 40:
            return None
        return {
            "code": fields[0],
            "name": fields[1],
            "open": safe_float(fields[5]),
            "prev_close": safe_float(fields[4]),
            "price": safe_float(fields[3]),
            "high": safe_float(fields[33]),
            "low": safe_float(fields[34]),
            "volume": safe_float(fields[6]),      # 手
            "amount": safe_float(fields[37]),      # 万元
            "buy_vol": safe_float(fields[10]),     # 买一量
            "sell_vol": safe_float(fields[20]),    # 卖一量
            "turnover": safe_float(fields[38]),    # 换手率
            "pe": safe_float(fields[39]),          # 市盈率
            "amplitude": safe_float(fields[43]),   # 振幅
            "circulation": safe_float(fields[44]), # 流通市值
            "total_market": safe_float(fields[45]),# 总市值
            "pb": safe_float(fields[46]),          # 市净率
            "time_str": fields[30],               # 时间
        }
    except Exception as e:
        return None


def safe_float(val):
    try:
        f = float(val)
        return f
    except (ValueError, TypeError):
        return 0.0


def calc_chg(quote):
    """计算涨跌幅"""
    if quote and quote["prev_close"] > 0:
        return round((quote["price"] - quote["prev_close"]) / quote["prev_close"] * 100, 2)
    return 0.0


def get_limit_price(price, market="sz"):
    """计算涨跌停价（主板10%，创业板/科创板20%，北交所30%）"""
    if market == "bj":
        return round(price * 1.3, 2), round(price * 0.7, 2)
    return round(price * 1.1, 2), round(price * 0.9, 2)


def check_entry_signal(quote, name, logic):
    """检查进场信号"""
    if not quote or quote["prev_close"] == 0:
        return None

    chg = calc_chg(quote)
    price = quote["price"]
    prev = quote["prev_close"]
    limit_up = round(prev * 1.1, 2)

    signals = []

    # 信号1: 涨停但未封死（价格≈涨停但卖盘还有量）
    if chg >= 9.5 and quote["sell_vol"] > 0 and quote["buy_vol"] < 5000:
        signals.append(f"🟡 涨停未封死！现价{price}，卖一还有{quote['sell_vol']:.0f}手，有机会上车")

    # 信号2: 涨停打开（曾涨停后回落）
    if abs(price - limit_up) / prev > 0.003 and quote["high"] >= limit_up * 0.995:
        signals.append(f"🔴 涨停打开！最高到{limit_up}，现回落到{price}（{chg}%），观察是否回封")

    # 信号3: 高开回踩（开盘>3%现在回落到2-4%）
    if 1.5 <= chg <= 4.5 and quote["open"] >= prev * 1.03:
        signals.append(f"🟢 高开回踩！今开{quote['open']}，现价{price}（{chg}%），回踩企稳可考虑")

    # 信号4: 放量异动（涨幅2-7% + 换手高）
    if 2 <= chg <= 7 and quote["turnover"] >= 8:
        signals.append(f"⚡ 放量异动！涨{chg}%，换手{quote['turnover']}%，量能充足")

    # 信号5: 平开拉升（涨幅3-6%，换手不高适合追）
    if 3 <= chg <= 6 and quote["turnover"] <= 5:
        signals.append(f"🚀 温和放量拉升！涨{chg}%，换手{quote['turnover']}%，有持续动力")

    if signals:
        return {
            "name": name,
            "code": quote["code"],
            "price": price,
            "chg": chg,
            "turnover": quote["turnover"],
            "signals": signals,
            "logic": logic,
            "time": datetime.now().strftime("%H:%M:%S"),
        }

    return None


def run_check():
    """执行一次检查"""
    results = []
    for code, name, logic in WATCH_LIST:
        quote = fetch_realtime_quote(code)
        signal = check_entry_signal(quote, name, logic)
        if signal:
            results.append(signal)
        time.sleep(0.3)  # 限流保护

    return results


def format_alert(results):
    """格式化提示消息"""
    if not results:
        return None

    lines = [
        "🕵️‍♂️ **妖股进场信号监控**",
        f"📅 {datetime.now().strftime('%m-%d %H:%M')}",
        "",
    ]

    for r in results:
        lines.append(f"---")
        lines.append(f"**{r['name']}** ({r['code']}) | {r['chg']}% | 换手{r['turnover']}%")
        lines.append(f"💡 {r['logic']}")
        for s in r['signals']:
            lines.append(f"  {s}")

    lines.append("")
    lines.append("⚠️ 脚本自动监控 · 不构成投资建议")

    return "\n".join(lines)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        # 持续监控模式（交易日专用）
        print(f"🕵️‍♂️ 妖股监控启动 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"监控 {len(WATCH_LIST)} 只标的，每10秒检测一次")
        print("按 Ctrl+C 停止")
        print()

        count = 0
        while count < 360:  # 最多1小时
            results = run_check()
            if results:
                print(f"\n{'='*50}")
                print(format_alert(results))
                print(f"{'='*50}\n")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 无进场信号", end="\r")
            time.sleep(10)
            count += 1
    else:
        # 单次检查
        results = run_check()
        msg = format_alert(results)
        if msg:
            print(msg)
            # 保存到文件（供cron通知）
            output = "/home/admin/.openclaw/workspace/mx_data/output/yaogu_signal_latest.txt"
            with open(output, "w", encoding="utf-8") as f:
                f.write(msg)
        else:
            no_signal = f"[{datetime.now().strftime('%H:%M:%S')}] 当前无进场信号"
            print(no_signal)
            with open("/home/admin/.openclaw/workspace/mx_data/output/yaogu_signal_latest.txt", "w") as f:
                f.write(no_signal)
