#!/usr/bin/env python3.11
"""
离场位自动计算工具 → 挂载到持仓仪表盘

根据股价走势阶段自动选用不同的离场规则：
  - 贴布林上轨运行 → 布林中轨止盈
  - 趋势震荡期 → 最高收盘价回撤百分比

用法：
    python trailing_stop.py                    # 分析波波持仓
    python trailing_stop.py --user boss        # 分析天天持仓
    python trailing_stop.py sz002192           # 分析指定个股
    python trailing_stop.py --all              # 全量分析
"""

import json
import math
import os
import re
import sys
import time
import urllib.request
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# 用户专属目录 & 数据源
USER_CONFIG = {
    "boyfriend": {
        "portfolio_file": os.path.join(PROJECT_DIR, "output", "portfolio_data.json"),
        "output_dir": os.path.join(PROJECT_DIR, "output", "boyfriend"),
        "label": "波波",
    },
    "boss": {
        "portfolio_file": os.path.join(PROJECT_DIR, "output", "boss", "portfolio_dashboard.json"),
        "output_dir": os.path.join(PROJECT_DIR, "output", "boss"),
        "label": "天天",
    },
}

# 回撤百分比配置（按波动率分级）
VOLATILITY_CONFIG = {
    "high": {"label": "高波动（连板妖股）", "pct": 0.15},   # 妖股
    "medium": {"label": "中波动（题材趋势股）", "pct": 0.10}, # 趋势股
    "low": {"label": "低波动（蓝筹稳健）", "pct": 0.07},     # 稳健股
}


def fetch_boll(code):
    """获取布林线参数"""
    market = "sh" if code.startswith("6") else "sz"
    url = f"http://qt.gtimg.cn/q={market}{code}"
    try:
        raw = urllib.request.urlopen(url, timeout=5).read().decode("gbk")
        m = re.search(r'"(.*?)"', raw)
        if not m:
            return None
        f = m.group(1).split("~")
        if len(f) < 47:
            return None
        return {
            "price": safe_float(f[3]),
            "prev": safe_float(f[4]),
            "high": safe_float(f[33]),
            "low": safe_float(f[34]),
            "amplitude": safe_float(f[43]),
        }
    except:
        return None


def fetch_kline(code, days=30):
    """获取K线数据计算布林"""
    market = "sh" if code.startswith("6") else "sz"
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,,,{days},qfq"
    try:
        raw = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
        data = json.loads(raw)
        d = data.get("data", {}).get(market + code, {})
        # 优先 qfqday（前复权），回退到 day
        bars = d.get("qfqday", d.get("day", []))
        if isinstance(bars, list) and len(bars) > 0:
            closes = [float(x[2]) for x in bars if len(x) >= 3 and safe_float(x[2]) > 0]
            highs = [float(x[1]) for x in bars if len(x) >= 3]
            lows = [float(x[3]) for x in bars if len(x) >= 4]
            return closes, highs, lows
        return None, None, None
    except:
        return None, None, None


def calc_boll(closes, period=20, multiplier=2):
    """计算布林带"""
    if len(closes) < period:
        return None, None, None, None
    ma_20 = sum(closes[-period:]) / period
    variance = sum((c - ma_20) ** 2 for c in closes[-period:]) / period
    std = math.sqrt(variance)
    upper = ma_20 + multiplier * std
    lower = ma_20 - multiplier * std
    return upper, ma_20, lower, std


def calc_atr(closes, highs, lows, period=14):
    """计算ATR"""
    if len(closes) < period:
        return None
    tr_sum = 0
    for i in range(-period, 0):
        if i == -period or i == 0:
            continue
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i-1])
        lc = abs(lows[i] - closes[i-1])
        tr_sum += max(hl, hc, lc)
    return tr_sum / period


def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0


def get_highest_close(code, days=60):
    """获取最近N天的最高收盘价"""
    closes, _, _ = fetch_kline(code, days)
    if not closes or len(closes) == 0:
        return None
    return max(closes)


