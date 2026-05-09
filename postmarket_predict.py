#!/usr/bin/env python3.11
"""盘后复盘 & 次日预测报告（15:30收盘后生成）"""
import urllib.request, json, math, time, os, sys, requests, pywencai
import pandas as pd

# mx-data: 东方财富妙想金融数据（主数据源）
sys.path.insert(0, '/home/admin/.openclaw/workspace/skills/mx-data')
sys.path.insert(0, '/home/admin/.openclaw/workspace/daily_stock_analysis')
try:
    from mx_data import MXData
    mx_data_available = True
    mx_data_instance = MXData()
except Exception:
    mx_data_available = False
    mx_data_instance = None
try:
    from capital_flow import get_close_capital_flow, format_capital_report
    capital_flow_available = True
except Exception:
    capital_flow_available = False
from datetime import datetime, timedelta

def run_for_user(user_key):
    """user_key: 'boss' or 'boyfriend'"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    
    # 读取持仓数据
    if user_key == "boss":
        data_file = "output/boss/portfolio_dashboard.json"
    else:
        data_file = "output/portfolio_data.json"
    
    try:
        with open(data_file) as f:
            data = json.load(f)
    except Exception as e:
        print(f"[{user_key}] 读取持仓失败: {e}")
        return None
    
    results = data.get("results", [])
    if not results:
        print(f"[{user_key}] 无持仓数据")
        return None
    
    stock_map = {}
    for s in results:
        stock_map[s["code"]] = s
    
    # 腾讯行情
    codes_tencent = []
    for s in results:
        c = s["code"]
        mkt = "sh" if c.startswith("6") else "sz"
        codes_tencent.append(mkt + c)
    
    url = "https://qt.gtimg.cn/q=" + ",".join(codes_tencent)
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=10
        ).read()
    except:
        print(f"[{user_key}] 腾讯行情获取失败")
        return None
    
    tencent_data = {}
    for line in raw.decode("gbk").split(";"):
        if "~" not in line: continue
        p = line.split("~")
        if len(p) < 40: continue
        tencent_data[p[2][-6:]] = {
            "price":float(p[3]),"pct":float(p[32]),"pre":float(p[4]),
            "high":float(p[33]),"low":float(p[34]),
            "turnover":float(p[38]) if len(p)>38 and p[38] else 0,
            "vol":float(p[37]) if len(p)>37 and p[37] else 0,
            "amount_wan":float(p[36]) if len(p)>36 and p[36] else 0
        }
    
    # 大盘指数
    market_indices = {}
    idx_codes = [('sh000001','上证指数'),('sz399001','深证成指'),('sz399006','创业板指'),('sh000688','科创50')]
    idx_url = "https://qt.gtimg.cn/q=" + ",".join([c[0] for c in idx_codes])
    try:
        idx_raw = urllib.request.urlopen(
            urllib.request.Request(idx_url, headers={"User-Agent":"Mozilla/5.0"}), timeout=8
        ).read()
        for line in idx_raw.decode("gbk").split(";"):
            if "~" not in line: continue
            p = line.split("~")
            if len(p) < 40: continue
            for ic, iname in idx_codes:
                if p[2].endswith(ic[2:]):
                    market_indices[iname] = {"price":float(p[3]),"pct":float(p[32])}
    except:
        pass
    
    # 资金流（mx-data 主 + pywencai 备选）
    flow_map = {}
    
    def parse_money_str(s):
        s = str(s).strip()
        if not s or s == '0' or s == '--': return 0.0
        sign = -1 if s.startswith('-') else 1
        s = s.lstrip('-')
        try:
            if '亿' in s: return sign * float(s.replace('亿','').replace('元','')) * 1e8
            elif '万' in s: return sign * float(s.replace('万','').replace('元','')) * 1e4
            else: return sign * float(s.replace('元',''))
        except: return 0.0
    
    for code in stock_map:
        sname = stock_map[code]["name"]
        mkt = "sz" if code.startswith(("0","3")) else "sh"
        full_code = mkt + code
        
        main_net = super_large = large_net = 0
        source_used = ""
        
        # 1️⃣ mx-data
        if mx_data_available and mx_data_instance:
            try:
                result = mx_data_instance.query(f'{sname} 主力资金流向')
                if result:
                    table = result['data']['data']['searchDataResultDTO']['dataTableDTOList'][0]['table']
                    main_net = parse_money_str(table.get('f62', ['0'])[0])
                    super_large = parse_money_str(table.get('f78', ['0'])[0])
                    large_net = parse_money_str(table.get('f72', ['0'])[0])
                    if abs(main_net) > 0 or abs(super_large) > 0:
                        source_used = "mx-data"
            except:
                pass
        
        # 2️⃣ pywencai 备选
        if not source_used:
            try:
                result = pywencai.get(query=f'{full_code} 资金流向 主力净流入 特大单 大单', query_type='stock', perpage=1)
                tbl = result.get('tableV1')
                if tbl is not None and hasattr(tbl, 'to_dict'):
                    rows = tbl.to_dict('records')
                    if rows:
                        row = rows[0]
                        main_net = float(row.get('资金流向', 0) or 0)
                        super_large = float(row.get('特大单净额', 0) or 0)
                        large_net = float(row.get('dde大单净额', 0) or 0)
                        source_used = "pywencai"
            except:
                pass
            time.sleep(0.3)
        
        flow_map[code] = {"f62": main_net, "f78": super_large, "f72": large_net, "data_source": source_used}
    
    # 新闻
    news_data = {}
    for code in stock_map:
        try:
            mkt = "sz" if code.startswith(("0","3")) else "sh"
            full_code = mkt + code
            result = pywencai.get(query=f'{full_code} 最新消息 新闻', query_type='stock', perpage=1)
            news_list = result.get('news_list1', [])
            if news_list and isinstance(news_list, list):
                items = []
                for n in news_list[:3]:
                    if not isinstance(n, dict): continue
                    dv = n.get('date', {})
                    tv = n.get('title', {})
                    sv = n.get('source', {})
                    lv = n.get('show_detail', {})
                    items.append({
                        "date": dv.get("value", "") if isinstance(dv, dict) else str(dv),
                        "title": tv.get("value", "") if isinstance(tv, dict) else str(tv),
                        "source": sv.get("value", "") if isinstance(sv, dict) else str(sv),
                        "url": lv.get("value", "") if isinstance(lv, dict) else str(lv)
                    })
                news_data[code] = items
            time.sleep(0.2)
        except:
            pass
    
    # 两融
    margin_data = {}
    for code in stock_map:
        try:
            mkt = "sz" if code.startswith(("0","3")) else "sh"
            full_code = mkt + code
            result = pywencai.get(query=f'{full_code} 融资融券 融资余额', query_type='stock', perpage=1)
            tbl = result.get('tableV1')
            if tbl is not None and hasattr(tbl, 'to_dict'):
                rows = tbl.to_dict('records')
                if rows:
                    r = rows[0]
                    margin_data[code] = {
                        "融资余额": r.get("融资余额", 0),
                        "融资余额增速": r.get("融资余额增速", 0),
                        "融券余额": r.get("融券余额", 0),
                    }
            time.sleep(0.3)
        except:
            pass
    
    # 模式识别
    pattern_data = {}
    today = datetime.now()
    date_90d = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    
    for code in stock_map:
        try:
            mkt = "sh" if code.startswith("6") else "sz"
            url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,{date_90d},{today_str},120,qfq'
            raw = json.loads(urllib.request.urlopen(url, timeout=5).read())
            kd = raw.get('data',{})
            if not kd or isinstance(kd, list): continue
            stock_data = kd.get(f'{mkt}{code}', {})
            if not stock_data: continue
            days = stock_data.get('qfqday', [])
            if not days or len(days) < 30: continue
            
            closes = [float(d[2]) for d in days]
            
            def calc_rsi(cl, period=14):
                if len(cl) < period+1: return 50
                gains, losses = [], []
                for i in range(1, len(cl)):
                    ch = cl[i] - cl[i-1]
                    gains.append(max(ch, 0))
                    losses.append(max(-ch, 0))
                ag = sum(gains[-period:])/period
                al = sum(losses[-period:])/period
                if al == 0: return 100
                return 100 - 100/(1+ag/al)
            
            def calc_ma(data, period):
                if len(data) < period: return data[-1]
                return sum(data[-period:])/period
            
            ma5 = calc_ma(closes, 5)
            ma10 = calc_ma(closes, 10)
            ma20 = calc_ma(closes, 20)
            cur_price = closes[-1]
            cur_rsi = calc_rsi(closes)
            
            cur_rsi_zone = '超买' if cur_rsi > 70 else ('超卖' if cur_rsi < 30 else '中性')
            cur_trend = '上升' if cur_price > ma20 else '下降'
            cur_macd = '金叉' if ma5 > ma10 else '死叉'
            
            similar_returns_5d = []
            similar_returns_10d = []
            for idx in range(20, len(closes)-11):
                h_rsi = calc_rsi(closes[:idx+1])
                h_ma5 = calc_ma(closes[:idx+1], 5)
                h_ma10 = calc_ma(closes[:idx+1], 10)
                h_ma20 = calc_ma(closes[:idx+1], 20)
                h_price = closes[idx]
                
                h_rsi_zone = '超买' if h_rsi > 70 else ('超卖' if h_rsi < 30 else '中性')
                h_trend = '上升' if h_price > h_ma20 else '下降'
                h_macd = '金叉' if h_ma5 > h_ma10 else '死叉'
                
                if h_rsi_zone == cur_rsi_zone and h_trend == cur_trend and h_macd == cur_macd:
                    ret_5 = (closes[idx+5] - closes[idx]) / closes[idx] * 100
                    ret_10 = (closes[idx+10] - closes[idx]) / closes[idx] * 100
                    similar_returns_5d.append(ret_5)
                    similar_returns_10d.append(ret_10)
            
            if len(similar_returns_5d) < 3:
                for idx in range(20, len(closes)-11):
                    h_rsi = calc_rsi(closes[:idx+1])
                    h_price = closes[idx]
                    h_ma20 = calc_ma(closes[:idx+1], 20)
                    h_rsi_zone = '超买' if h_rsi > 70 else ('超卖' if h_rsi < 30 else '中性')
                    h_trend = '上升' if h_price > h_ma20 else '下降'
                    if h_rsi_zone == cur_rsi_zone and h_trend == cur_trend:
                        ret_5 = (closes[idx+5] - closes[idx]) / closes[idx] * 100
                        ret_10 = (closes[idx+10] - closes[idx]) / closes[idx] * 100
                        similar_returns_5d.append(ret_5)
                        similar_returns_10d.append(ret_10)
            
            if similar_returns_5d:
                avg_5 = sum(similar_returns_5d) / len(similar_returns_5d)
                avg_10 = sum(similar_returns_10d) / len(similar_returns_10d)
                win_5 = sum(1 for r in similar_returns_5d if r > 0) / len(similar_returns_5d) * 100
                win_10 = sum(1 for r in similar_returns_10d if r > 0) / len(similar_returns_10d) * 100
                pattern_data[code] = {
                    "rsi": round(cur_rsi, 1), "rsi_zone": cur_rsi_zone,
                    "trend": cur_trend, "macd": cur_macd,
                    "sample_5d": len(similar_returns_5d), "avg_5d": round(avg_5, 2), "win_5d": round(win_5, 1),
                    "sample_10d": len(similar_returns_10d), "avg_10d": round(avg_10, 2), "win_10d": round(win_10, 1),
                }
            time.sleep(0.2)
        except:
            pass
    
    # AI逐只预测
    print(f"[{user_key}] AI预测...")
    predictions = {}
    sd = ""
    for i, (code, s) in enumerate(stock_map.items()):
        tq = tencent_data.get(code, {})
        fl = flow_map.get(code, {})
        pd_data = pattern_data.get(code, {})
        sd += f"{i+1}. {s['name']}({code}) 现价{tq.get('price',0):.2f}({tq.get('pct',0):+.1f}%) 盈亏{s.get('pnl_pct', s.get('last_pnl',0)):+.1f}% "
        sd += f"RSI{pd_data.get('rsi',50)} {pd_data.get('rsi_zone','')} {pd_data.get('trend','')} {pd_data.get('macd','')} "
        sd += f"主力{fl.get('f62',0)/1e4:+.0f}万 "
        nl = news_data.get(code, [])
        if nl:
            sd += f"新闻:{nl[0]['title'][:20]} "
        sd += "\n"
    
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Content-Type":"application/json","Authorization":"Bearer sk-c6e0a0f9b7554680b1c4d81e2e5324e2"},
            json={
                "model":"deepseek-v4-flash",
                "messages":[
                    {"role":"system","content":"A股收盘复盘分析师。根据收盘数据给出次日预测。输出JSON数组。"},
                    {"role":"user","content":f"持仓数据：\n{sd}\n\n返回JSON：[{{\"name\":\"股票名\",\"predict\":\"看涨/看平/看跌\",\"confidence\":1-100,\"reason\":\"30字以内预测理由\",\"target_high\":\"明日目标高价\",\"target_low\":\"明日目标低价\",\"support\":\"关键支撑位\",\"action\":\"操作建议：持有/加仓/减仓/卖出/观望\"}}]\n按顺序，只返回JSON。"}
                ],
                "temperature":0.3,"max_tokens":3000
            },
            timeout=120
        )
        content = resp.json().get("choices",[{}])[0].get("message",{}).get("content","").strip()
        if content.startswith("```"):
            parts=content.split("```")
            content=parts[1] if len(parts)>1 else content
            if content.startswith("json"): content=content[4:]
        predictions = json.loads(content)
        print(f"  AI预测完成: {len(predictions)}只")
    except Exception as e:
        print(f"  AI预测失败: {e}")
        predictions = []
    
    # 构建报告数据
    results_with_data = []
    for s in results:
        code = s["code"]
        tq = tencent_data.get(code, {})
        fl = flow_map.get(code, {})
        pd_data = pattern_data.get(code, {})
        nl = news_data.get(code, [])
        md = margin_data.get(code, {})
        pred = None
        for p in predictions:
            if p.get("name","") == s["name"]:
                pred = p
                break
        
        results_with_data.append({
            "name": s["name"], "code": code,
            "sector": s.get("sector", ""),
            "price": tq.get("price", 0), "pct": tq.get("pct", 0),
            "cost": s.get("cost", 0), "pnl_pct": s.get("pnl_pct", s.get("last_pnl", 0)),
            "turnover": tq.get("turnover", 0),
            "f62": fl.get("f62", 0),
            "rsi": pd_data.get("rsi", 50), "rsi_zone": pd_data.get("rsi_zone", ""),
            "trend": pd_data.get("trend", ""), "macd": pd_data.get("macd", ""),
            "pattern": pd_data, "news": nl, "margin": md, "prediction": pred,
        })
    
    # 生成HTML
    H = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    user_label = "邓天天" if user_key == "boss" else "波波"
    
    H.append('<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    H.append('<title>盘后预测 - ' + user_label + '</title>')
    H.append('<style>')
    H.append('* {margin:0;padding:0;box-sizing:border-box}')
    H.append('body {font-family:-apple-system,"Microsoft YaHei","PingFang SC",sans-serif;background:#f0f2f5;color:#333;padding:12px;font-size:13px}')
    H.append('.header {background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;border-radius:8px;padding:14px 18px;margin-bottom:12px}')
    H.append('.header h1 {font-size:17px;margin-bottom:4px}')
    H.append('.section {background:#fff;border-radius:8px;padding:14px;margin-bottom:12px}')
    H.append('.section h2 {font-size:15px;margin-bottom:10px;padding-bottom:6px;border-bottom:2px solid #e0e0e0}')
    H.append('.stk {background:#fafafa;border-radius:6px;padding:10px;margin-bottom:8px;border-left:3px solid #ddd}')
    H.append('.red {color:#c62828;font-weight:bold}')
    H.append('.green {color:#2e7d32;font-weight:bold}')
    H.append('.tag {display:inline-block;padding:1px 5px;border-radius:3px;font-size:11px}')
    H.append('.tb {background:#e3f2fd;color:#1565c0}')
    H.append('table {width:100%;border-collapse:collapse;font-size:12px}')
    H.append('th {background:#f5f5f5;padding:6px 5px;text-align:left}td {padding:6px 5px;border-bottom:1px solid #f0f0f0}')
    H.append('.pred-box {border-radius:4px;padding:6px 10px;margin-top:6px;font-weight:bold;font-size:13px}')
    H.append('.ft {text-align:center;padding:12px;color:#999;font-size:11px}')
    H.append('</style></head><body>')
    H.append('<div style="max-width:1200px;margin:0 auto">')
    
    # 头部
    H.append('<div class="header">')
    H.append('<h1>📊 盘后复盘 & 次日预测</h1>')
    H.append('<p>' + user_label + ' · 生成: ' + now + '</p>')
    H.append('</div>')
    
    # 大盘
    if market_indices:
        H.append('<div class="section"><h2>📈 今日大盘</h2><div style="display:flex;gap:12px;flex-wrap:wrap">')
        for iname, idata in market_indices.items():
            ic = "red" if idata["pct"] >= 0 else "green"
            H.append('<div style="flex:1;min-width:120px;background:#f8f9fa;border-radius:6px;padding:10px;text-align:center">')
            H.append('<div style="font-size:14px;font-weight:bold">' + iname + '</div>')
            H.append('<div class="' + ic + '" style="font-size:18px;font-weight:bold">' + "{:+.2f}".format(idata["pct"]) + '%</div>')
            H.append('<div style="font-size:12px;color:#888">' + "{:.2f}".format(idata["price"]) + '</div>')
            H.append('</div>')
        H.append('</div></div>')
    
    # 持仓概览
    profit = sum(r.get("pnl_pct", 0) * 1000 for r in results_with_data)
    up_c = sum(1 for r in results_with_data if r["pct"] > 0)
    dn_c = sum(1 for r in results_with_data if r["pct"] < 0)
    H.append('<div class="section"><h2>📋 持仓概览</h2>')
    H.append('<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">')
    H.append(f'<div style="text-align:center"><div style="font-size:20px;font-weight:bold">{len(results_with_data)}</div><div style="color:#888;font-size:11px">持仓数</div></div>')
    H.append(f'<div style="text-align:center"><div class="red" style="font-size:20px;font-weight:bold">{up_c}</div><div style="color:#888;font-size:11px">上涨</div></div>')
    H.append(f'<div style="text-align:center"><div class="green" style="font-size:20px;font-weight:bold">{dn_c}</div><div style="color:#888;font-size:11px">下跌</div></div>')
    profit_cls = "red" if profit>=0 else "green"
    H.append(f'<div style="text-align:center"><div class="{profit_cls}" style="font-size:20px;font-weight:bold">{profit:+.0f}</div><div style="color:#888;font-size:11px">总盈亏</div></div>')
    H.append('</div></div>')
    
    # 逐只分析
    H.append('<div class="section"><h2>🔍 逐股复盘 & 预测</h2>')
    H.append('<div style="margin-bottom:12px;font-size:11px;color:#999">📋 数据来源标注: <span style="display:inline-block;padding:1px 6px;border-radius:3px;background:#e8f5e9;color:#2e7d32">硬数据</span> 公式计算/交易所官方 | <span style="display:inline-block;padding:1px 6px;border-radius:3px;background:#fff3e0;color:#e65100">软参考</span> 统计估算/仅供参考 | <span style="display:inline-block;padding:1px 6px;border-radius:3px;background:#f3e5f5;color:#7b1fa2">AI分析</span> 大模型推理</div>')
    for r in results_with_data:
        fc = "red" if r["pct"] > 0 else ("green" if r["pct"] < 0 else "gray")
        pc = "red" if r["pnl_pct"] >= 0 else "green"
        
        H.append('<div class="stk">')
        H.append(f'<div style="font-size:14px;font-weight:bold">{r["name"]} <span style="font-size:11px;color:#888">({r["code"]})</span>')
        if r["sector"]: H.append(f' ·{r["sector"]}')
        H.append('</div>')
        H.append(f'<div><span class="{fc}" style="font-size:14px">{r["pct"]:+.2f}%</span>')
        H.append(f' <span class="{pc}" style="font-size:12px;margin-left:6px">盈亏{r["pnl_pct"]:+.1f}%</span></div>')
        
        # 技术指标
        rsi_c = "red" if r["rsi"] > 70 else ("green" if r["rsi"] < 30 else "")
        H.append(f'<div style="font-size:11px;color:#666;margin-top:4px"><span style="display:inline-block;padding:1px 4px;border-radius:2px;background:#e8f5e9;color:#2e7d32;font-size:9px;margin-right:3px">硬</span>RSI:{r["rsi"]}')
        if r["rsi_zone"]: H.append(f' <span class="{rsi_c}">({r["rsi_zone"]})</span>')
        if r["trend"]: H.append(f' {r["trend"]} {r["macd"]}')
        H.append(f' | 换手:{r["turnover"]:.1f}%</div>')
        
        # 资金流
        if r["f62"] != 0:
            fl_c = "red" if r["f62"] > 0 else "green"
            H.append(f'<div style="font-size:11px;color:#666"><span style="display:inline-block;padding:1px 4px;border-radius:2px;background:#fff3e0;color:#e65100;font-size:9px;margin-right:3px">软</span>主力净流: <span class="{fl_c}">{r["f62"]/1e4:+.0f}万</span></div>')
        
        # 新闻
        if r["news"]:
            H.append('<div style="margin-top:4px;font-size:11px;color:#888">📰 新闻: ' + r["news"][0]["title"][:40])
            if len(r["news"][0]["title"]) > 40: H.append('...')
            H.append('</div>')
        
        # 两融
        if r["margin"]:
            md = r["margin"]
            growth = md.get("融资余额增速", 0)
            gc = "red" if growth > 0 else "green"
            H.append(f'<div style="font-size:11px;color:#888"><span style="display:inline-block;padding:1px 4px;border-radius:2px;background:#e8f5e9;color:#2e7d32;font-size:9px;margin-right:3px">硬</span>融资:{md.get("融资余额",0)/1e8:.1f}亿 增速<span class="{gc}">{growth:+.2f}%</span></div>')
        
        # 模式识别
        pd_data = r.get("pattern", {})
        if pd_data:
            w5 = pd_data.get("win_5d", 50)
            s5 = pd_data.get("sample_5d", 0)
            w5c = "red" if w5 >= 60 else ("green" if w5 <= 40 else "")
            # 模式识别判断提示
            if s5 >= 5:
                if w5 >= 75: hint = '→ 🔺历史偏向利好'
                elif w5 >= 60: hint = '→ 轻微利好'
                elif w5 <= 25: hint = '→ 🔻历史偏向利空'
                elif w5 <= 40: hint = '→ 轻微利空'
                else: hint = '→ 历史无明显偏向'
            elif s5 >= 3:
                if w5 >= 80: hint = '→ 可能利好（样本偏少）'
                elif w5 <= 20: hint = '→ 可能利空（样本偏少）'
                else: hint = '→ 样本偏少，参考有限'
            else:
                hint = '→ 样本不足'
            H.append(f'<div style="font-size:11px;color:#888"><span style="display:inline-block;padding:1px 4px;border-radius:2px;background:#fff3e0;color:#e65100;font-size:9px;margin-right:3px">软</span>历史{s5}次相似 | 5日胜率<span class="{w5c}">{w5:.0f}%</span> <span style="color:#999">{hint}</span></div>')
        
        # AI预测
        pred = r.get("prediction")
        if pred:
            pred_c = {"看涨":"#c62828","看平":"#e65100","看跌":"#2e7d32"}.get(pred.get("predict",""),"")
            bg_c = {"看涨":"#ffebee","看平":"#fff3e0","看跌":"#e8f5e9"}.get(pred.get("predict",""),"#f5f5f5")
            H.append(f'<div class="pred-box" style="background:{bg_c};border-left:3px solid {pred_c};color:{pred_c}">')
            H.append(f'🎯 <span style="display:inline-block;padding:1px 5px;border-radius:2px;background:#f3e5f5;color:#7b1fa2;font-size:9px;margin-right:3px">AI</span>明日{pred.get("predict","—")} (信心{pred.get("confidence",0)})')
            H.append(f'<div style="font-weight:normal;font-size:12px;color:#333;margin-top:2px">{pred.get("reason","")}</div>')
            if pred.get("action"):
                H.append(f'<div style="font-weight:normal;font-size:11px;margin-top:2px">建议: {pred.get("action")}</div>')
            H.append('</div>')
        
        H.append('</div>')
    
    H.append('</div>')
    H.append('<div class="ft"><p>⚠️ 仅供参考，不构成投资建议。股市有风险，投资需谨慎。</p></div>')
    H.append('</div></body></html>')
    
    full = "\n".join(H)
    
    # 保存到用户专属目录
    if user_key == "boss":
        out_dir = "output/boss"
    else:
        out_dir = "output/boyfriend"
    
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    fn = f"盘后预测_{ts}.html"
    fp = os.path.join(out_dir, fn)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(full)
    with open(os.path.join(out_dir, "盘后预测_最新.html"), "w", encoding="utf-8") as f:
        f.write(full)
    
    print(f"[{user_key}] ✅ 盘后预测: {fp} ({len(full)} bytes)")
    
    # 生成摘要文本（用于飞书推送）
    report_link = "boss" if user_key == "boss" else "boyfriend"
    link_key = "tiantian_reports_8k3m" if user_key == "boss" else "bobo_reports_9x7n"
    summary_lines = [f"📊 盘后复盘 & 次日预测 - {user_label}", f"生成时间: {now}", ""]
    
    # 大盘摘要
    if market_indices:
        summary_lines.append("📈 大盘收盘:")
        for iname, idata in market_indices.items():
            pct_str = f"{idata['pct']:+.2f}%"
            summary_lines.append(f"  {iname} {pct_str}")
        summary_lines.append("")
    
    # 持仓概览
    summary_lines.append(f"📋 持仓: {len(results_with_data)}只 | 上涨{up_c} 下跌{dn_c}")
    summary_lines.append("")
    
    # 逐股预测摘要
    summary_lines.append("🎯 明日预测:")
    for r in results_with_data:
        pred = r.get("prediction")
        if pred:
            name = r["name"]
            predict = pred.get("predict", "?")
            reason = pred.get("reason", "")
            action = pred.get("action", "")
            summary_lines.append(f"  {name}: {predict} — {reason}")
            if action:
                summary_lines.append(f"    建议: {action}")
        else:
            summary_lines.append(f"  {r['name']}: 无预测")
    
    summary_lines.append("")
    summary_lines.append(f"🔗 完整报告: http://47.116.23.182:8081/{link_key}/盘后预测_最新.html")
    summary_lines.append("")
    summary_lines.append("⚠️ 仅供参考，不构成投资建议。股市有风险，投资需谨慎。")
    
    summary_text = "\n".join(summary_lines)
    summary_fp = os.path.join(out_dir, "盘后预测_摘要.txt")
    with open(summary_fp, "w", encoding="utf-8") as f:
        f.write(summary_text)
    
    # 打印摘要（供cron推送使用）
    print("\n---SUMMARY_START---")
    print(summary_text)
    print("---SUMMARY_END---")
    
    return fp

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        user_key = sys.argv[1]
        run_for_user(user_key)
    else:
        run_for_user("boss")
        run_for_user("boyfriend")
