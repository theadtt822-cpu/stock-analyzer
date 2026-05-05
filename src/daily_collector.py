"""
每日定时报告数据收集器
- 盘前数据（隔夜外盘 + 期货 + 政策 + 板块预测）
- 午间新闻（A股/美股新闻 + 经济指标 + 投行观点）
- 收盘复盘（指数 + 板块 + 涨跌停 + 技术分析 + 明日展望）
"""
import html
import os
from datetime import datetime

os.environ["PATH"] = r"C:\Users\Admin\AppData\Local\Programs\Python\Python312;" + os.environ.get("PATH", "")

import akshare as ak
import pandas as pd
from src import StockData, MarketData, TechIndicator
from src.analysis import (
    PremarketReportGenerator,
    NewsReportGenerator,
    PostmarketReportGenerator,
)

REPORT_DIR = "./output"
os.makedirs(REPORT_DIR, exist_ok=True)


def _safe_call(func, *args, **kwargs):
    """安全调用，失败返回 None"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"  [WARN] {func.__name__}: {e}")
        return None


def _fmt_pct(val) -> str:
    """格式化涨跌幅"""
    try:
        v = float(val)
        return f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%"
    except (ValueError, TypeError):
        return str(val)


def _get_col(df, candidates, default=None):
    """从 DataFrame 安全获取值"""
    if df is None or df.empty:
        return default
    row = df.iloc[0]
    for c in candidates:
        if c in row.index:
            return row[c]
    return default


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ============================================================
# 盘前预测数据收集
# ============================================================

def collect_premarket_data() -> dict:
    """收集盘前预测所需数据"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[盘前预测] 收集数据 - {today}")

    # --- 隔夜美股 ---
    us_indices = []
    us_summary_parts = []
    for code, name in [("100", "纳斯达克"), ("300", "道琼斯"), ("500", "标普500")]:
        try:
            df = ak.stock_us_index_daily_em(symbol=code)
            if df is not None and not df.empty:
                # 列名可能是中文
                close_c = "收盘" if "收盘" in df.columns else ("close" if "close" in df.columns else None)
                pct_c = "涨跌幅" if "涨跌幅" in df.columns else ("pct_change" if "pct_change" in df.columns else None)
                if close_c and pct_c:
                    last = df.iloc[-1]
                    us_indices.append({
                        "name": name,
                        "close": f"{_safe_float(last[close_c]):.2f}",
                        "pct_change": _fmt_pct(last[pct_c]),
                    })
                    us_summary_parts.append(f"{name} {_fmt_pct(last[pct_c])}")
        except Exception:
            pass

    us_summary = "；".join(us_summary_parts) if us_summary_parts else "暂无数据"

    # --- 港股 ---
    hk_data = {}
    try:
        df = ak.index_zh_a_hist(symbol="HSI", period="daily",
                                start_date=(datetime.now() - pd.Timedelta(days=10)).strftime("%Y%m%d"),
                                end_date=datetime.now().strftime("%Y%m%d"))
        if df is not None and not df.empty:
            close_c = "收盘" if "收盘" in df.columns else "close"
            pct_c = "涨跌幅" if "涨跌幅" in df.columns else "pct_change"
            last = df.iloc[-1]
            hk_data = {
                "close": f"{_safe_float(last[close_c]):.2f}",
                "pct_change": _fmt_pct(last[pct_c]),
                "summary": f"恒生指数收于{_safe_float(last[close_c]):.0f}点",
            }
    except Exception:
        hk_data = {"close": "暂无数据", "pct_change": "", "summary": "暂无数据"}

    # --- 股指期货 ---
    futures = []
    try:
        df = ak.futures_index_board_em()
        if df is not None and not df.empty:
            name_c = "名称" if "名称" in df.columns else ("name" if "name" in df.columns else None)
            pct_c = "涨跌幅" if "涨跌幅" in df.columns else ("pct_change" if "pct_change" in df.columns else None)
            if name_c and pct_c:
                for _, row in df.head(5).iterrows():
                    futures.append({"name": str(row[name_c]), "pct_change": _fmt_pct(row[pct_c])})
    except Exception:
        pass
    if not futures:
        futures = [{"name": "暂无数据", "pct_change": ""}]

    # --- 政策消息 ---
    policy_news = []
    try:
        df = ak.stock_news_cctv(date=datetime.now().strftime("%Y%m%d"))
        if df is not None and not df.empty:
            title_c = "标题" if "标题" in df.columns else ("title" if "title" in df.columns else None)
            content_c = "内容" if "内容" in df.columns else ("content" if "content" in df.columns else None)
            if title_c and content_c:
                for _, row in df.head(8).iterrows():
                    policy_news.append({
                        "title": str(row[title_c]),
                        "summary": str(row[content_c])[:120],
                        "impact_level": "high" if any(k in str(row[title_c]) for k in ["央行", "降息", "降准", "财政", "监管"]) else "medium",
                    })
    except Exception:
        pass
    if not policy_news:
        policy_news = [{"title": "暂无重要政策消息", "summary": "", "impact_level": "low"}]

    # --- 板块预测 ---
    sector_forecast = {"bullish": [], "bearish": []}
    try:
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            name_c = "板块名称" if "板块名称" in df.columns else ("name" if "name" in df.columns else None)
            pct_c = "涨跌幅" if "涨跌幅" in df.columns else ("pct_change" if "pct_change" in df.columns else None)
            if name_c and pct_c:
                sorted_df = df.sort_values(pct_c, ascending=False)
                for _, row in sorted_df.head(5).iterrows():
                    sector_forecast["bullish"].append({
                        "sector": str(row[name_c]),
                        "reason": f"涨幅{_fmt_pct(row[pct_c])}",
                    })
                for _, row in sorted_df.tail(5).iterrows():
                    sector_forecast["bearish"].append({
                        "sector": str(row[name_c]),
                        "reason": f"跌幅{_fmt_pct(row[pct_c])}",
                    })
    except Exception:
        pass

    # --- 综合研判 ---
    # 用上交所近期指数趋势判断
    verdict = {"direction": "震荡", "confidence": "中", "reasoning": "市场整体处于震荡格局"}
    try:
        mkt = MarketData()
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - pd.Timedelta(days=60)).strftime("%Y%m%d")
        df = mkt.get_index_daily("000001", start, end)
        if df is not None and not df.empty and len(df) >= 20:
            close_c = "收盘" if "收盘" in df.columns else "close"
            last_close = _safe_float(df.iloc[-1][close_c])
            ma20 = df[close_c].tail(20).mean()
            if last_close > ma20 * 1.02:
                verdict = {
                    "direction": "看多", "confidence": "中高",
                    "reasoning": "沪指站上20日均线，短期趋势向好",
                }
            elif last_close < ma20 * 0.98:
                verdict = {
                    "direction": "看空", "confidence": "中",
                    "reasoning": "沪指跌破20日均线，注意下行风险",
                }
    except Exception:
        pass

    return {
        "overnight_us": {"indices": us_indices, "summary": us_summary},
        "hk_market": hk_data,
        "futures": futures,
        "policy_news": policy_news,
        "sector_forecast": sector_forecast,
        "overall_verdict": verdict,
    }


