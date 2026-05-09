#!/usr/bin/env python3.11
"""
早盘强势股推荐脚本
运行时间: 9:25 集合竞价结束后
数据源:
  - mx-xuangu: 智能选股初筛
  - 腾讯API: K线数据（计算BOLL）
策略: 结合BOLL指标 + 量价筛选
"""
import os, sys, json, time, math, urllib.request
from datetime import datetime

# 妙想选股
sys.path.insert(0, '/home/admin/.openclaw/workspace/skills/mx-xuangu')
from mx_xuangu import MXSelectStock

# 资本流工具
sys.path.insert(0, '/home/admin/.openclaw/workspace/daily_stock_analysis')
from capital_flow import get_close_capital_flow, format_combined_report

MX_APIKEY = os.environ.get("MX_APIKEY", "")

def get_market(code):
    return "sh" if code.startswith("6") else "sz"

def fetch_kline_tencent(code, days=30):
    """获取每日K线数据（腾讯API）"""
    mkt = get_market(code)
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,{days},qfq"
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=8).read()
        data = json.loads(raw)
        kd = data.get("data",{}).get(mkt+code,{}).get("day",[]) or data.get("data",{}).get(mkt+code,{}).get("qfqday",[])
        if not kd:
            return []
        closes = []
        for k in kd:
            if len(k) >= 5:
                closes.append({"date":k[0],"close":float(k[2]),"high":float(k[3]),"low":float(k[4])})
        return closes
    except:
        return []

def calc_boll(closes, period=20, multiplier=2):
    """计算BOLL指标"""
    if len(closes) < period:
        return None, None, None
    ma = sum(closes[-period:]) / period
    variance = sum((c - ma)**2 for c in closes[-period:]) / period
    std = math.sqrt(variance)
    upper = ma + multiplier * std
    lower = ma - multiplier * std
    return upper, ma, lower

def calc_boll_signal(kline_data):
    """分析BOLL信号"""
    if len(kline_data) < 21:
        return "数据不足", ""
    
    closes = [k["close"] for k in kline_data]
    current_close = closes[-1]
    
    upper, mid, lower = calc_boll(closes)
    if upper is None:
        return "数据不足", ""
    
    signals = []
    
    # 1. 突破上轨 = 强势启动
    if current_close >= upper:
        signals.append("🚀 突破BOLL上轨，强势启动")
    # 2. 接近上轨 = 强势
    elif current_close >= mid + (upper - mid) * 0.8:
        signals.append("📈 贴近BOLL上轨，强势运行")
    # 3. 回踩中轨企稳 = 买点
    elif abs(current_close - mid) / mid < 0.01:
        signals.append("📊 回踩BOLL中轨，关注企稳")
    # 4. 跌破中轨 = 偏弱
    elif current_close < mid and current_close > lower:
        signals.append("📉 跌破BOLL中轨，偏弱")
    # 5. 触及下轨 = 超跌
    elif current_close <= lower:
        signals.append("🆘 触及BOLL下轨，超跌关注")
    
    # 通道宽度变化
    prev_upper, prev_mid, prev_lower = calc_boll(closes[:-1])
    if prev_upper is not None:
        curr_width = upper - lower
        prev_width = prev_upper - prev_lower
        width_change = (curr_width - prev_width) / prev_width * 100
        
        if width_change < -5:
            signals.append("🔺 通道收窄中，变盘预警")
        elif width_change > 10:
            signals.append("🔻 通道扩张中，趋势加速")
    
    # 价格在BOLL中的位置百分比
    if upper != lower:
        position = (current_close - lower) / (upper - lower) * 100
        signals.append(f"BOLL位置: {position:.0f}%")
    
    return " | ".join(signals), f"UP:{upper:.2f} MID:{mid:.2f} LOW:{lower:.2f}"

