#!/usr/bin/env python3.11
"""
资本流（Capital Flow）工具模块
基于 mx-xuangu 提供尾盘/全天主力资金流向查询

典型用法:
    from capital_flow import get_close_capital_flow, get_full_day_capital_flow

    # 尾盘30分钟主力净流入TOP10
    df = get_close_capital_flow(limit=10, market="all")

    # 全天主力净流入TOP10（含行业过滤）
    df = get_full_day_capital_flow(limit=10, sector="半导体")

    # 生成资金流向文本报告
    txt = format_capital_report(df, title="尾盘主力资金流入TOP10")
"""
import os, sys, json, time
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

sys.path.insert(0, '/home/admin/.openclaw/workspace/skills/mx-xuangu')
from mx_xuangu import MXSelectStock

# 全局对象（延迟初始化）
_mx: Optional[MXSelectStock] = None

def _get_mx() -> MXSelectStock:
    global _mx
    if _mx is None:
        _mx = MXSelectStock()
    return _mx

def _gv(row: Dict, hint: str, default="0") -> str:
    """模糊匹配字段值"""
    for k, v in row.items():
        if k and hint in k:
            return str(v) if v is not None else default
    return default

def _parse_float(val) -> float:
    """安全转float"""
    if val is None:
        return 0.0
    s = str(val)
    # 处理 "1.39亿" "12.04%" "-2.975亿元" 等
    mul = 1
    if "亿" in s:
        mul = 100000000
    elif "万" in s:
        mul = 10000
    try:
        return float(s.replace(",","").replace("%","").replace("亿元","").replace("亿","").replace("万元","").replace("万","")) * mul
    except:
        return 0.0

def _fmt_money(val) -> str:
    """格式化金额"""
    if val >= 100000000:
        return f"{val/100000000:.2f}亿"
    if val >= 10000:
        return f"{val/10000:.1f}万"
    return f"{val:.0f}元"

# ---------- 尾盘主力资金流向 ----------

def get_close_capital_flow(
    direction: str = "inflow",
    limit: int = 20,
    market: str = "创业板",
    extra_conditions: str = "",
) -> List[Dict[str, Any]]:
    """
    获取尾盘（14:30-15:00）主力资金流向排名
    
    Args:
        direction: "inflow"=净流入TOP, "outflow"=净流出TOP
        limit: 返回多少只
        market: "all"="A股", "创业板", "科创板", "主板"
        extra_conditions: 额外筛选条件（如"换手率大于3% 股价小于50元"）
    
    Returns:
        [{"code","name","price","pct","turnover","close_net","close_net_raw","score"}]
    """
    query_parts = []
    if direction == "inflow":
        query_parts.append("尾盘主力净流入大于0")
    else:
        query_parts.append("尾盘主力净流出小于0")
    
    if market and market != "all":
        query_parts.append(market)
    if extra_conditions:
        query_parts.append(extra_conditions)
    
    query_parts.append(f"前{limit}")
    query = " ".join(query_parts)
    
    result = _get_mx().search(query)
    rows, source, err = _get_mx().extract_data(result)
    if err or not rows:
        print(f"[capital_flow] ❌ mx-xuangu查询失败: {err or '空结果'}")
        return []
    
    # 找到尾盘主力净额字段
    close_net_key = None
    for k in rows[0].keys():
        if "1分钟线主力净额合计" in k or "尾盘主力净额" in k:
            close_net_key = k
            break
    if not close_net_key:
        # 回退到主力净额字段
        for k in rows[0].keys():
            if "主力净额" in k:
                close_net_key = k
                break
    
    print(f"[capital_flow] ✅ {len(rows)}条, 资金字段: {close_net_key}")
    
    results = []
    for r in rows:
        code = str(r.get("代码", "") or "").strip()
        name = str(r.get("名称", "") or "").strip()
        if not code or not name:
            continue
        
        close_net = _parse_float(r.get(close_net_key or "", 0))
        if direction == "outflow" and close_net > 0:
            close_net = -close_net  # 流出为负
        
        results.append({
            "code": code,
            "name": name,
            "price": _parse_float(_gv(r, "最新价")),
            "pct": _parse_float(_gv(r, "涨跌幅")),
            "turnover": _parse_float(_gv(r, "换手率")),
            "vol_ratio": _parse_float(_gv(r, "量比")),
            "amount": _parse_float(_gv(r, "成交额")),
            "close_net": close_net / 100000000,  # 转亿
            "close_net_raw": close_net,
            "pe": _parse_float(_gv(r, "市盈率")),
            "pb": _parse_float(_gv(r, "市净率")),
        })
    
    # 按尾盘净额排序
    results.sort(key=lambda r: abs(r["close_net"]), reverse=True)
    return results[:limit]


