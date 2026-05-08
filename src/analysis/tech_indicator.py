"""
技术指标计算
"""
import pandas as pd
import numpy as np
from typing import Optional


class TechIndicator:
    """技术指标类"""

    def __init__(self, df: pd.DataFrame):
        """
        初始化

        Args:
            df: 包含 open, high, low, close, volume 字段的 DataFrame
        """
        self.df = df.copy()
        self._ensure_columns()

    def _ensure_columns(self):
        """确保必要的列存在"""
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in self.df.columns:
                raise ValueError(f"缺少必要列: {col}")

    def calc_sma(self, window: int = 5) -> pd.Series:
        """
        计算简单移动平均线

        Args:
            window: 窗口大小

        Returns:
            SMA 序列
        """
        return self.df['close'].rolling(window=window).mean()

    def calc_ema(self, window: int = 12) -> pd.Series:
        """
        计算指数移动平均线

        Args:
            window: 窗口大小

        Returns:
            EMA 序列
        """
        return self.df['close'].ewm(span=window, adjust=False).mean()

    def calc_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """
        计算 MACD 指标

        Args:
            fast: 快线窗口
            slow: 慢线窗口
            signal: 信号线窗口

        Returns:
            包含 dif, dea, macd 的字典
        """
        ema_fast = self.df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = self.df['close'].ewm(span=slow, adjust=False).mean()

        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd = (dif - dea) * 2

        return {
            'dif': dif,
            'dea': dea,
            'macd': macd
        }

    def calc_rsi(self, window: int = 14) -> pd.Series:
        """
        计算 RSI 指标

        Args:
            window: 窗口大小

        Returns:
            RSI 序列
        """
        delta = self.df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calc_boll(self, window: int = 20, std: float = 2) -> dict:
        """
        计算布林带指标

        Args:
            window: 窗口大小
            std: 标准差倍数

        Returns:
            包含 upper, middle, lower 的字典
        """
        middle = self.df['close'].rolling(window=window).mean()
        std_dev = self.df['close'].rolling(window=window).std()

        upper = middle + std_dev * std
        lower = middle - std_dev * std

        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }

    def calc_kdj(self, n: int = 9) -> dict:
        """
        计算 KDJ 指标

        Args:
            n: 窗口大小

        Returns:
            包含 k, d, j 的字典
        """
        low_list = self.df['low'].rolling(n).min()
        high_list = self.df['high'].rolling(n).max()

        rsv = (self.df['close'] - low_list) / (high_list - low_list) * 100

        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d

        return {
            'k': k,
            'd': d,
            'j': j
        }

    def calc_atr(self, window: int = 14) -> pd.Series:
        """
        计算真实波动幅度均值

        Args:
            window: 窗口大小

        Returns:
            ATR 序列
        """
        high = self.df['high']
        low = self.df['low']
        close = self.df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
        atr = tr.rolling(window=window).mean()

        return atr