# ============================================================
# 午间新闻数据收集
# ============================================================

def collect_news_data() -> dict:
    """收集午间投资新闻数据"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[午间新闻] 收集数据 - {today}")

    date_str = datetime.now().strftime("%Y%m%d")

    # --- A股新闻 ---
    a_stock_news = []
    try:
        df = ak.stock_news_cctv(date=date_str)
        if df is not None and not df.empty:
            title_c = "标题" if "标题" in df.columns else "title"
            content_c = "内容" if "内容" in df.columns else "content"
            source_c = "来源" if "来源" in df.columns else ("source" if "source" in df.columns else "CCTV")
            for _, row in df.head(10).iterrows():
                title = str(row[title_c])
                # 简单判断利好/利空
                if any(k in title for k in ["利好", "上涨", "突破", "增长", "超预期", "新高"]):
                    impact = "positive"
                elif any(k in title for k in ["利空", "下跌", "暴跌", "下滑", "不及预期", "新低"]):
                    impact = "negative"
                else:
                    impact = "neutral"
                a_stock_news.append({
                    "title": title,
                    "summary": str(row[content_c])[:120],
                    "source": str(row[source_c]) if source_c in row.index else "CCTV",
                    "impact": impact,
                })
    except Exception:
        pass

    # --- 美股新闻 ---
    us_stock_news = []
    try:
        # 尝试获取全球财经新闻
        df = ak.stock_news_cctv(date=date_str)
        if df is not None and not df.empty:
            title_c = "标题" if "标题" in df.columns else "title"
            content_c = "内容" if "内容" in df.columns else "content"
            for _, row in df.tail(5).iterrows():
                title = str(row[title_c])
                us_stock_news.append({
                    "title": title,
                    "summary": str(row[content_c])[:120],
                    "source": "CCTV",
                    "impact": "neutral",
                })
    except Exception:
        pass

    # --- 经济指标 ---
    economic_indicators = []
    for func, name in [
        (ak.macro_china_cpi_yearly, "CPI同比"),
        (ak.macro_china_ppi_yearly, "PPI同比"),
        (ak.macro_china_pmi_yearly, "PMI"),
    ]:
        try:
            df = func()
            if df is not None and not df.empty:
                last = df.iloc[-1]
                cols = list(last.index)
                val_col = cols[1] if len(cols) > 1 else cols[0]
                date_col = cols[0]
                val = _safe_float(last[val_col], None)
                if val is not None:
                    prev_val = _safe_float(df.iloc[-2][val_col], None) if len(df) > 1 else None
                    change_str = "环比持平"
                    if prev_val is not None:
                        diff = val - prev_val
                        change_str = f"环比{'+' if diff >= 0 else ''}{diff:.2f}"
                    economic_indicators.append({
                        "name": name,
                        "value": f"{val:.1f}" if val < 100 else f"{val:.0f}",
                        "change": change_str,
                        "change_color": "green" if prev_val and val < prev_val else "red" if prev_val and val > prev_val else "gray",
                        "interpretation": f"{name}最新值",
                    })
        except Exception:
            pass
    if not economic_indicators:
        economic_indicators = [{"name": "暂无数据", "value": "", "change": "", "change_color": "gray", "interpretation": ""}]

    # --- 投行观点 ---
    investment_views = [
        {
            "firm": "市场研判",
            "direction": "bullish" if a_stock_news and any(n["impact"] == "positive" for n in a_stock_news) else "neutral",
            "view": "综合市场消息，当前投资情绪" + ("偏积极" if a_stock_news and any(n["impact"] == "positive" for n in a_stock_news) else "整体平稳"),
        },
    ]

    return {
        "a_stock_news": a_stock_news,
        "us_stock_news": us_stock_news,
        "economic_indicators": economic_indicators,
        "investment_views": investment_views,
    }


# ============================================================
# 收盘复盘数据收集
# ============================================================

def collect_postmarket_data() -> dict:
    """收集收盘复盘所需数据"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[收盘复盘] 收集数据 - {today}")

    # --- 主要指数 ---
    indices = []
    index_map = {
        "000001": "上证指数",
        "399001": "深证成指",
        "399006": "创业板指",
        "000016": "上证50",
        "000905": "中证500",
    }
    mkt = MarketData()
    start = (datetime.now() - pd.Timedelta(days=10)).strftime("%Y%m%d")
    end = datetime.now().strftime("%Y%m%d")

    for code, name in index_map.items():
        try:
            df = mkt.get_index_daily(code, start, end)
            if df is not None and not df.empty:
                close_c = "收盘" if "收盘" in df.columns else "close"
                pct_c = "涨跌幅" if "涨跌幅" in df.columns else ("pct_change" if "pct_change" in df.columns else None)
                vol_c = "成交量" if "成交量" in df.columns else ("volume" if "volume" in df.columns else None)
                amt_c = "成交额" if "成交额" in df.columns else ("amount" if "amount" in df.columns else None)
                last = df.iloc[-1]
                vol_str = f"{_safe_float(last[vol_c]) / 1e8:.0f}亿" if vol_c and vol_c in last.index else "N/A"
                amt_str = f"{_safe_float(last[amt_c]) / 1e8:.0f}亿" if amt_c and amt_c in last.index else "N/A"
                indices.append({
                    "name": name, "code": code,
                    "close": f"{_safe_float(last[close_c]):.2f}",
                    "pct_change": _fmt_pct(last[pct_c]) if pct_c and pct_c in last.index else "N/A",
                    "volume": vol_str, "turnover": amt_str,
                })
        except Exception:
            pass

    # --- 板块涨跌排行 ---
    sector_rise = []
    sector_fall = []
    try:
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            name_c = "板块名称" if "板块名称" in df.columns else ("name" if "name" in df.columns else None)
            pct_c = "涨跌幅" if "涨跌幅" in df.columns else ("pct_change" if "pct_change" in df.columns else None)
            if name_c and pct_c:
                sorted_df = df.sort_values(pct_c, ascending=False)
                for _, row in sorted_df.head(10).iterrows():
                    sector_rise.append({"sector": str(row[name_c]), "pct_change": _fmt_pct(row[pct_c])})
                for _, row in sorted_df.tail(10).iterrows():
                    sector_fall.append({"sector": str(row[name_c]), "pct_change": _fmt_pct(row[pct_c])})
    except Exception:
        pass

    # --- 涨停/跌停 ---
    limit_up = []
    limit_down = []
    try:
        df = ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d"))
        if df is not None and not df.empty:
            name_c = "名称" if "名称" in df.columns else "name"
            code_c = "代码" if "代码" in df.columns else "code"
            reason_c = "封板原因" if "封板原因" in df.columns else ("reason" if "reason" in df.columns else None)
            for _, row in df.head(10).iterrows():
                limit_up.append({
                    "name": str(row.get(name_c, "")),
                    "code": str(row.get(code_c, "")),
                    "reason": str(row.get(reason_c, "")) if reason_c and reason_c in row.index else "",
                })
    except Exception:
        pass
    try:
        df = ak.stock_dt_pool_em(date=datetime.now().strftime("%Y%m%d"))
        if df is not None and not df.empty:
            name_c = "名称" if "名称" in df.columns else "name"
            code_c = "代码" if "代码" in df.columns else "code"
            reason_c = "跌停原因" if "跌停原因" in df.columns else ("reason" if "reason" in df.columns else None)
            for _, row in df.head(10).iterrows():
                limit_down.append({
                    "name": str(row.get(name_c, "")),
                    "code": str(row.get(code_c, "")),
                    "reason": str(row.get(reason_c, "")) if reason_c and reason_c in row.index else "",
                })
    except Exception:
        pass

    # --- 技术面分析（上证指数） ---
    technical_analysis = {"support_levels": [], "resistance_levels": [], "volume_analysis": "", "key_indicators": ""}
    try:
        df = mkt.get_index_daily("000001", (datetime.now() - pd.Timedelta(days=200)).strftime("%Y%m%d"), end)
        if df is not None and not df.empty and len(df) >= 60:
            close_c = "收盘" if "收盘" in df.columns else "close"
            high_c = "最高" if "最高" in df.columns else "high"
            low_c = "最低" if "最低" in df.columns else "low"
            vol_c = "成交量" if "成交量" in df.columns else ("volume" if "volume" in df.columns else None)

            df = df.copy()
            df["sma5"] = df[close_c].rolling(5).mean()
            df["sma10"] = df[close_c].rolling(10).mean()
            df["sma20"] = df[close_c].rolling(20).mean()
            df["sma60"] = df[close_c].rolling(60).mean()

            ti = TechIndicator(df)
            macd_data = ti.calc_macd()
            df["dif"], df["dea"], df["macd"] = macd_data["dif"], macd_data["dea"], macd_data["macd"]
            df["rsi"] = ti.calc_rsi(14)

            last = df.iloc[-1]
            low_20 = df[low_c].tail(20).min()
            high_20 = df[high_c].tail(20).max()
            ma20 = last["sma20"]
            ma60 = last["sma60"]

            close_val = _safe_float(last[close_c])
            if ma20 < close_val:
                technical_analysis["support_levels"].append(f"MA20={ma20:.0f}")
            if ma60 < close_val:
                technical_analysis["support_levels"].append(f"MA60={ma60:.0f}")
            technical_analysis["support_levels"].append(f"20日低={low_20:.0f}")

            if ma20 > close_val:
                technical_analysis["resistance_levels"].append(f"MA20={ma20:.0f}")
            if ma60 > close_val:
                technical_analysis["resistance_levels"].append(f"MA60={ma60:.0f}")
            technical_analysis["resistance_levels"].append(f"20日高={high_20:.0f}")

            # 成交量分析
            if vol_c:
                vol_avg = df[vol_c].tail(20).mean()
                last_vol = _safe_float(last[vol_c])
                if last_vol > vol_avg * 1.5:
                    technical_analysis["volume_analysis"] = f"今日成交量为20日均量的{last_vol/vol_avg:.1f}倍，明显放量"
                elif last_vol < vol_avg * 0.5:
                    technical_analysis["volume_analysis"] = f"今日成交量为20日均量的{last_vol/vol_avg:.1f}倍，明显缩量"
                else:
                    technical_analysis["volume_analysis"] = f"今日成交量与20日均量相当"

            rsi_val = _safe_float(last["rsi"])
            dif_val = _safe_float(last["dif"])
            dea_val = _safe_float(last["dea"])
            if rsi_val > 70:
                rsi_status = "超买区域"
            elif rsi_val < 30:
                rsi_status = "超卖区域"
            else:
                rsi_status = "中性区域"
            macd_status = "金叉" if dif_val > dea_val else "死叉"
            technical_analysis["key_indicators"] = f"RSI={rsi_val:.1f}（{rsi_status}），MACD{macd_status}"
    except Exception:
        pass

    # --- 明日展望 ---
    outlook = {"direction": "震荡", "key_factors": [], "strategy": "观望为主"}
    if indices:
        sh_pct = _safe_float(indices[0].get("pct_change", "0").replace("%", "").replace("+", ""))
        if sh_pct > 0.5:
            outlook["direction"] = "看多"
            outlook["key_factors"] = ["市场放量上涨，做多情绪积极"]
            outlook["strategy"] = "可适当加仓，关注持续性"
        elif sh_pct < -0.5:
            outlook["direction"] = "看空"
            outlook["key_factors"] = ["市场下跌，注意防范风险"]
            outlook["strategy"] = "控制仓位，谨慎操作"
        else:
            outlook["direction"] = "震荡"
            outlook["key_factors"] = ["市场窄幅震荡，方向不明确"]
            outlook["strategy"] = "观望为主，等待突破信号"

    return {
        "indices": indices,
        "sector_rise": sector_rise,
        "sector_fall": sector_fall,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "technical_analysis": technical_analysis,
        "tomorrow_outlook": outlook,
    }


