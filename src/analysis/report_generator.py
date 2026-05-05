"""
专业股票分析报告生成器
"""
import pandas as pd
import numpy as np
from typing import Optional
from datetime import datetime


class ReportGenerator:
    """分析报告生成器"""

    def __init__(self, df: pd.DataFrame, symbol: str = ""):
        self.df = df.copy()
        self.symbol = symbol
        self.latest = df.iloc[-1]
        self.prev = df.iloc[-2] if len(df) > 1 else df.iloc[0]

    def _get(self, col: str, default=0) -> float:
        val = self.latest.get(col, default)
        return val if val is not None and not np.isnan(val) else default

    def _get_prev(self, col: str, default=0) -> float:
        val = self.prev.get(col, default)
        return val if val is not None and not np.isnan(val) else default

    # ========== 指标解读 ==========

    def interpret_macd(self) -> dict:
        dif = self._get('dif')
        dea = self._get('dea')
        macd = self._get('macd')
        dif_prev = self._get_prev('dif')
        dea_prev = self._get_prev('dea')
        # 判断交叉
        is_golden = dif_prev <= dea_prev and dif > dea
        is_death = dif_prev >= dea_prev and dif < dea
        # 判断零轴
        above_zero = dif > 0 and dea > 0
        below_zero = dif < 0 and dea < 0
        # 判断方向
        dif_rising = dif > dif_prev
        dea_rising = dea > dea_prev

        if is_golden and below_zero:
            status, status_color = "底部金叉", "green"
            desc = "零轴下方金叉，超跌反弹信号"
        elif is_golden and above_zero:
            status, status_color = "多头金叉", "red"
            desc = "多头趋势确认，多方力量增强"
        elif is_death and above_zero:
            status, status_color = "高位死叉", "green"
            desc = "零轴上方死叉，警惕回调"
        elif is_death and below_zero:
            status, status_color = "空头死叉", "green"
            desc = "空头趋势延续，观望为主"
        elif above_zero and dif_rising:
            status, status_color = "多头持续", "red"
            desc = "多方持续放大，趋势健康"
        elif above_zero:
            status, status_color = "多头减弱", "orange"
            desc = "多方力量减弱，注意风险"
        elif below_zero and dif < dif_prev:
            status, status_color = "空头放大", "green"
            desc = "空方持续放大，下跌加速"
        elif below_zero:
            status, status_color = "空头减弱", "orange"
            desc = "空方力量减弱，可能企稳"
        else:
            status, status_color = "中性", "gray"
            desc = "指标无明显信号"

        return {
            'name': 'MACD',
            'value': f'DIF={dif:.2f} DEA={dea:.1f} MACD={macd:.2f}',
            'status': status,
            'status_color': status_color,
            'desc': desc
        }

    def interpret_rsi(self) -> dict:
        rsi = self._get('rsi')
        rsi_prev = self._get_prev('rsi')
        rsi_change = rsi - rsi_prev

        if rsi > 80:
            status, status_color = "严重超买", "green"
            desc = f"RSI={rsi:.1f}，极度超买，回调风险大"
        elif rsi > 70:
            status, status_color = "超买", "green"
            desc = f"RSI={rsi:.1f} 进入超买区，注意回调"
        elif rsi > 60:
            status, status_color = "偏强", "red"
            trend = "上行" if rsi_change > 0 else "回落"
            desc = f"RSI={rsi:.1f} 偏强区域，{trend}中"
        elif rsi > 40:
            status, status_color = "中性", "gray"
            desc = f"RSI={rsi:.1f} 中性区间，无明显方向"
        elif rsi > 30:
            status, status_color = "偏弱", "orange"
            trend = "上行" if rsi_change > 0 else "下行"
            desc = f"RSI={rsi:.1f} 偏弱区域，{trend}中"
        elif rsi > 20:
            status, status_color = "超卖", "red"
            desc = f"RSI={rsi:.1f} 超卖区，可能反弹"
        else:
            status, status_color = "严重超卖", "red"
            desc = f"RSI={rsi:.1f}，极度超卖，反弹概率大"

        return {
            'name': 'RSI(14)',
            'value': f'{rsi:.1f}',
            'status': status,
            'status_color': status_color,
            'desc': desc
        }

    def interpret_ma(self) -> dict:
        ma5 = self._get('sma5')
        ma10 = self._get('sma10')
        ma20 = self._get('sma20')
        ma60 = self._get('sma60')
        close = self._get('close')

        # 均线排列判断
        if ma5 > ma10 > ma20 > ma60:
            status, status_color = "多头排列", "red"
            desc = "均线完美多头排列，趋势明确向上"
        elif ma5 > ma10 > ma20:
            status, status_color = "短期多头", "red"
            desc = "短中期均线向上，短期趋势向好"
        elif close > ma20 and ma5 > ma10:
            status, status_color = "偏多", "red"
            desc = "价格在20日线上，短期偏多"
        elif close < ma20 and ma5 < ma10:
            status, status_color = "偏空", "green"
            desc = "价格在20日线下，短期偏空"
        elif ma5 < ma10 < ma20 < ma60:
            status, status_color = "空头排列", "green"
            desc = "均线空头排列，趋势明确向下"
        else:
            status, status_color = "震荡", "gray"
            desc = "均线交织，震荡整理中"

        # 支撑/压力
        if close > ma5:
            support = f"MA5={ma5:.0f}"
        elif close > ma10:
            support = f"MA10={ma10:.0f}"
        elif close > ma20:
            support = f"MA20={ma20:.0f}"
        else:
            support = f"MA60={ma60:.0f}"

        return {
            'name': '均线系统',
            'value': f'MA5={ma5:.0f} MA20={ma20:.0f} MA60={ma60:.0f}',
            'status': status,
            'status_color': status_color,
            'desc': desc,
            'support': support
        }

    def interpret_boll(self) -> dict:
        upper = self._get('upper')
        middle = self._get('middle')
        lower = self._get('lower')
        close = self._get('close')

        if upper > lower and upper > 0:
            pct = (close - lower) / (upper - lower) * 100
        else:
            pct = 50

        bandwidth = (upper - lower) / middle * 100 if middle > 0 else 0

        if close > upper:
            status, status_color = "突破上轨", "red"
            desc = f"价格突破上轨({upper:.0f})，强势上行"
        elif pct > 75:
            status, status_color = "靠近上轨", "orange"
            desc = f"接近上轨压力位({upper:.0f})，注意阻力"
        elif close < lower:
            status, status_color = "跌破下轨", "green"
            desc = f"价格跌破下轨({lower:.0f})，弱势下行"
        elif pct < 25:
            status, status_color = "靠近下轨", "red"
            desc = f"接近下轨支撑位({lower:.0f})，可能反弹"
        elif abs(pct - 50) < 15:
            status, status_color = "中轨附近", "gray"
            desc = f"价格在中轨({middle:.0f})附近，方向不明"
        else:
            status, status_color = "通道内", "gray"
            desc = f"价格在通道内运行，带宽{bandwidth:.1f}%"

        return {
            'name': '布林带',
            'value': f'上={upper:.0f} 中={middle:.0f} 下={lower:.0f}',
            'status': status,
            'status_color': status_color,
            'desc': desc
        }

    def interpret_kdj(self) -> dict:
        k = self._get('k')
        d = self._get('d')
        j = self._get('j')
        k_prev = self._get_prev('k')
        d_prev = self._get_prev('d')

        is_golden = k_prev <= d_prev and k > d
        is_death = k_prev >= d_prev and k < d

        if j > 100:
            status, status_color = "J值极高", "green"
            desc = f"J={j:.0f} 极高值，回调压力大"
        elif j < 0:
            status, status_color = "J值极低", "red"
            desc = f"J={j:.0f} 极低值，反弹概率大"
        elif k > 80 and d > 80:
            status, status_color = "超买区", "green"
            desc = "KDJ进入超买区，注意风险"
        elif k < 20 and d < 20:
            status, status_color = "超卖区", "red"
            desc = "KDJ进入超卖区，可能反弹"
        elif is_golden and k < 50:
            status, status_color = "低位金叉", "red"
            desc = "K上穿D，低位金叉买入信号"
        elif is_golden:
            status, status_color = "金叉", "red"
            desc = "K上穿D，买入信号"
        elif is_death and k > 50:
            status, status_color = "高位死叉", "green"
            desc = "K下穿D，高位死叉卖出信号"
        elif is_death:
            status, status_color = "死叉", "green"
            desc = "K下穿D，卖出信号"
        elif k > d:
            status, status_color = "K>D偏多", "red"
            desc = f"K({k:.0f})>D({d:.0f})，偏多格局"
        else:
            status, status_color = "K<D偏空", "green"
            desc = f"K({k:.0f})<D({d:.0f})，偏空格局"

        return {
            'name': 'KDJ',
            'value': f'K={k:.0f} D={d:.0f} J={j:.0f}',
            'status': status,
            'status_color': status_color,
            'desc': desc
        }

    def interpret_atr(self) -> dict:
        atr = self._get('atr')
        close = self._get('close')
        atr_pct = (atr / close * 100) if close > 0 else 0

        # 计算ATR相对变化
        atr_hist = self.df.get('atr', pd.Series([atr] * 20))
        atr_avg_20 = atr_hist.tail(20).mean()
        atr_ratio = atr / atr_avg_20 if atr_avg_20 > 0 else 1

        if atr_pct > 4:
            status, status_color = "高波动", "green"
            desc = f"波动率{atr_pct:.1f}%，风险较高"
        elif atr_pct > 2:
            status, status_color = "正常波动", "gray"
            desc = f"波动率{atr_pct:.1f}%，正常水平"
        else:
            status, status_color = "低波动", "red"
            desc = f"波动率{atr_pct:.1f}%，可能变盘"

        return {
            'name': 'ATR',
            'value': f'{atr:.2f} ({atr_pct:.1f}%)',
            'status': status,
            'status_color': status_color,
            'desc': desc
        }

    # ========== 趋势分析 ==========

    def analyze_trend(self) -> dict:
        close = self._get('close')
        ma5 = self._get('sma5')
        ma10 = self._get('sma10')
        ma20 = self._get('sma20')
        ma60 = self._get('sma60')
        macd = self._get('macd')
        macd_prev = self._get_prev('macd')

        # 短期趋势 (5-10日)
        if close > ma5 and ma5 > ma10:
            short_score = 5
            short_trend = "看多"
            short_emoji = "📈"
            short_desc = "价格站上MA5/MA10，短期动能强劲"
        elif close > ma5:
            short_score = 4
            short_trend = "偏多"
            short_emoji = "📈"
            short_desc = "价格在MA5上方，短期偏强"
        elif close < ma10 and ma5 < ma10:
            short_score = 1
            short_trend = "看空"
            short_emoji = "📉"
            short_desc = "价格跌破MA5/MA10，短期承压"
        elif close < ma5:
            short_score = 2
            short_trend = "偏空"
            short_emoji = "📉"
            short_desc = "价格在MA5下方，短期偏弱"
        else:
            short_score = 3
            short_trend = "震荡"
            short_emoji = "⚖️"
            short_desc = "均线交织，短期震荡整理"

        # 中期趋势 (20-60日)
        if close > ma20 and ma20 > 0:
            ma20_slope = (ma20 - self.df['sma20'].tail(20).iloc[0]) / self.df['sma20'].tail(20).iloc[0] * 100 if 'sma20' in self.df.columns else 0
            if ma20_slope > 0 and macd > 0:
                mid_score = 5
                mid_trend = "看多"
                mid_emoji = "📈"
                mid_desc = f"MA20向上({ma20_slope:+.1f}%)，MACD多头"
            elif ma20_slope > 0:
                mid_score = 4
                mid_trend = "偏多"
                mid_emoji = "📈"
                mid_desc = "MA20向上，中期趋势向好"
            elif macd > 0:
                mid_score = 3
                mid_trend = "中性偏多"
                mid_emoji = "⚖️"
                mid_desc = "MACD偏多，但均线走平"
            else:
                mid_score = 2
                mid_trend = "偏空"
                mid_emoji = "📉"
                mid_desc = "MACD转弱，中期承压"
        else:
            mid_score = 1
            mid_trend = "看空"
            mid_emoji = "📉"
            mid_desc = "价格跌破MA20，中期走弱"

        # 长期趋势 (60日以上)
        if close > ma60 and ma60 > 0:
            ma60_slope = (ma60 - self.df['sma60'].tail(60).iloc[0]) / self.df['sma60'].tail(60).iloc[0] * 100 if 'sma60' in self.df.columns else 0
            if ma60_slope > 0:
                long_score = 5
                long_trend = "看多"
                long_emoji = "📈"
                long_desc = f"MA60向上({ma60_slope:+.1f}%)，长期牛市格局"
            else:
                long_score = 3
                long_trend = "中性"
                long_emoji = "⚖️"
                long_desc = "价格在MA60上方，但均线走平"
        else:
            long_score = 1
            long_trend = "看空"
            long_emoji = "📉"
            long_desc = "价格跌破MA60，长期走弱"

        return {
            'short': {'score': short_score, 'trend': short_trend, 'emoji': short_emoji, 'desc': short_desc},
            'mid': {'score': mid_score, 'trend': mid_trend, 'emoji': mid_emoji, 'desc': mid_desc},
            'long': {'score': long_score, 'trend': long_trend, 'emoji': long_emoji, 'desc': long_desc}
        }

    # ========== 信号检测 ==========

    def detect_signals(self, n: int = 10) -> list[dict]:
        signals = []
        df = self.df.copy()

        # 均线金叉/死叉
        if 'sma5' in df.columns and 'sma20' in df.columns:
            df['ma_cross'] = (df['sma5'] > df['sma20']) & (df['sma5'].shift(1) <= df['sma20'].shift(1))
            df['ma_death'] = (df['sma5'] < df['sma20']) & (df['sma5'].shift(1) >= df['sma20'].shift(1))

            for i, row in df[df['ma_cross']].tail(n).iterrows():
                signals.append({
                    'date': str(row.get('date', ''))[:10],
                    'type': '金叉',
                    'icon': '✅',
                    'desc': f"MA5上穿MA20，短线看多",
                    'color': 'buy'
                })
            for i, row in df[df['ma_death']].tail(n).iterrows():
                signals.append({
                    'date': str(row.get('date', ''))[:10],
                    'type': '死叉',
                    'icon': '⚠️',
                    'desc': f"MA5下穿MA20，短线看空",
                    'color': 'sell'
                })

        # MACD 金叉/死叉
        if 'dif' in df.columns and 'dea' in df.columns:
            df['macd_golden'] = (df['dif'] > df['dea']) & (df['dif'].shift(1) <= df['dea'].shift(1))
            df['macd_death'] = (df['dif'] < df['dea']) & (df['dif'].shift(1) >= df['dea'].shift(1))

            for i, row in df[df['macd_golden']].tail(n).iterrows():
                signals.append({
                    'date': str(row.get('date', ''))[:10],
                    'type': 'MACD金叉',
                    'icon': '✅',
                    'desc': f"DIF上穿DEA，买入信号",
                    'color': 'buy'
                })
            for i, row in df[df['macd_death']].tail(n).iterrows():
                signals.append({
                    'date': str(row.get('date', ''))[:10],
                    'type': 'MACD死叉',
                    'icon': '⚠️',
                    'desc': f"DIF下穿DEA，卖出信号",
                    'color': 'sell'
                })

        # 放量
        if 'volume' in df.columns:
            vol_avg = df['volume'].rolling(20).mean()
            df['volume_spike'] = df['volume'] > vol_avg * 2

            for i, row in df[df['volume_spike']].tail(n).iterrows():
                ratio = row['volume'] / vol_avg.get(i, 1) if vol_avg.get(i, 1) > 0 else 1
                chg = row.get('close', 0) - row.get('open', 0)
                direction = "放量上涨" if chg > 0 else "放量下跌"
                signals.append({
                    'date': str(row.get('date', ''))[:10],
                    'type': '放量',
                    'icon': '🔥',
                    'desc': f"{direction}，量能放大至均量{ratio:.1f}倍",
                    'color': 'buy' if chg > 0 else 'sell'
                })

        # RSI 超卖反弹
        if 'rsi' in df.columns:
            df['rsi_oversold'] = (df['rsi'] < 30) & (df['rsi'].shift(1) >= 30)
            df['rsi_overbought'] = (df['rsi'] > 70) & (df['rsi'].shift(1) <= 70)

            for i, row in df[df['rsi_oversold']].tail(n).iterrows():
                signals.append({
                    'date': str(row.get('date', ''))[:10],
                    'type': '超卖反弹',
                    'icon': '📈',
                    'desc': f"RSI跌破30后回升，反弹信号",
                    'color': 'buy'
                })
            for i, row in df[df['rsi_overbought']].tail(n).iterrows():
                signals.append({
                    'date': str(row.get('date', ''))[:10],
                    'type': '超买回落',
                    'icon': '📉',
                    'desc': f"RSI突破70后回落，回调信号",
                    'color': 'sell'
                })

        # 按日期排序，去重，取最近 N 个
        signals.sort(key=lambda x: x['date'], reverse=True)
        seen = set()
        unique = []
        for s in signals:
            key = (s['date'], s['type'])
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique[:n]

    # ========== 综合评分 ==========

    def calc_composite_score(self) -> dict:
        score = 50  # 中性起点

        close = self._get('close')
        ma5 = self._get('sma5')
        ma10 = self._get('sma10')
        ma20 = self._get('sma20')
        ma60 = self._get('sma60')
        rsi = self._get('rsi')
        dif = self._get('dif')
        dea = self._get('dea')
        k = self._get('k')
        d = self._get('d')

        # 均线部分 (±15分)
        if close > ma5 > ma10 > ma20:
            score += 15
        elif close > ma5 > ma10:
            score += 10
        elif close > ma20:
            score += 5
        elif close < ma5 < ma10 < ma20:
            score -= 15
        elif close < ma20:
            score -= 5

        # MACD (±15分)
        if dif > dea > 0:
            score += 15
        elif dif > dea:
            score += 8
        elif dif < dea < 0:
            score -= 15
        elif dif < dea:
            score -= 8

        # RSI (±10分)
        if 55 <= rsi <= 70:
            score += 10
        elif 40 <= rsi < 55:
            score += 5
        elif rsi > 80:
            score -= 10
        elif rsi < 20:
            score += 5  # 超卖反弹机会

        # KDJ (±10分)
        if k > d and k < 80:
            score += 10
        elif k > d:
            score += 3
        elif k < d and k > 20:
            score -= 10
        elif k < d:
            score -= 3

        # 布林带 (±10分)
        upper = self._get('upper')
        lower = self._get('lower')
        if upper > lower:
            boll_pct = (close - lower) / (upper - lower) * 100
            if 40 <= boll_pct <= 70:
                score += 5
            elif boll_pct > 90:
                score -= 10
            elif boll_pct < 10:
                score += 5

        score = max(0, min(100, score))

        if score >= 80:
            level, level_color = "强烈看多", "#DC143C"
        elif score >= 65:
            level, level_color = "偏多", "#E8555A"
        elif score >= 45:
            level, level_color = "中性", "#888"
        elif score >= 30:
            level, level_color = "偏空", "#2E8B57"
        else:
            level, level_color = "强烈看空", "#008000"

        return {'score': score, 'level': level, 'level_color': level_color}

    # ========== 支撑/压力位 ==========

    def calc_support_resistance(self) -> dict:
        close = self._get('close')
        ma20 = self._get('sma20')
        ma60 = self._get('sma60')
        high_20 = self.df['high'].tail(20).max()
        low_20 = self.df['low'].tail(20).min()
        high_60 = self.df['high'].tail(60).max()
        low_60 = self.df['low'].tail(60).min()

        supports = []
        resistances = []

        if ma20 < close:
            supports.append((f'MA20={ma20:.0f}', ma20))
        if ma60 < close:
            supports.append((f'MA60={ma60:.0f}', ma60))
        if low_20 < close:
            supports.append((f'20日低={low_20:.0f}', low_20))
        if low_60 < close:
            supports.append((f'60日低={low_60:.0f}', low_60))

        if ma20 > close:
            resistances.append((f'MA20={ma20:.0f}', ma20))
        if ma60 > close:
            resistances.append((f'MA60={ma60:.0f}', ma60))
        if high_20 > close:
            resistances.append((f'20日高={high_20:.0f}', high_20))
        if high_60 > close:
            resistances.append((f'60日高={high_60:.0f}', high_60))

        supports.sort(key=lambda x: x[1], reverse=True)
        resistances.sort(key=lambda x: x[1])

        return {
            'supports': [s[0] for s in supports[:3]],
            'resistances': [r[0] for r in resistances[:3]]
        }

    # ========== 操作建议 ==========

    def get_advice(self) -> dict:
        close = self._get('close')
        score = self.calc_composite_score()['score']
        ma20 = self._get('sma20')
        low_20 = self.df['low'].tail(20).min()
        high_20 = self.df['high'].tail(20).max()

        # 止损位
        stop_loss = min(ma20 * 0.97, low_20) if ma20 > 0 else low_20 * 0.97

        # 止盈位
        take_profit = high_20 * 1.05

        if score >= 70:
            holder = "趋势良好，继续持有，关注新高突破"
            watcher = "可轻仓介入，止损位{:.0f}".format(stop_loss)
        elif score >= 55:
            holder = "继续持有，关注{:.0f}压力位".format(high_20)
            watcher = "可小仓位试探，严格止损{:.0f}".format(stop_loss)
        elif score >= 45:
            holder = "震荡格局，可适当减仓观望"
            watcher = "暂不介入，等待明确信号"
        elif score >= 30:
            holder = "趋势偏弱，建议减仓或离场"
            watcher = "暂不介入，下跌趋势中不抄底"
        else:
            holder = "趋势走坏，果断离场"
            watcher = "严格回避，等待企稳信号"

        risk_items = []
        rsi = self._get('rsi')
        if rsi > 70:
            risk_items.append("RSI进入超买区，回调风险加大")
        if close > high_20 * 0.98:
            risk_items.append("价格接近前期高点，遇阻可能大")
        atr = self._get('atr')
        atr_pct = (atr / close * 100) if close > 0 else 0
        if atr_pct > 3:
            risk_items.append(f"波动率偏高({atr_pct:.1f}%)，注意日内风险")

        if not risk_items:
            risk_items.append("当前无明显风险信号")

        return {
            'holder': holder,
            'watcher': watcher,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risks': risk_items
        }

    # ========== 交易策略 (6步分析) ==========

    def generate_trading_strategy(self, fund_flow_data: dict = None) -> dict:
        """生成6步交易策略分析"""
        close = self._get('close')
        high = self._get('high')
        low = self._get('low')
        prev_close = self._get_prev('close')
        chg_pct = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0
        vol = self._get('volume')
        vol_avg = self.df['volume'].tail(20).mean() if 'volume' in self.df.columns else 0

        # MACD 状态
        macd_i = self.interpret_macd()
        if '金叉' in macd_i['status']:
            macd_status = '金叉'
        elif '死叉' in macd_i['status']:
            macd_status = '死叉'
        else:
            macd_status = '粘合'

        # RSI 状态
        rsi = self._get('rsi')
        if rsi > 70:
            rsi_status = '强势区'
        elif rsi < 30:
            rsi_status = '弱势区'
        else:
            rsi_status = '中性'

        # 盘口分析（简化版）：基于资金流大单vs小单
        if fund_flow_data:
            big_net = (fund_flow_data.get('super_order') or 0) + (fund_flow_data.get('large_order') or 0)
            small_net = fund_flow_data.get('small_order') or 0
            if big_net > 0 and big_net > abs(small_net) * 0.5:
                bid_ask = '买盘占优'
            elif big_net < 0 and abs(big_net) > abs(small_net) * 0.5:
                bid_ask = '卖盘占优'
            else:
                bid_ask = '均衡'
        else:
            bid_ask = 'N/A'

        # 关键价位
        sr = self.calc_support_resistance()
        advice = self.get_advice()
        score = self.calc_composite_score()['score']
        atr_pct = (self._get('atr') / close * 100) if close > 0 else 0
        trend = self.analyze_trend()

        # 仓位建议
        if score >= 70 and atr_pct <= 3:
            position = '可重仓（70%以上）'
        elif score >= 55:
            position = '适中仓位（30%-50%）'
        elif score >= 30:
            position = '轻仓试探（10%-30%）'
        else:
            position = '严格控制仓位或观望'

        # 今日价格行为描述
        if chg_pct > 3 and vol > vol_avg * 1.5:
            price_action = '放量上涨'
        elif chg_pct > 3:
            price_action = '缩量上涨'
        elif chg_pct < -3 and vol > vol_avg * 1.5:
            price_action = '放量下跌'
        elif chg_pct < -3:
            price_action = '缩量下跌'
        elif abs(chg_pct) < 1:
            price_action = '窄幅震荡'
        elif chg_pct > 0:
            price_action = '温和上涨'
        else:
            price_action = '温和下跌'

        # 核心逻辑
        logic_parts = []
        logic_parts.append(f"MACD{macd_status}+RSI{rsi_status}")
        if trend['short']['trend'] in ('看多', '偏多'):
            logic_parts.append("技术面向好")
        elif trend['short']['trend'] in ('看空', '偏空'):
            logic_parts.append("短期承压")
        else:
            logic_parts.append("短期震荡")
        logic_parts.append(f"今日{price_action}")
        if rsi > 70:
            logic_parts.append("注意超买回调风险")
        if fund_flow_data and fund_flow_data.get('main_5day_trend') in ('持续流出', '偏流出'):
            logic_parts.append("近期资金持续流出")
        elif fund_flow_data and fund_flow_data.get('main_5day_trend') in ('持续流入', '偏流入'):
            logic_parts.append("近期资金偏流入")
        if atr_pct > 4:
            logic_parts.append("高波动需谨慎")

        core_logic = '，'.join(logic_parts) + '。'

        return {
            'key_info': {
                'price': f'{close:.2f}',
                'chg_pct': f'+{chg_pct:.2f}%' if chg_pct >= 0 else f'{chg_pct:.2f}%',
                'high': f'{high:.2f}',
                'low': f'{low:.2f}',
                'bid_ask': bid_ask,
                'rsi': f'{rsi:.2f}',
                'rsi_status': rsi_status,
                'macd': macd_status,
            },
            'strategy': {
                'resistances': sr['resistances'][:2],
                'supports': sr['supports'][:2],
                'holder_advice': advice['holder'],
                'watcher_advice': advice['watcher'],
                'position_advice': position,
            },
            'core_logic': core_logic,
        }

    # ========== 生成 HTML 报告 ==========

    def generate_html(self, save_path: str, fund_flow_data: dict = None):
        indicators = [
            self.interpret_macd(),
            self.interpret_rsi(),
            self.interpret_ma(),
            self.interpret_boll(),
            self.interpret_kdj(),
            self.interpret_atr()
        ]
        trend = self.analyze_trend()
        signals = self.detect_signals(8)
        composite = self.calc_composite_score()
        sr = self.calc_support_resistance()
        advice = self.get_advice()
        strategy = self.generate_trading_strategy(fund_flow_data)

        # 价格和变化
        close = self._get('close')
        prev_close = self._get_prev('close')
        price_chg = close - prev_close
        price_pct = (price_chg / prev_close * 100) if prev_close > 0 else 0
        is_up = price_chg >= 0
        chg_color = "#DC143C" if is_up else "#008000"
        chg_arrow = "▲" if is_up else "▼"
        chg_sign = "+" if is_up else ""

        # 成交量格式化
        vol = self._get('volume')
        if vol >= 10000:
            vol_str = f"{vol / 10000:.1f}万手"
        elif vol >= 1000:
            vol_str = f"{vol / 1000:.1f}千手"
        else:
            vol_str = f"{vol:.0f}"

        high_20 = self.df['high'].tail(20).max()
        low_20 = self.df['low'].tail(20).min()
        date_str = str(self.latest.get('date', ''))[:10]
        sym = self.symbol or "未知股票"

        # Stars rendering
        def stars(score):
            full = '★' * score
            empty = '☆' * (5 - score)
            return f'<span class="stars">{full}{empty}</span>'

        # HTML generation
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{sym} - 技术分析报告</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Microsoft YaHei', 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; padding: 16px; }}
.container {{ max-width: 900px; margin: 0 auto; }}
.card {{ background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 16px; padding: 20px; }}
h2 {{ font-size: 16px; color: #333; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px; margin-bottom: 16px; }}

/* Header */
.header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; border-radius: 12px; padding: 24px; margin-bottom: 16px; }}
.header h1 {{ font-size: 22px; margin-bottom: 4px; }}
.header .date {{ font-size: 13px; opacity: 0.7; }}
.price-row {{ display: flex; align-items: baseline; gap: 12px; margin: 12px 0; }}
.price {{ font-size: 36px; font-weight: bold; }}
.chg {{ font-size: 18px; font-weight: 500; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-top: 16px; }}
.stat-item {{ background: rgba(255,255,255,0.1); border-radius: 8px; padding: 10px; }}
.stat-label {{ font-size: 12px; opacity: 0.6; margin-bottom: 4px; }}
.stat-value {{ font-size: 16px; font-weight: 500; }}