# ---------- 全天主力资金流向 ----------

def get_full_day_capital_flow(
    direction: str = "inflow",
    limit: int = 20,
    sector: str = "",
    extra_conditions: str = "",
) -> List[Dict[str, Any]]:
    """
    获取全天主力资金流向排名
    
    Args:
        direction: "inflow"=净流入TOP, "outflow"=净流出TOP
        limit: 多少只
        sector: 板块过滤（如"半导体"）
        extra_conditions: 额外条件
    
    Returns:
        [{"code","name","price","pct","turnover","main_net","main_net_raw",...}]
    """
    query_parts = []
    if direction == "inflow":
        query_parts.append("主力资金净流入排名前")
    else:
        query_parts.append("主力资金净流出排名前")
    
    if sector:
        query_parts.append(sector)
    if extra_conditions:
        query_parts.append(extra_conditions)
    
    query_parts.append(f"前{limit}")
    query = " ".join(query_parts)
    
    result = _get_mx().search(query)
    rows, source, err = _get_mx().extract_data(result)
    if err or not rows:
        # 换个写法
        query_parts2 = ["今日主力净额大于0"]
        if sector:
            query_parts2.append(sector)
        if extra_conditions:
            query_parts2.append(extra_conditions)
        query_parts2.append(f"前{limit}")
        query = " ".join(query_parts2)
        result = _get_mx().search(query)
        rows, source, err = _get_mx().extract_data(result)
    
    if err or not rows:
        print(f"[capital_flow] ❌ 全天主力查询失败: {err or '空结果'}")
        return []
    
    # 找字段名
    net_key = "主力净额(元)"
    for k in rows[0].keys():
        if "主力净额" in k and "合计" not in k:
            net_key = k
            break
    
    print(f"[capital_flow] ✅ 全天{len(rows)}条, 字段: {net_key}")
    
    results = []
    for r in rows:
        code = str(r.get("代码", "") or "").strip()
        name = str(r.get("名称", "") or "").strip()
        if not code or not name:
            continue
        
        main_net = _parse_float(r.get(net_key, 0))
        if direction == "outflow" and main_net > 0:
            main_net = -main_net
        
        results.append({
            "code": code,
            "name": name,
            "price": _parse_float(_gv(r, "最新价")),
            "pct": _parse_float(_gv(r, "涨跌幅")),
            "turnover": _parse_float(_gv(r, "换手率")),
            "vol_ratio": _parse_float(_gv(r, "量比")),
            "amount": _parse_float(_gv(r, "成交额")),
            "main_net": main_net / 100000000,
            "main_net_raw": main_net,
            "pe": _parse_float(_gv(r, "市盈率")),
            "pb": _parse_float(_gv(r, "市净率")),
        })
    
    results.sort(key=lambda r: abs(r["main_net"]), reverse=True)
    return results[:limit]


# ---------- 单只个股资金流向 ----------

def get_stock_money_flow(code: str, name: str) -> Dict[str, Any]:
    """
    获取单只个股的资金流向数据（主力净额）
    返回结构兼容 dashboard 原 fetch_money_flow 的 'zhu_li_net' 字段
    
    Returns:
        {"zhu_li_net": 万元, "source": "mx-xuangu"} 或空dict
    """
    try:
        # mx-xuangu 用自然语言查个股主力资金
        query = f"{name} {code} 今日主力净额"
        result = _get_mx().search(query)
        rows, source, err = _get_mx().extract_data(result)
        if err or not rows:
            print(f"[money_flow] mx-xuangu无结果: {err}")
            return {}
        
        r = rows[0]
        zhu_li_raw = _gv(r, "主力净额", "0")
        # 解析 "-7.73亿" 或 "1234.56万" 格式
        zhu_li_yuan = _parse_float(zhu_li_raw)
        zhu_li_wan = round(zhu_li_yuan / 10000, 0)
        
        ret = {
            "zhu_li_net": zhu_li_wan,
            "source": "mx-xuangu",
            "_raw": zhu_li_raw,
        }
        print(f"[money_flow] {name}({code}) 主力净额: {zhu_li_raw} = {zhu_li_wan}万元")
        return ret
    except Exception as e:
        print(f"[money_flow] {name}({code}) 查询失败: {e}")
        return {}