# ============================================================
# 报告生成 & 推送
# ============================================================

def _push(title: str, summary: str):
    """推送到微信"""
    try:
        from src.utils.push import push
        result = push(title, summary)
        if result.get("code") == 0:
            print(f"  [OK] 微信推送成功: {title}")
        else:
            print(f"  [WARN] 微信推送失败: {result.get('message', 'unknown')}")
    except Exception as e:
        print(f"  [WARN] 微信推送异常: {e}")


def run_premarket_report():
    """执行盘前预测报告"""
    print("\n" + "=" * 60)
    print("盘前预测报告")
    print("=" * 60)

    data = collect_premarket_data()
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{REPORT_DIR}/premarket_{date_str}.html"

    gen = PremarketReportGenerator(date_str)
    gen.generate_html(data, filename)
    print(f"  报告已保存: {filename}")

    # 微信推送摘要
    verdict = data.get("overall_verdict", {})
    summary = f"方向: {verdict.get('direction', 'N/A')}\n"
    summary += f"置信度: {verdict.get('confidence', 'N/A')}\n"
    summary += f"原因: {verdict.get('reasoning', '')}"
    _push(f"盘前预测 {date_str}", summary)


def run_news_report():
    """执行午间新闻报告"""
    print("\n" + "=" * 60)
    print("午间新闻报告")
    print("=" * 60)

    data = collect_news_data()
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{REPORT_DIR}/news_{date_str}.html"

    gen = NewsReportGenerator(date_str)
    gen.generate_html(data, filename)
    print(f"  报告已保存: {filename}")

    a_news = data.get("a_stock_news", [])
    pos = sum(1 for n in a_news if n.get("impact") == "positive")
    neg = sum(1 for n in a_news if n.get("impact") == "negative")
    summary = f"A股要闻: {len(a_news)}条（利好{pos}条，利空{neg}条）"
    _push(f"午间新闻 {date_str}", summary)