/* Indicator Table */
.indicator-row {{ display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid #f5f5f5; gap: 12px; }}
.indicator-row:last-child {{ border-bottom: none; }}
.ind-name {{ width: 80px; font-weight: 500; color: #666; font-size: 14px; }}
.ind-value {{ width: 160px; font-size: 13px; color: #888; font-family: 'SF Mono', monospace; }}
.ind-status {{ width: 80px; font-size: 13px; font-weight: 600; }}
.ind-desc {{ flex: 1; font-size: 13px; color: #555; }}
.status-red {{ color: #DC143C; }}
.status-green {{ color: #008000; }}
.status-orange {{ color: #FF8C00; }}
.status-gray {{ color: #888; }}

/* Score */
.score-circle {{ width: 100px; height: 100px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 0 auto 16px; border: 4px solid; }}
.score-num {{ font-size: 32px; font-weight: bold; }}
.score-label {{ font-size: 12px; margin-top: 2px; }}
.score-section {{ text-align: center; }}

/* Trend */
.trend-row {{ display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid #f5f5f5; }}
.trend-row:last-child {{ border-bottom: none; }}
.trend-label {{ width: 100px; font-weight: 500; }}
.trend-result {{ flex: 1; }}

/* Signals */
.signal-item {{ display: flex; align-items: flex-start; padding: 8px 0; gap: 10px; border-bottom: 1px solid #f8f8f8; }}
.signal-item:last-child {{ border-bottom: none; }}
.signal-date {{ width: 90px; font-size: 12px; color: #999; }}
.signal-type {{ width: 80px; font-size: 13px; font-weight: 500; }}
.signal-desc {{ flex: 1; font-size: 13px; color: #555; }}

/* Advice */
.advice-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }}
.advice-box {{ background: #f8f9fa; border-radius: 8px; padding: 14px; }}
.advice-box h4 {{ font-size: 13px; color: #666; margin-bottom: 6px; }}
.advice-box p {{ font-size: 14px; color: #333; }}
.price-levels {{ display: flex; gap: 24px; flex-wrap: wrap; }}
.level-group {{ flex: 1; min-width: 200px; }}
.level-group h4 {{ font-size: 13px; color: #666; margin-bottom: 6px; }}
.level-tag {{ display: inline-block; background: #f0f2f5; padding: 4px 10px; border-radius: 4px; font-size: 13px; margin: 2px 4px 2px 0; }}
.risk-tag {{ display: inline-block; background: #fff3e0; color: #e65100; padding: 4px 10px; border-radius: 4px; font-size: 12px; margin: 2px 4px 2px 0; }}

/* Strategy Card */
.key-info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; margin-bottom: 16px; }}
.key-info-item {{ background: #f8f9fa; border-radius: 8px; padding: 10px; text-align: center; }}
.key-info-label {{ font-size: 11px; color: #999; margin-bottom: 4px; }}
.key-info-value {{ font-size: 15px; font-weight: 600; }}
.strategy-section {{ margin-bottom: 16px; }}
.strategy-section h4 {{ font-size: 13px; color: #666; margin-bottom: 8px; font-weight: 600; }}
.price-level-row {{ display: flex; gap: 16px; margin-bottom: 8px; flex-wrap: wrap; }}
.level-tag-red {{ display: inline-block; background: #ffebee; color: #DC143C; padding: 3px 10px; border-radius: 4px; font-size: 13px; margin-right: 4px; }}
.level-tag-green {{ display: inline-block; background: #e8f5e9; color: #008000; padding: 3px 10px; border-radius: 4px; font-size: 13px; margin-right: 4px; }}
.advice-line {{ font-size: 14px; color: #333; margin-bottom: 6px; padding-left: 12px; border-left: 3px solid #4a90d9; }}
.core-logic {{ background: linear-gradient(135deg, #f0f4ff, #f8f9fa); border-radius: 8px; padding: 14px; font-size: 14px; color: #444; line-height: 1.7; }}
.core-logic strong {{ color: #1a1a2e; }}

/* Footer */
.footer {{ text-align: center; padding: 16px; color: #999; font-size: 12px; }}

@media (max-width: 600px) {{
    .price {{ font-size: 28px; }}
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .advice-grid {{ grid-template-columns: 1fr; }}
    .indicator-row {{ flex-wrap: wrap; }}
    .ind-value {{ width: 100%; order: 3; }}
}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
    <h1>{sym}</h1>
    <div class="date">{date_str} 收盘分析</div>
    <div class="price-row">
        <span class="price" style="color: {chg_color}">{close:.2f}</span>
        <span class="chg" style="color: {chg_color}">{chg_arrow} {chg_sign}{price_chg:.2f} ({chg_sign}{price_pct:.2f}%)</span>
    </div>
    <div class="stats-grid">
        <div class="stat-item">
            <div class="stat-label">成交量</div>
            <div class="stat-value">{vol_str}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">20日最高</div>
            <div class="stat-value">{high_20:.2f}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">20日最低</div>
            <div class="stat-value">{low_20:.2f}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">MA20</div>
            <div class="stat-value">{self._get('sma20'):.2f}</div>
        </div>
    </div>
</div>

<!-- Score -->
<div class="card score-section">
    <h2>综合评分</h2>
    <div class="score-circle" style="border-color: {composite['level_color']}">
        <span class="score-num" style="color: {composite['level_color']}">{composite['score']}</span>
        <span class="score-label" style="color: {composite['level_color']}">{composite['level']}</span>
    </div>
</div>

<!-- Trading Strategy -->
<div class="card">
    <h2>交易策略</h2>

    <!-- Key Info -->
    <div class="key-info-grid">
        <div class="key-info-item">
            <div class="key-info-label">现价</div>
            <div class="key-info-value" style="color:{chg_color}">{strategy['key_info']['price']}</div>
            <div style="font-size:12px;color:{chg_color}">{strategy['key_info']['chg_pct']}</div>
        </div>
        <div class="key-info-item">
            <div class="key-info-label">今日最高</div>
            <div class="key-info-value">{strategy['key_info']['high']}</div>
        </div>
        <div class="key-info-item">
            <div class="key-info-label">今日最低</div>
            <div class="key-info-value">{strategy['key_info']['low']}</div>
        </div>
        <div class="key-info-item">
            <div class="key-info-label">盘口</div>
            <div class="key-info-value" style="color:{'#DC143C' if strategy['key_info']['bid_ask'] == '买盘占优' else '#008000' if strategy['key_info']['bid_ask'] == '卖盘占优' else '#888'}">{strategy['key_info']['bid_ask']}</div>
        </div>
        <div class="key-info-item">
            <div class="key-info-label">RSI</div>
            <div class="key-info-value">{strategy['key_info']['rsi']}</div>
            <div style="font-size:11px;color:{'#DC143C' if strategy['key_info']['rsi_status'] == '强势区' else '#008000' if strategy['key_info']['rsi_status'] == '弱势区' else '#888'}">{strategy['key_info']['rsi_status']}</div>
        </div>
        <div class="key-info-item">
            <div class="key-info-label">MACD</div>
            <div class="key-info-value" style="color:{'#DC143C' if strategy['key_info']['macd'] == '金叉' else '#008000' if strategy['key_info']['macd'] == '死叉' else '#888'}">{strategy['key_info']['macd']}</div>
        </div>
    </div>

    <!-- Strategy -->
    <div class="strategy-section">
        <h4>1. 关键价位</h4>
        <div class="price-level-row">
            <div>
                <span style="font-size:12px;color:#999;margin-right:8px">压力位:</span>
                {''.join(f'<span class="level-tag-red">{r}</span>' for r in strategy['strategy']['resistances'])}
            </div>
        </div>
        <div class="price-level-row">
            <div>
                <span style="font-size:12px;color:#999;margin-right:8px">支撑位:</span>
                {''.join(f'<span class="level-tag-green">{s}</span>' for s in strategy['strategy']['supports'])}
            </div>
        </div>
    </div>

    <div class="strategy-section">
        <h4>2. 操作建议</h4>
        <div class="advice-line"><strong>若已持有：</strong>{strategy['strategy']['holder_advice']}</div>
        <div class="advice-line" style="border-left-color:#008000"><strong>若未持有：</strong>{strategy['strategy']['watcher_advice']}</div>
    </div>

    <div class="strategy-section">
        <h4>3. 仓位建议</h4>
        <div class="advice-line" style="border-left-color:#FF8C00">{strategy['strategy']['position_advice']}</div>
    </div>

    <div class="strategy-section" style="margin-bottom:0">
        <h4>核心逻辑</h4>
        <div class="core-logic"><strong>综合研判：</strong>{strategy['core_logic']}</div>
    </div>
</div>

<!-- Indicators -->
<div class="card">
    <h2>技术指标解读</h2>
    {''.join(f"""
    <div class="indicator-row">
        <span class="ind-name">{ind['name']}</span>
        <span class="ind-value">{ind['value']}</span>
        <span class="ind-status status-{ind['status_color']}">{ind['status']}</span>
        <span class="ind-desc">{ind['desc']}</span>
    </div>""" for ind in indicators)}
</div>

<!-- Trend -->
<div class="card">
    <h2>多周期趋势评估</h2>
    <div class="trend-row">
        <span class="trend-label">短期(5-10日)</span>
        <span class="trend-result">{trend['short']['emoji']} <strong style="color: {'#DC143C' if trend['short']['score'] >= 4 else '#008000' if trend['short']['score'] <= 2 else '#888'}">{trend['short']['trend']}</strong> {stars(trend['short']['score'])}
        <div style="font-size:12px;color:#888;margin-top:4px">{trend['short']['desc']}</div>
        </span>
    </div>
    <div class="trend-row">
        <span class="trend-label">中期(20-60日)</span>
        <span class="trend-result">{trend['mid']['emoji']} <strong style="color: {'#DC143C' if trend['mid']['score'] >= 4 else '#008000' if trend['mid']['score'] <= 2 else '#888'}">{trend['mid']['trend']}</strong> {stars(trend['mid']['score'])}
        <div style="font-size:12px;color:#888;margin-top:4px">{trend['mid']['desc']}</div>
        </span>
    </div>
    <div class="trend-row">
        <span class="trend-label">长期(60日+)</span>
        <span class="trend-result">{trend['long']['emoji']} <strong style="color: {'#DC143C' if trend['long']['score'] >= 4 else '#008000' if trend['long']['score'] <= 2 else '#888'}">{trend['long']['trend']}</strong> {stars(trend['long']['score'])}
        <div style="font-size:12px;color:#888;margin-top:4px">{trend['long']['desc']}</div>
        </span>
    </div>
</div>

<!-- Signals -->
<div class="card">
    <h2>近期交易信号</h2>
    {"".join(f"""
    <div class="signal-item">
        <span class="signal-date">{s['date']}</span>
        <span class="signal-type">{s['icon']} {s['type']}</span>
        <span class="signal-desc">{s['desc']}</span>
    </div>""" for s in signals) if signals else '<div style="color:#999;padding:12px">近期无明显交易信号</div>'}
</div>

<!-- Support / Resistance -->
<div class="card">
    <h2>支撑与压力位</h2>
    <div class="price-levels">
        <div class="level-group">
            <h4 style="color:#DC143C">支撑位</h4>
            {''.join(f'<span class="level-tag">{s}</span>' for s in sr['supports'])}
        </div>
        <div class="level-group">
            <h4 style="color:#008000">压力位</h4>
            {''.join(f'<span class="level-tag">{r}</span>' for r in sr['resistances'])}
        </div>
    </div>
</div>

<!-- Advice -->
<div class="card">
    <h2>操作建议</h2>
    <div class="advice-grid">
        <div class="advice-box">
            <h4>持有者</h4>
            <p>{advice['holder']}</p>
        </div>
        <div class="advice-box">
            <h4>观望者</h4>
            <p>{advice['watcher']}</p>
        </div>
    </div>
    <div style="margin-top:12px">
        <h4 style="font-size:13px;color:#666;margin-bottom:6px">风险提示</h4>
        {''.join(f'<span class="risk-tag">{r}</span>' for r in advice['risks'])}
    </div>
</div>

<div class="footer">
    本报告由技术分析自动生成，仅供参考，不构成投资建议
    <br>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>

</div>
</body>
</html>"""

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return save_path