def determine_volatility(closes):
    """自动判断波动等级"""
    if not closes or len(closes) < 10:
        return "medium"
    # 用最近10日的平均振幅判断
    avg_amp = 0
    for i in range(-10, 0):
        if i < -len(closes):
            continue
        amp = abs(closes[i] - closes[i-1]) / closes[i-1]
        avg_amp += amp
    avg_amp /= 10
    if avg_amp > 0.04:     # 日均振幅>4%
        return "high"
    elif avg_amp > 0.025:  # 日均振幅2.5-4%
        return "medium"
    else:
        return "low"


def analyze_stock(code, name=""):
    """分析一只股票，返回离场建议"""
    # 实时行情
    rt = fetch_boll(code)
    if not rt:
        return None

    # K线
    closes, highs, lows = fetch_kline(code, 30)
    if not closes or len(closes) < 22:
        return None

    # 布林
    upper, mid, lower, std = calc_boll(closes, 20, 2)
    if not upper:
        return None

    price = rt["price"]
    current_chg = round((price - rt["prev"]) / rt["prev"] * 100, 2)

    # ATR
    atr = calc_atr(closes, highs, lows, 14) or std

    # 最高收盘价
    max_close = get_highest_close(code, 60) or price

    # 波动等级
    vol_level = determine_volatility(closes)
    vol_pct = VOLATILITY_CONFIG[vol_level]["pct"]

    # --- 阶段判断 ---
    # 阶段一：股价站在布林上轨上方（≥上轨×0.99）
    on_upper_band = price >= upper * 0.99

    if on_upper_band:
        # 阶段一规则：布林中轨止盈
        exit_level_1 = round(mid, 2)
        exit_label_1 = f"布林中轨({mid:.2f})"
        active_rule = "阶段一（加速期）"
    else:
        exit_level_1 = None
        exit_label_1 = "—"

    # 阶段二规则：最高收盘价回撤百分比
    retrace_level = round(max_close * (1 - vol_pct), 2)
    retrace_label = f"回撤{int(vol_pct*100)}%({retrace_level:.2f})"

    # 综合建议（取对当前更有利/更保守的那个）
    if on_upper_band:
        # 加速期：布林中轨是第一个防线
        suggested = min(exit_level_1, retrace_level) if exit_level_1 else retrace_level
        suggested_reason = f"中轨{exit_level_1} / 回撤{retrace_level} 取低值防风险"
    else:
        suggested = retrace_level
        suggested_reason = f"最高价{max_close:.2f}回撤{int(vol_pct*100)}%"

    # 当前盈亏距离
    drawdown_pct = round((price - suggested) / price * 100, 2) if suggested < price else 0
    peak_dd_pct = round((max_close - suggested) / max_close * 100, 2)

    return {
        "code": code,
        "name": name,
        "price": price,
        "chg": current_chg,
        "phase": "\U0001f680 加速期" if on_upper_band else "\U0001f31f 震荡期",
        "upper_band": round(upper, 2),
        "mid_band": round(mid, 2),
        "atr": round(atr, 2),
        "vol_level": VOLATILITY_CONFIG[vol_level]["label"],
        "max_close": round(max_close, 2),
        "exit_mid": exit_level_1,
        "exit_label_mid": exit_label_1,
        "exit_retrace": retrace_level,
        "exit_label_retrace": retrace_label,
        "suggested_exit": round(suggested, 2),
        "suggested_reason": suggested_reason,
        "potential_slump": f"{drawdown_pct:+.2f}%",
        "peak_slump": f"{peak_dd_pct:+.2f}%",
    }