def run_postmarket_report():
    """执行收盘复盘报告"""
    print("\n" + "=" * 60)
    print("收盘复盘报告")
    print("=" * 60)

    data = collect_postmarket_data()
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{REPORT_DIR}/postmarket_{date_str}.html"

    gen = PostmarketReportGenerator(date_str)
    gen.generate_html(data, filename)
    print(f"  报告已保存: {filename}")

    indices = data.get("indices", [])
    summary_lines = ["今日指数:"]
    for idx in indices[:3]:
        summary_lines.append(f"{idx['name']}: {idx['close']} ({idx['pct_change']})")
    limit_up = data.get("limit_up", [])
    limit_down = data.get("limit_down", [])
    summary_lines.append(f"\n涨停: {len(limit_up)}只  跌停: {len(limit_down)}只")
    outlook = data.get("tomorrow_outlook", {})
    summary_lines.append(f"\n明日展望: {outlook.get('direction', 'N/A')}")
    _push(f"收盘复盘 {date_str}", "\n".join(summary_lines))


# ============================================================
# 一次性运行所有报告（手动测试用）
# ============================================================

def run_all_reports():
    """手动运行全部报告"""
    run_premarket_report()
    run_news_report()
    run_postmarket_report()
    print("\n全部报告生成完成！")
