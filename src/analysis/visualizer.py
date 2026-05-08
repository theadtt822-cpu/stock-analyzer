"""
市场数据可视化
"""
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import mplfinance as mpf
from typing import Optional
import os

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 设置样式
sns.set_style("whitegrid")
sns.set_palette("deep")


class Visualizer:
    """可视化类"""

    def __init__(self):
        pass

    def plot_price(self, df: pd.DataFrame, symbol: str = ""):
        """
        绘制价格走势

        Args:
            df: 数据 DataFrame
            symbol: 股票代码
        """
        plt.figure(figsize=(12, 6))
        if 'date' in df.columns:
            plt.plot(df['date'], df['close'])
        else:
            plt.plot(df['close'])

        plt.title(f"{' '.join(symbol)} 股价走势" if symbol else "股价走势")
        plt.xlabel("日期")
        plt.ylabel("价格")
        plt.tight_layout()
        plt.show()

    def plot_candlestick_with_volume(self, df: pd.DataFrame, symbol: str = "", save_path: str = None):
        """
        绘制专业K线图 + 成交量

        Args:
            df: 数据 DataFrame (需要包含: date, open, high, low, close, volume)
            symbol: 股票代码
            save_path: 保存路径，如果不提供则显示
        """
        # 确保 date 是 datetime 类型并设置为索引
        df_plot = df.copy()
        if 'date' in df_plot.columns:
            df_plot['date'] = pd.to_datetime(df_plot['date'])
            df_plot = df_plot.set_index('date')

        # 定义样式
        mc = mpf.make_marketcolors(
            up='red',      # 涨 - 红色
            down='green',  # 跌 - 绿色
            inherit=True
        )
        s = mpf.make_mpf_style(
            marketcolors=mc,
            style_name='classic'
        )

        # 创建副图（成交量）
        volume_panel = 1

        # 绘制K线图
        fig, axes = mpf.plot(
            df_plot,
            type='candle',
            volume=True,
            returnfig=True,
            style=s,
            figratio=(16, 9),
            title=f'\n{symbol} - 股价与成交量' if symbol else '\n股价与成交量',
            ylabel='价格',
            ylabel_lower='成交量'
        )

        # 添加均线（如果有）
        if 'sma5' in df_plot.columns:
            ax = axes[0]
            ax.plot(df_plot.index, df_plot['sma5'], label='SMA5', alpha=0.7)
            ax.legend()

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def plot_candlestick(self, df: pd.DataFrame, symbol: str = "", n: int = 20):
        """
        绘制K线图

        Args:
            df: 数据 DataFrame
            symbol: 股票代码
            n: 显示最近 n 根 K线
        """
        plt.figure(figsize=(14, 8))

        # 只显示最近 n 根
        df_plot = df.tail(n).copy()

        # 成交额颜色
        colors = ['red' if row['close'] > row['open'] else 'green' for _, row in df_plot.iterrows()]

        # 绘制K线
        for i, (_, row) in enumerate(df_plot.iterrows()):
            # 实体
            plt.Rectangle((i-0.2, min(row['open'], row['close'])), 0.4,
                         abs(row['close']-row['open']),
                         facecolor=colors[i], edgecolor='black')
            # 上影线
            plt.plot([i, i], [row['low'], row['high']], color='black')

        plt.title(f"{' '.join(symbol)} K线图 (最近{n}根)" if symbol else f"K线图 (最近{n}根)")
        plt.xlabel("日期")
        plt.ylabel("价格")
        plt.xticks(range(n), df_plot['date'].dt.strftime('%m-%d') if 'date' in df_plot.columns else range(n))
        plt.tight_layout()
        plt.show()

    def plot_indicator(self, df: pd.DataFrame, symbol: str = ""):
        """
        绘制技术指标

        Args:
            df: 数据 DataFrame
            symbol: 股票代码
        """
        fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

        # 价格和均线
        if 'date' in df.columns:
            axes[0].plot(df['date'], df['close'], label='收盘价', alpha=0.8)
            if 'sma5' in df.columns:
                axes[0].plot(df['date'], df['sma5'], label='SMA5', alpha=0.8)
            if 'sma10' in df.columns:
                axes[0].plot(df['date'], df['sma10'], label='SMA10', alpha=0.8)
            axes[0].set_ylabel("价格")
            axes[0].legend()
        else:
            axes[0].plot(df['close'], label='收盘价', alpha=0.8)
            axes[0].set_ylabel("价格")
            axes[0].legend()

        axes[0].set_title(f"{' '.join(symbol)} 技术指标" if symbol else "技术指标")

        # MACD
        if 'macd' in df.columns:
            axes[1].bar(df['date'] if 'date' in df.columns else df.index,
                       df['macd'], label='MACD', alpha=0.7)
            if 'dif' in df.columns and 'dea' in df.columns:
                axes[1].plot(df['date'] if 'date' in df.columns else df.index,
                            df['dif'], label='DIF', alpha=0.8)
                axes[1].plot(df['date'] if 'date' in df.columns else df.index,
                            df['dea'], label='DEA', alpha=0.8)
            axes[1].set_ylabel("MACD")
            axes[1].legend()

        # RSI
        if 'rsi' in df.columns:
            axes[2].plot(df['date'] if 'date' in df.columns else df.index,
                        df['rsi'], label='RSI', alpha=0.8)
            axes[2].axhline(y=70, color='red', linestyle='--', alpha=0.5)
            axes[2].axhline(y=30, color='green', linestyle='--', alpha=0.5)
            axes[2].set_ylabel("RSI")
            axes[2].set_xlabel("日期")
            axes[2].legend()

        plt.tight_layout()
        plt.show()

    def plot_price_with_ma(self, df: pd.DataFrame, symbol: str = ""):
        """价格与移动平均线"""
        plt.figure(figsize=(14, 8))

        if 'date' in df.columns:
            plt.plot(df['date'], df['close'], label='收盘价', linewidth=1.5, color='blue')
            if 'sma5' in df.columns:
                plt.plot(df['date'], df['sma5'], label='SMA5', alpha=0.8)
            if 'sma10' in df.columns:
                plt.plot(df['date'], df['sma10'], label='SMA10', alpha=0.8)
            if 'sma20' in df.columns:
                plt.plot(df['date'], df['sma20'], label='SMA20', alpha=0.8)
            if 'sma60' in df.columns:
                plt.plot(df['date'], df['sma60'], label='SMA60', alpha=0.8)
            plt.xlabel("日期")
        else:
            plt.plot(df['close'], label='收盘价', linewidth=1.5, color='blue')
            if 'sma5' in df.columns:
                plt.plot(df['sma5'], label='SMA5', alpha=0.8)
            if 'sma10' in df.columns:
                plt.plot(df['sma10'], label='SMA10', alpha=0.8)
            if 'sma20' in df.columns:
                plt.plot(df['sma20'], label='SMA20', alpha=0.8)
            if 'sma60' in df.columns:
                plt.plot(df['sma60'], label='SMA60', alpha=0.8)

        plt.title(f"{symbol} - 股价与移动平均线" if symbol else "股价与移动平均线")
        plt.ylabel("价格")
        plt.legend()
        plt.tight_layout()
        plt.show()

    def plot_macd(self, df: pd.DataFrame, symbol: str = ""):
        """MACD指标"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

        # MACD线
        if 'date' in df.columns:
            ax1.plot(df['date'], df['dif'], label='DIF', color='red', alpha=0.8)
            ax1.plot(df['date'], df['dea'], label='DEA', color='blue', alpha=0.8)
            ax1.fill_between(df['date'], df['macd'], 0, alpha=0.3, label='MACD', color='gray')
            ax1.axhline(0, color='black', linestyle='-', linewidth=0.5)
            ax1.set_ylabel("MACD")
            ax1.legend()
        else:
            ax1.plot(df['dif'], label='DIF', color='red', alpha=0.8)
            ax1.plot(df['dea'], label='DEA', color='blue', alpha=0.8)
            ax1.fill_between(df.index, df['macd'], 0, alpha=0.3, label='MACD', color='gray')
            ax1.axhline(0, color='black', linestyle='-', linewidth=0.5)
            ax1.set_ylabel("MACD")
            ax1.legend()

        # 柱状图
        colors = ['red' if x > 0 else 'green' for x in df['macd']]
        ax2.bar(df['date'] if 'date' in df.columns else df.index,
                df['macd'], color=colors, alpha=0.7, label='MACD柱')
        ax2.axhline(0, color='black', linestyle='-', linewidth=0.5)
        ax2.set_ylabel("MACD柱")
        ax2.set_xlabel("日期" if 'date' in df.columns else "Index")
        ax2.legend()

        plt.suptitle(f"{symbol} - MACD指标" if symbol else "MACD指标")
        plt.tight_layout()
        plt.show()

    def plot_rsi(self, df: pd.DataFrame, symbol: str = ""):
        """RSI指标"""
        plt.figure(figsize=(14, 6))

        if 'date' in df.columns:
            plt.plot(df['date'], df['rsi'], label='RSI', color='purple', alpha=0.8)
        else:
            plt.plot(df['rsi'], label='RSI', color='purple', alpha=0.8)

        plt.axhline(y=70, color='red', linestyle='--', alpha=0.5, label='超买(70)')
        plt.axhline(y=30, color='green', linestyle='--', alpha=0.5, label='超卖(30)')
        plt.axhline(y=50, color='gray', linestyle='-', alpha=0.3)

        plt.fill_between(df['date'] if 'date' in df.columns else df.index,
                        70, 30, alpha=0.1, color='gray')
        plt.ylabel("RSI")
        plt.ylim(0, 100)
        plt.legend()
        plt.title(f"{symbol} - RSI指标" if symbol else "RSI指标")
        plt.tight_layout()
        plt.show()

    def plot_boll(self, df: pd.DataFrame, symbol: str = ""):
        """布林带"""
        plt.figure(figsize=(14, 8))

        if 'date' in df.columns:
            plt.plot(df['date'], df['close'], label='收盘价', color='blue', linewidth=1.5)
            plt.plot(df['date'], df['upper'], label='上轨', color='red', alpha=0.7)
            plt.plot(df['date'], df['middle'], label='中轨', color='orange', alpha=0.7)
            plt.plot(df['date'], df['lower'], label='下轨', color='green', alpha=0.7)
            plt.fill_between(df['date'], df['upper'], df['lower'], alpha=0.1, color='gray')
        else:
            plt.plot(df['close'], label='收盘价', color='blue', linewidth=1.5)
            plt.plot(df['upper'], label='上轨', color='red', alpha=0.7)
            plt.plot(df['middle'], label='中轨', color='orange', alpha=0.7)
            plt.plot(df['lower'], label='下轨', color='green', alpha=0.7)
            plt.fill_between(df.index, df['upper'], df['lower'], alpha=0.1, color='gray')

        plt.title(f"{symbol} - 布林带" if symbol else "布林带")
        plt.ylabel("价格")
        plt.legend()
        plt.tight_layout()
        plt.show()

    def plot_kdj(self, df: pd.DataFrame, symbol: str = ""):
        """KDJ指标"""
        plt.figure(figsize=(14, 6))

        if 'date' in df.columns:
            plt.plot(df['date'], df['k'], label='K', color='red', alpha=0.8)
            plt.plot(df['date'], df['d'], label='D', color='blue', alpha=0.8)
            plt.plot(df['date'], df['j'], label='J', color='purple', alpha=0.8)
        else:
            plt.plot(df['k'], label='K', color='red', alpha=0.8)
            plt.plot(df['d'], label='D', color='blue', alpha=0.8)
            plt.plot(df['j'], label='J', color=' purple', alpha=0.8)

        plt.axhline(y=80, color='red', linestyle='--', alpha=0.5)
        plt.axhline(y=20, color='green', linestyle='--', alpha=0.5)
        plt.ylabel("KDJ")
        plt.ylim(-5, 105)
        plt.legend()
        plt.title(f"{symbol} - KDJ指标" if symbol else "KDJ指标")
        plt.tight_layout()
        plt.show()

    def plot_atr(self, df: pd.DataFrame, symbol: str = ""):
        """ATR指标"""
        plt.figure(figsize=(14, 6))

        if 'date' in df.columns:
            plt.plot(df['date'], df['atr'], label='ATR', color='orange', alpha=0.8)
        else:
            plt.plot(df['atr'], label='ATR', color='orange', alpha=0.8)

        plt.ylabel("ATR")
        plt.legend()
        plt.title(f"{symbol} - 真实波动幅度均值(ATR)" if symbol else "真实波动幅度均值(ATR)")
        plt.tight_layout()
        plt.show()

    def plot_combined(self, df: pd.DataFrame, symbol: str = ""):
        """综合指标页"""
        fig = plt.figure(figsize=(16, 10))

        # 子图1: 价格和均线
        ax1 = plt.subplot(3, 2, 1)
        if 'date' in df.columns:
            ax1.plot(df['date'], df['close'], label='收盘价', linewidth=1.5)
            if 'sma20' in df.columns:
                ax1.plot(df['date'], df['sma20'], label='SMA20', alpha=0.7)
        else:
            ax1.plot(df['close'], label='收盘价', linewidth=1.5)
            if 'sma20' in df.columns:
                ax1.plot(df['sma20'], label='SMA20', alpha=0.7)
        ax1.set_ylabel("价格")
        ax1.legend()
        ax1.set_title("价格与20日均线")

        # 子图2: MACD
        ax2 = plt.subplot(3, 2, 2)
        if 'date' in df.columns:
            ax2.plot(df['date'], df['dif'], label='DIF', color='red', alpha=0.8)
            ax2.plot(df['date'], df['dea'], label='DEA', color='blue', alpha=0.8)
            ax2.fill_between(df['date'], df['macd'], 0, alpha=0.3, color='gray')
            ax2.axhline(0, color='black', linestyle='-', linewidth=0.5)
        else:
            ax2.plot(df['dif'], label='DIF', color='red', alpha=0.8)
            ax2.plot(df['dea'], label='DEA', color='blue', alpha=0.8)
            ax2.fill_between(df.index, df['macd'], 0, alpha=0.3, color='gray')
            ax2.axhline(0, color='black', linestyle='-', linewidth=0.5)
        ax2.set_ylabel("MACD")
        ax2.legend()
        ax2.set_title("MACD指标")

        # 子图3: RSI
        ax3 = plt.subplot(3, 2, 3)
        if 'date' in df.columns:
            ax3.plot(df['date'], df['rsi'], label='RSI', color='purple', alpha=0.8)
        else:
            ax3.plot(df['rsi'], label='RSI', color='purple', alpha=0.8)
        ax3.axhline(y=70, color='red', linestyle='--', alpha=0.5)
        ax3.axhline(y=30, color='green', linestyle='--', alpha=0.5)
        ax3.set_ylabel("RSI")
        ax3.set_ylim(0, 100)
        ax3.legend()
        ax3.set_title("RSI指标")

        # 子图4: 布林带
        ax4 = plt.subplot(3, 2, 4)
        if 'date' in df.columns:
            ax4.plot(df['date'], df['close'], color='blue', linewidth=1.5)
            ax4.plot(df['date'], df['upper'], color='red', alpha=0.7)
            ax4.plot(df['date'], df['middle'], color='orange', alpha=0.7)
            ax4.plot(df['date'], df['lower'], color='green', alpha=0.7)
            ax4.fill_between(df['date'], df['upper'], df['lower'], alpha=0.1)
        else:
            ax4.plot(df['close'], color='blue', linewidth=1.5)
            ax4.plot(df['upper'], color='red', alpha=0.7)
            ax4.plot(df['middle'], color='orange', alpha=0.7)
            ax4.plot(df['lower'], color='green', alpha=0.7)
            ax4.fill_between(df.index, df['upper'], df['lower'], alpha=0.1)
        ax4.set_ylabel("价格")
        ax4.set_title("布林带")

        # 子图5: KDJ
        ax5 = plt.subplot(3, 2, 5)
        if 'date' in df.columns:
            ax5.plot(df['date'], df['k'], label='K', color='red', alpha=0.8)
            ax5.plot(df['date'], df['d'], label='D', color='blue', alpha=0.8)
            ax5.plot(df['date'], df['j'], label='J', color='purple', alpha=0.8)
        else:
            ax5.plot(df['k'], label='K', color='red', alpha=0.8)
            ax5.plot(df['d'], label='D', color='blue', alpha=0.8)
            ax5.plot(df['j'], label='J', color='purple', alpha=0.8)
        ax5.axhline(y=80, color='red', linestyle='--', alpha=0.5)
        ax5.axhline(y=20, color='green', linestyle='--', alpha=0.5)
        ax5.set_ylabel("KDJ")
        ax5.set_ylim(-5, 105)
        ax5.legend()
        ax5.set_title("KDJ指标")

        # 子图6: ATR
        ax6 = plt.subplot(3, 2, 6)
        if 'date' in df.columns:
            ax6.plot(df['date'], df['atr'], label='ATR', color='orange', alpha=0.8)
        else:
            ax6.plot(df['atr'], label='ATR', color='orange', alpha=0.8)
        ax6.set_ylabel("ATR")
        ax6.legend()
        ax6.set_title("真实波动幅度均值(ATR)")

        plt.suptitle(f"{symbol} - 综合技术指标分析" if symbol else "综合技术指标分析", fontsize=14, y=0.995)
        plt.tight_layout()
        plt.show()

    def plot_analysis_report(self, df: pd.DataFrame, symbol: str = "", save_path: str = None):
        """
        创建综合分析报告（完整的6子图 + 数据面板）

        Args:
            df: 数据 DataFrame
            symbol: 股票名称
            save_path: 保存路径
        """
        # 计算最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else df.iloc[0]
        price_change = latest['close'] - prev['close']
        price_pct = (price_change / prev['close']) * 100

        # 20日最高最低
        high_20 = df['high'].tail(20).max()
        low_20 = df['low'].tail(20).min()

        # MACD状态
        macd_latest = latest.get('macd', 0)
        macd_prev = prev.get('macd', 0)
        if macd_latest > 0 and macd_prev > 0 and macd_latest > macd_prev:
            macd_status = "多方放大（多头趋势）"
        elif macd_latest > 0 and macd_prev > 0:
            macd_status = "多方减弱（多头减弱）"
        elif macd_latest < 0 and macd_prev < 0 and macd_latest < macd_prev:
            macd_status = "空方放大（空头趋势）"
        else:
            macd_status = "空方减弱（空头减弱）"

        # RSI状态
        rsi_latest = latest.get('rsi', 50)
        if rsi_latest > 70:
            rsi_status = "超买区域"
        elif rsi_latest > 60:
            rsi_status = "偏强区域"
        elif rsi_latest < 30:
            rsi_status = "超卖区域"
        elif rsi_latest < 40:
            rsi_status = "偏弱区域"
        else:
            rsi_status = "中性区域"

        fig = plt.figure(figsize=(18, 12))
        fig.suptitle(f'{symbol} - 技术分析报告', fontsize=16, fontweight='bold', y=0.995)

        # 子图1: K线图 + 成交量 (手动绘制)
        ax1 = plt.subplot(3, 2, 1)

        # 准备数据
        df_plot = df.tail(60).copy()
        if 'date' in df_plot.columns:
            df_plot['date'] = pd.to_datetime(df_plot['date'])
            dates = df_plot['date']
        else:
            dates = df_plot.index

        from matplotlib.patches import Rectangle

        # K线图
        candle_colors = ['red' if row['close'] > row['open'] else 'green' for _, row in df_plot.iterrows()]
        for i, (_, row) in enumerate(df_plot.iterrows()):
            # 实体
            ax1.add_patch(Rectangle((i-0.2, min(row['open'], row['close'])), 0.4,
                         abs(row['close']-row['open']),
                         facecolor=candle_colors[i], edgecolor='black', alpha=0.8))
            # 上下影线
            ax1.plot([i, i], [row['low'], row['high']], color='black', linewidth=1)

        # 添加均线
        if 'sma20' in df_plot.columns:
            ax1.plot(range(len(df_plot)), df_plot['sma20'], label='SMA20', color='orange', alpha=0.8)

        ax1.set_ylabel("价格")
        ax1.set_title(f"{symbol} - K线图")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 设置x轴标签
        step = max(1, len(df_plot) // 10)
        ax1.set_xticks(range(0, len(df_plot), step))
        ax1.set_xticklabels([str(dates.iloc[i].strftime('%m-%d')) for i in range(0, len(df_plot), step)], rotation=45)

        # 成交量子图
        ax1_v = ax1.twinx()
        ax1_v.bar(range(len(df_plot)), df_plot['volume'], color='gray', alpha=0.3, width=0.8)
        ax1_v.set_ylabel("成交量")
        ax1_v.grid(False)

        # 子图2: MACD
        ax2 = plt.subplot(3, 2, 2)
        if 'date' in df.columns:
            ax2.plot(df['date'], df['dif'], label='DIF', color='red', alpha=0.8)
            ax2.plot(df['date'], df['dea'], label='DEA', color='blue', alpha=0.8)
            colors = ['red' if x > 0 else 'green' for x in df['macd']]
            ax2.bar(df['date'], df['macd'], color=colors, alpha=0.5, label='MACD柱')
            ax2.axhline(0, color='black', linestyle='-', linewidth=0.5)
            ax2.set_ylabel("MACD")
            ax2.legend()
            ax2.tick_params(axis='x', rotation=45)
        else:
            ax2.plot(df['dif'], label='DIF', color='red', alpha=0.8)
            ax2.plot(df['dea'], label='DEA', color='blue', alpha=0.8)
            colors = ['red' if x > 0 else 'green' for x in df['macd']]
            ax2.bar(df.index, df['macd'], color=colors, alpha=0.5, label='MACD柱')
            ax2.axhline(0, color='black', linestyle='-', linewidth=0.5)
            ax2.set_ylabel("MACD")
            ax2.legend()
        ax2.set_title("MACD指标")
        ax2.grid(True, alpha=0.3)

        # 子图3: RSI
        ax3 = plt.subplot(3, 2, 3)
        if 'date' in df.columns:
            ax3.plot(df['date'], df['rsi'], label='RSI', color='purple', alpha=0.8)
            ax3.fill_between(df['date'], 70, 30, alpha=0.1, color='gray')
        else:
            ax3.plot(df['rsi'], label='RSI', color='purple', alpha=0.8)
            ax3.fill_between(df.index, 70, 30, alpha=0.1, color='gray')
        ax3.axhline(y=70, color='red', linestyle='--', alpha=0.5)
        ax3.axhline(y=30, color='green', linestyle='--', alpha=0.5)
        ax3.axhline(y=50, color='gray', linestyle='-', alpha=0.3)
        ax3.set_ylabel("RSI")
        ax3.set_ylim(0, 100)
        ax3.legend()
        ax3.set_title("RSI指标 (当前: {:.1f} - {})".format(rsi_latest, rsi_status))
        ax3.grid(True, alpha=0.3)

        # 子图4: 布林带
        ax4 = plt.subplot(3, 2, 4)
        if 'date' in df.columns:
            ax4.plot(df['date'], df['close'], label='收盘价', color='blue', linewidth=1.5)
            ax4.plot(df['date'], df['upper'], label='上轨', color='red', alpha=0.7)
            ax4.plot(df['date'], df['middle'], label='中轨', color='orange', alpha=0.7)
            ax4.plot(df['date'], df['lower'], label='下轨', color='green', alpha=0.7)
            ax4.fill_between(df['date'], df['upper'], df['lower'], alpha=0.1)
        else:
            ax4.plot(df['close'], label='收盘价', color='blue', linewidth=1.5)
            ax4.plot(df['upper'], label='上轨', color='red', alpha=0.7)
            ax4.plot(df['middle'], label='中轨', color='orange', alpha=0.7)
            ax4.plot(df['lower'], label='下轨', color='green', alpha=0.7)
            ax4.fill_between(df.index, df['upper'], df['lower'], alpha=0.1)
        ax4.set_ylabel("价格")
        ax4.legend()
        ax4.set_title("布林带")
        ax4.grid(True, alpha=0.3)

        # 子图5: KDJ
        ax5 = plt.subplot(3, 2, 5)
        if 'date' in df.columns:
            ax5.plot(df['date'], df['k'], label='K', color='red', alpha=0.8)
            ax5.plot(df['date'], df['d'], label='D', color='blue', alpha=0.8)
            ax5.plot(df['date'], df['j'], label='J', color='purple', alpha=0.8)
        else:
            ax5.plot(df['k'], label='K', color='red', alpha=0.8)
            ax5.plot(df['d'], label='D', color='blue', alpha=0.8)
            ax5.plot(df['j'], label='J', color='purple', alpha=0.8)
        ax5.axhline(y=80, color='red', linestyle='--', alpha=0.5)
        ax5.axhline(y=20, color='green', linestyle='--', alpha=0.5)
        ax5.set_ylabel("KDJ")
        ax5.set_ylim(-5, 105)
        ax5.legend()
        ax5.set_title("KDJ指标")
        ax5.grid(True, alpha=0.3)

        # 子图6: ATR
        ax6 = plt.subplot(3, 2, 6)
        if 'date' in df.columns:
            ax6.plot(df['date'], df['atr'], label='ATR', color='orange', alpha=0.8)
        else:
            ax6.plot(df['atr'], label='ATR', color='orange', alpha=0.8)
        ax6.set_ylabel("ATR")
        ax6.legend()
        ax6.set_title("真实波动幅度均值(ATR)")
        ax6.grid(True, alpha=0.3)

        # 添加数据面板
        panel_text = f"""