def format_report(results, user_label):
    """生成文本报告"""
    lines = [
        f"🕵️‍♂️ **{user_label} · 离场位跟踪**",
        f"⏰ {datetime.now().strftime('%m-%d %H:%M')}",
        "",
        "=" * 54,
        " 规则说明",
        "=" * 54,
        " 阶段一（贴布林上轨）：中轨止盈",
        " 阶段二（震荡期）：最高收盘价回撤",
        " 综合建议 = 两者取更保守的离场价",
        "",
    ]

    for r in results:
        lines.append(f"📌 **{r['name']}** ({r['code']}) | {r['chg']:+.1f}% | 现{r['price']}")
        lines.append(f"   阶段：{r['phase']} | 波动：{r['vol_level']}")
        lines.append(f"   布林：上轨{r['upper_band']} | 中轨{r['mid_band']} | ATR{r['atr']}")
        lines.append(f"   阶段一离场：{r['exit_label_mid']}")
        lines.append(f"   阶段二离场：{r['exit_label_retrace']}")
        lines.append(f"   🎯 **建议离场价：{r['suggested_exit']}**")
        lines.append(f"   距当前：{r['potential_slump']} | 距峰值：{r['peak_slump']}")
        lines.append(f"   理由：{r['suggested_reason']}")
        lines.append("")

    lines.append("⚠️ 自动分析 · 不构成投资建议")
    return "\n".join(lines)


def load_portfolio(user="boyfriend"):
    """加载用户持仓"""
    config = USER_CONFIG.get(user)
    if not config:
        return [], ""

    pf = config["portfolio_file"]
    if not os.path.exists(pf):
        return [], ""

    try:
        with open(pf) as f:
            data = json.load(f)

        codes = []

        # portfolio_data.json 格式：{ "results": [{ "code": "603601", "name": "再升科技", ... }] }
        if isinstance(data, dict) and "results" in data:
            items = data["results"]
            for item in items:
                code = re.sub(r"[^0-9]", "", str(item.get("code", "")))
                name = item.get("name", item.get("名称", code))
                if code:
                    codes.append((code, name))
            return codes, config["label"]

        # portfolio_dashboard.json 格式（boss用）
        if isinstance(data, dict):
            items = data.get("stocks", data.get("holdings", []))
        else:
            items = data if isinstance(data, list) else []

        for item in items:
            if isinstance(item, dict):
                raw = item.get("code", item.get("代码", ""))
                code = re.sub(r"[^0-9]", "", str(raw))
                name = item.get("name", item.get("名称", code))
                if code:
                    codes.append((code, name))
        return codes, config["label"]
    except Exception as e:
        print(f"⚠️ 持仓读取失败: {e}")
        return [], ""


def main():
    # 解析参数
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    user = "boyfriend"
    for f in flags:
        if f == "--user":
            idx = sys.argv.index(f)
            if idx + 1 < len(sys.argv):
                user = sys.argv[idx + 1]
        elif f == "--boss":
            user = "boss"

    # 如果传了股票代码，分析指定个股
    codes_to_analyze = []
    name_map = {}
    for arg in args:
        code = re.sub(r"[^0-9]", "", arg)
        if code:
            codes_to_analyze.append(code)

    if not codes_to_analyze:
        # 从持仓读取
        codes_info, user_label = load_portfolio(user)
        if not codes_info:
            print("❌ 没有找到持仓数据，请传股票代码")
            sys.exit(1)
        codes_to_analyze = [c[0] for c in codes_info]
        name_map = dict(codes_info)
    else:
        user_label = USER_CONFIG[user]["label"]

    results = []
    for code in codes_to_analyze:
        name = name_map.get(code, code)
        r = analyze_stock(code, name)
        if r:
            results.append(r)
        time.sleep(0.3)

    results.sort(key=lambda x: x["suggested_exit"], reverse=True)

    # 生成报告
    report = format_report(results, user_label)
    print(report)

    # 保存文件
    out_dir = USER_CONFIG[user]["output_dir"]
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "trailing_stop_latest.txt")
    with open(path, "w") as f:
        f.write(report)
    print(f"\n✅ 已保存到: {path}")

    # 也输出JSON
    json_path = os.path.join(out_dir, "trailing_stop_data.json")
    with open(json_path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