def main():
    print(f"🔍 早盘强势股筛选 [{datetime.now().strftime('%H:%M')}]")
    
    if not MX_APIKEY:
        print("❌ MX_APIKEY 未配置，退出")
        return
    
    mx = MXSelectStock()
    
    # ==================== 选股条件 ====================
    # 条件1: 创业板/科创板 活跃股
    queries = [
        "今日涨幅大于1% 小于15% 换手率大于3% 股价5-100元 创业板 的A股 前30",
        "今日涨幅大于1% 小于15% 换手率大于3% 股价5-100元 科创板 的A股 前30",
    ]
    
    all_candidates = []
    for q in queries:
        try:
            print(f"\n📊 查询: {q}")
            result = mx.search(q)
            rows, source, err = mx.extract_data(result)
            if err:
                print(f"  ❌ {err}")
                continue
            
            print(f"  ✅ 返回 {len(rows)} 只（来源: {source}）")
            
            # 统一字段名映射（mx-xuangu字段名可能带日期后缀）
            for r in rows:
                code = str(r.get("代码", "") or "").strip()
                name = str(r.get("名称", "") or "").strip()
                if not code or not name:
                    continue
                
                # 模糊匹配字段名
                def val(key, default="0"):
                    for k, v in r.items():
                        if k and key in k:
                            return v
                    return default
                
                try:
                    price = float(str(val("最新价")).replace(",",""))
                    pct = float(str(val("涨跌幅")).replace("%","").replace(",",""))
                    turnover = float(str(val("换手率")).replace("%","").replace(",",""))
                    vol_ratio = float(str(val("量比")).replace(",",""))
                    amount_raw = str(val("成交额"))
                    if "亿" in amount_raw:
                        amount = float(amount_raw.replace("亿","")) * 100000000
                    elif "万" in amount_raw:
                        amount = float(amount_raw.replace("万","")) * 10000
                    else:
                        amount = float(amount_raw) if amount_raw else 0
                except:
                    continue
                
                mkt_label = "SZ" if not code.startswith("6") else "SH"
                all_candidates.append({
                    "code": code, "name": name, "mkt": mkt_label,
                    "price": price, "pct": pct, "turnover": turnover,
                    "vol_ratio": vol_ratio, "amount": amount,
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"  ❌ 查询失败: {e}")
    
    if not all_candidates:
        print("\n❌ 没有找到符合条件的股票")
        return
    
    # ==================== 去重 ====================
    seen = set()
    deduped = []
    for c in all_candidates:
        if c["code"] not in seen:
            seen.add(c["code"])
            deduped.append(c)
    
    print(f"\n📊 去重后共 {len(deduped)} 只候选股")
    
    # ==================== 获取K线 + BOLL分析 ====================
    results = []
    for i, c in enumerate(deduped):
        code, name = c["code"], c["name"]
        print(f"  [{i+1}/{len(deduped)}] {name}({code})...", end=" ")
        
        kline = fetch_kline_tencent(code, 30)
        if len(kline) < 21:
            print("K线不足")
            continue
        
        signal_str, boll_str = calc_boll_signal(kline)
        print(f"BOLL OK")
        
        results.append({
            **c,
            "boll_signal": signal_str,
            "boll_values": boll_str,
        })
        time.sleep(0.3)
    
    print(f"  \n📊 results长度: {len(results)}, 开始评分")
    if results:
        print(f"    第一只: {json.dumps(results[0], ensure_ascii=False)}")
    # ==================== 排序和筛选 ====================
    # 排序: 换手率优先，结合BOLL位置
    scored = []
    for r in results:
        score = 0
        # 换手率加分
        score += min(float(r["turnover"]) * 2, 30)
        # 量比加分
        score += min(float(r["vol_ratio"]) * 3, 20)
        # 涨幅加分（太大扣分，连板风险高）
        pct = float(r["pct"])
        if 2 <= pct <= 8:
            score += 15
        elif pct > 10:
            score += 5
        # BOLL信号加分
        signal = r.get("boll_signal", "")
        if "突破" in signal:
            score += 25
        elif "贴近" in signal:
            score += 20
        elif "回踩" in signal:
            score += 15
        elif "收窄" in signal:
            score += 10
        elif "触及" in signal or "超跌" in signal:
            score += 8
        r["score"] = score
        scored.append(r)
    
    scored.sort(key=lambda r: r["score"], reverse=True)
    print(f"  \n评分统计: {len(scored)}只有评分，最高{scored[0]['score'] if scored else 0}")
    for s in scored[:5]:
        print(f"    {s['name']}({s['code']}): 评分{s['score']} | BOLL:{s.get('boll_signal','')[:40]}")
    top = scored[:8]
    
    # ==================== 生成报告 ====================
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>早盘强势股推荐 {now[:10]}</title>
<style>
body{{font-family:-apple-system,sans-serif;max-width:900px;margin:20px auto;padding:10px;background:#f5f5f5}}
h1{{color:#1a1a2e;border-bottom:2px solid #e94560;padding-bottom:8px}}
.pick{{background:#fff;border-radius:10px;padding:16px;margin:12px 0;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
.pick h2{{margin:0 0 8px 0;font-size:18px;color:#1a1a2e}}
.pick h2 span{{font-size:13px;color:#888}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;margin:2px;font-weight:bold}}
.tag-red{{background:#ffe0e0;color:#c62828}}
.tag-green{{background:#e0f5e0;color:#2e7d32}}
.tag-blue{{background:#e0e8ff;color:#1565c0}}
.tag-orange{{background:#fff3e0;color:#e65100}}
.stats{{font-size:13px;color:#555;margin:6px 0}}
.boll{{background:#f0f4ff;padding:8px 12px;border-radius:6px;font-size:12px;margin:6px 0;color:#333;border-left:3px solid #1565c0}}
.body-hint{{font-size:11px;color:#888;margin-top:6px}}
.ft{{margin-top:20px;font-size:11px;color:#999;text-align:center}}
</style></head><body>
<h1>🕵️‍♂️ 早盘强势股推荐 <span style="font-size:14px;color:#888;font-weight:normal">{now}</span></h1>
<p style="font-size:13px;color:#666">基于集合竞价+BOLL通道+量价筛选</p>
"""
    
    for i, r in enumerate(top[:5]):
        # 标签
        tags = []
        pct = r["pct"]
        if pct > 5:
            tags.append(f'<span class="tag tag-red">涨幅{pct:+.1f}%</span>')
        elif pct > 2:
            tags.append(f'<span class="tag tag-green">涨幅{pct:+.1f}%</span>')
        tags.append(f'<span class="tag tag-blue">换手{r["turnover"]:.1f}%</span>')
        if r["vol_ratio"] > 3:
            tags.append(f'<span class="tag tag-orange">量比{r["vol_ratio"]:.1f}</span>')
        
        score = r["score"]
        if score >= 60:
            rank_tag = '<span class="tag tag-red" style="font-size:14px">🔥 强烈关注</span>'
        elif score >= 40:
            rank_tag = '<span class="tag tag-green" style="font-size:14px">⭐ 重点关注</span>'
        else:
            rank_tag = '<span class="tag tag-blue" style="font-size:14px">👀 适当关注</span>'
        
        boll = r.get("boll_signal", "")
        boll_v = r.get("boll_values", "")
        
        html += f"""
<div class="pick">
  <h2>#{i+1} {r["name"]} <span>({r["code"]})</span> {rank_tag}</h2>
  <div>{"".join(tags)}</div>
  <div class="stats">价格: {r["price"]:.2f} | 量比: {r["vol_ratio"]:.1f} | 成交额: {r["amount"]/100000000:.1f}亿 | 评分: {score}</div>
  <div class="boll">📊 {boll}</div>
  <div class="body-hint">{boll_v}</div>
</div>
"""
    
    # 备选池
    if len(top) > 5:
        html += '<h2 style="font-size:16px;margin-top:20px">📋 备选池</h2>'
        for r in top[5:]:
            html += f'<div class="pick" style="padding:10px"><strong>{r["name"]}({r["code"]})</strong> ' \
                    f'<span class="tag tag-green">+{r["pct"]:.1f}%</span> ' \
                    f'<span class="tag tag-blue">换手{r["turnover"]:.1f}%</span> ' \
                    f'<span class="stats" style="margin:0">评分{r["score"]}</span> ' \
                    f'<div class="boll" style="margin:4px 0;padding:4px 8px">{r.get("boll_signal","")}</div></div>'
    
    html += f"""
<div class="ft">
<p>🕵️‍♂️ StockHolmes · 早盘强势股 · MX智能选股 + BOLL通道分析</p>
<p style="font-size:10px">⚠️ 仅供参考，不构成投资建议</p>
</div></body></html>
"""
    
    # 保存
    output_dir = "/home/admin/.openclaw/workspace/daily_stock_analysis/output"
    for user_dir in ["boss", "boyfriend"]:
        date_str = datetime.now().strftime("%Y%m%d")
        path = f"{output_dir}/{user_dir}/早盘强势股推荐_{date_str}.html"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(html)
        print(f"\n✅ 报告已保存: {path}")
    
    # 命令行输出
    print("\n" + "="*60)
    print("🔥 早盘强势股 TOP 5")
    print("="*60)
    for i, r in enumerate(top[:5]):
        print(f"\n#{i+1} {r['name']}({r['code']}) | 评分:{r['score']}")
        print(f"   价格:{r['price']:.2f} 涨幅:{r['pct']:+.1f}% 换手:{r['turnover']:.1f}% 量比:{r['vol_ratio']:.1f}")
        print(f"   BOLL: {r.get('boll_signal','')}")
    
    # ==================== 生成文本摘要 ====================
    now_dt = datetime.now()
    date_str = now_dt.strftime("%Y-%m-%d")
    
    for user_key, user_name in [("boss", "邓天天"), ("boyfriend", "波波")]:
        summary_lines = [
            f"🔥 早盘强势股推荐 | {date_str}",
            "─" * 40,
            "🤖 【MX智能选股脚本自动生成 · 非人工推荐】",
            "",
        ]
        for i, r in enumerate(top[:5]):
            pct_str = f"+{r['pct']:.1f}%" if r['pct'] > 0 else f"{r['pct']:.1f}%"
            boll_short = r.get("boll_signal", "").split("|")[0].replace(" 🚀","🚀").strip()
            summary_lines.append(f"#{i+1} {r['name']}({r['code']}) | {r['price']:.2f}({pct_str}) | 评分{r['score']:.0f}")
            summary_lines.append(f"   换手{r['turnover']:.1f}% 量比{r['vol_ratio']:.1f}")
            summary_lines.append(f"   {boll_short}")
            summary_lines.append("")
        
        summary_lines.append("📋 备选池: " + " | ".join([f"{r['name']}({r['code']})" for r in top[5:8]]))
        summary_lines.append("")
        
        # 添加昨日尾盘资金流向
        try:
            capital_inflow = get_close_capital_flow("inflow", 5, "all")
            capital_outflow = get_close_capital_flow("outflow", 5, "all")
            capital_report = format_combined_report(capital_inflow, capital_outflow, "close", 5)
            summary_lines.append("📊 昨日尾盘30分钟主力资金流向:")
            summary_lines.append("─" * 40)
            summary_lines.append("🟢 尾盘净流入TOP5:")
            for r in capital_inflow[:5]:
                summary_lines.append(f"  {r['name']}({r['code']}) +{r['close_net']:.2f}亿")
            summary_lines.append("")
            summary_lines.append("🔴 尾盘净流出TOP5:")
            for r in capital_outflow[:5]:
                summary_lines.append(f"  {r['name']}({r['code']}) {r['close_net']:.2f}亿")
        except Exception as e:
            summary_lines.append(f"📊 尾盘资金流向: 暂时无法获取")
        
        summary_lines.append("")
        summary_lines.append("⚠️ 仅供参考，不构成投资建议")
        summary_lines.append("🕵️‍♂️ StockHolmes · MX智能选股 + BOLL通道分析 + 尾盘资金流")
        
        output_dir_user = f"/home/admin/.openclaw/workspace/daily_stock_analysis/output/{user_key}"
        summary_path = f"{output_dir_user}/早晨推荐_summary_latest.txt"
        os.makedirs(output_dir_user, exist_ok=True)
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("\n".join(summary_lines))
        print(f"✅ 摘要已保存: {summary_path}")
        
        # ========== 飞书推送（波波） ==========
        if user_key == "boyfriend":
            push_feishu("\n".join(summary_lines))
    
    return top[:5]


def push_feishu(text):
    """推送到波波的飞书私聊（通过appId+appSecret获取tenant_token）"""
    try:
        cfg_path = "/home/admin/.openclaw/openclaw.json"
        with open(cfg_path) as f:
            cfg = json.load(f)
        bobo = cfg.get("channels", {}).get("feishu", {}).get("accounts", {}).get("bobo", {})
        app_id = bobo.get("appId", "")
        app_secret = bobo.get("appSecret", "")
        if not app_id or not app_secret:
            print("⚠️ 飞书appId/secret未找到，跳过推送")
            return
        
        # 获取tenant_token
        token_req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
            headers={"Content-Type": "application/json"}
        )
        token_resp = json.loads(urllib.request.urlopen(token_req, timeout=5).read())
        token = token_resp.get("tenant_access_token", "")
        if not token:
            print(f"⚠️ 飞书token获取失败: {token_resp}")
            return
        
        url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = json.dumps({
            "receive_id": "ou_cc19d62ec1cb5c5db18c13bc61efce53",
            "msg_type": "text",
            "content": json.dumps({"text": text})
        })
        req = urllib.request.Request(url, data=body.encode(), headers=headers, method="POST")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if resp.get("code") == 0:
            print(f"✅ 飞书推送成功（波波）")
        else:
            print(f"⚠️ 飞书推送失败: {resp.get('msg','')}")
    except Exception as e:
        print(f"⚠️ 飞书推送异常: {e}")


if __name__ == "__main__":
    main()