股票分析信息面板
{'='*35}
当前价格: {latest['close']:.2f} ({price_change:+.2f}, {price_pct:+.2f}%)
20日最高: {high_20:.2f}
20日最低: {low_20:.2f}
成交量: {latest.get('volume', latest.get('amount', 0)):,.0f} 手
MACD状态: {macd_status}
RSI状态: {rsi_status}
SMA20: {latest.get('sma20', 0):.2f}
        """
        # 移除空行并格式化
        panel_lines = [line.strip() for line in panel_text.strip().split('\n') if line.strip()]

        plt.figtext(0.02, 0.02, '\n'.join(panel_lines),
                   fontsize=9, family='monospace',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()
        plt.subplots_adjust(top=0.97, bottom=0.12)

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def plot_correlation(self, df_dict: dict, method: str = 'pearson'):
        """
        绘制相关性热力图

        Args:
            df_dict: {名称: DataFrame} 字典
            method: 相关性计算方法
        """
        # 合并数据
        combined = pd.DataFrame()
        for name, df in df_dict.items():
            if 'close' in df.columns:
                combined[name] = df['close']

        # 计算相关性
        corr = combined.pct_change().corr(method=method)

        # 绘制热力图
        plt.figure(figsize=(10, 8))
        sns.heatmap(corr, annot=True, cmap='RdYlBu', center=0,
                   square=True, linewidths=0.5)
        plt.title("相关性热力图")
        plt.tight_layout()
        plt.show()