# ---------- 报表生成 ----------

def format_capital_report(
    data: List[Dict[str, Any]],
    title: str = "主力资金流向TOP",
    net_field: str = "close_net",
    max_items: int = 10,
) -> str:
    """
    生成资金流向文本报告
    
    Args:
        data: 股票列表
        title: 报告标题
        net_field: 资金字段名（close_net / main_net）
        max_items: 输出条数
    """
    if not data:
        return f"📊 {title}\n没有数据\n"
    
    lines = [
        f"📊 {title}",
        "─" * 40,
        f"🤖 【MX智能选股脚本自动生成】",
        f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    
    for i, r in enumerate(data[:max_items]):
        net_val = r.get(net_field, 0)
        net_str = f"+{net_val:.2f}亿" if net_val >= 0 else f"{net_val:.2f}亿"
        pct_str = f"+{r['pct']:.1f}%" if r['pct'] >= 0 else f"{r['pct']:.1f}%"
        
        lines.append(f"#{i+1} {r['name']}({r['code']}) | {r['price']:.2f}({pct_str})")
        lines.append(f"   尾盘主力净额: {net_str} | 换手{r['turnover']:.1f}%")
    
    lines.extend([
        "",
        "⚠️ 仅供参考，不构成投资建议",
        "🕵️‍♂️ StockHolmes · MX智能选股",
    ])
    return "\n".join(lines)


def format_combined_report(
    inflow: List[Dict[str, Any]],
    outflow: List[Dict[str, Any]],
    mode: str = "close",
    max_items: int = 5,
) -> str:
    """
    生成资金流入流出综合报告
    mode: "close"=尾盘, "full"=全天
    """
    if mode == "close":
        title = "尾盘30分钟主力资金流向"
        field = "close_net"
    else:
        title = "今日主力资金流向"
        field = "main_net"
    
    lines = [
        f"📊 {title}",
        "─" * 45,
        f"🤖 【MX智能选股脚本自动生成】",
        f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "🟢 主力净流入TOP5:",
    ]
    
    for i, r in enumerate(inflow[:max_items]):
        net_val = r.get(field, 0)
        lines.append(f"  #{i+1} {r['name']}({r['code']}) +{net_val:.2f}亿 涨幅{r['pct']:+.1f}%")
    
    lines.extend([
        "",
        "🔴 主力净流出TOP5:",
    ])
    
    for i, r in enumerate(outflow[:max_items]):
        net_val = r.get(field, 0)
        lines.append(f"  #{i+1} {r['name']}({r['code']}) {net_val:.2f}亿 涨幅{r['pct']:+.1f}%")
    
    lines.extend([
        "",
        "⚠️ 仅供参考，不构成投资建议",
        "🕵️‍♂️ StockHolmes · MX智能选股",
    ])
    return "\n".join(lines)


# ---------- 独立运行测试 ----------

if __name__ == "__main__":
    print("=" * 50)
    print("🕵️‍♂️ Capital Flow 工具模块测试")
    print(datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 50)
    
    print("\n\n=== 1️⃣ 尾盘30分钟主力净流入TOP10（创业板+科创板） ===")
    inflow = get_close_capital_flow("inflow", 10, "all", "换手率大于3%")
    print(format_capital_report(inflow, "尾盘主力净流入TOP10", "close_net"))
    
    print("\n\n=== 2️⃣ 尾盘30分钟主力净流出TOP5 ===")
    outflow = get_close_capital_flow("outflow", 5, "all")
    print(format_capital_report(outflow, "尾盘主力净流出TOP5", "close_net"))
    
    print("\n\n=== 3️⃣ 全天主力净流入TOP5（半导体板块） ===")
    full = get_full_day_capital_flow("inflow", 5, "半导体")
    print(format_capital_report(full, "半导体板块全天主力净流入TOP5", "main_net"))
    
    print("\n\n=== 4️⃣ 综合报告（尾盘） ===")
    inflow2 = get_close_capital_flow("inflow", 10, "all")
    outflow2 = get_close_capital_flow("outflow", 10, "all")
    print(format_combined_report(inflow2, outflow2, "close"))
