"""
因子分析模块
"""
import pandas as pd
import numpy as np
from typing import Optional


class FactorAnalyzer:
    """因子分析类"""

    def __init__(self, df: pd.DataFrame):
        """
        初始化

        Args:
            df: 股票数据 DataFrame
        """
        self.df = df.copy()

    def calc_returns(self) -> pd.Series:
        """
        计算收益率

        Returns:
            收益率序列
        """
        close = self.df['close']
        returns = close.pct_change()
        return returns

    def calc_cum_returns(self) -> pd.Series:
        """
        计算累计收益

        Returns:
            累计收益序列
        """
        returns = self.calc_returns()
        cum_returns = (1 + returns).cumprod()
        return cum_returns

    def calc_volatility(self, window: int = 252) -> pd.Series:
        """
        计算波动率

        Args:
            window: 窗口大小 (年化)

        Returns:
            波动率序列
        """
        returns = self.calc_returns()
        volatility = returns.rolling(window=window).std() * np.sqrt(252)
        return volatility

    def calc_sharpe_ratio(self, window: int = 252, risk_free: float = 0.02) -> pd.Series:
        """
        计算夏普比率

        Args:
            window: 窗口大小
            risk_free: 无风险利率

        Returns:
            夏普比率序列
        """
        returns = self.calc_returns()
        excess_return = returns - risk_free / 252
        sharpe = excess_return.rolling(window=window).mean() / returns.rolling(window=window).std() * np.sqrt(252)
        return sharpe

    def calc_max_drawdown(self, window: int = 252) -> pd.Series:
        """
        计算最大回撤

        Args:
            window: 窗口大小

        Returns:
            最大回撤序列
        """
        cum_returns = self.calc_cum_returns()
        rolling_max = cum_returns.rolling(window=window, min_periods=1).max()
        drawdown = cum_returns / rolling_max - 1
        return drawdown

    def calc_beta(self, market_returns: pd.Series) -> float:
        """
        计算 beta 值

        Args:
            market_returns: 市场收益率序列

        Returns:
            beta 值
        """
        stock_returns = self.calc_returns()
        cov_matrix = np.cov(stock_returns, market_returns)
        beta = cov_matrix[0, 1] / cov_matrix[1, 1]
        return beta

    def calc_alpha(self, market_returns: pd.Series, risk_free: float = 0.02) -> float:
        """
        计算 alpha 值

        Args:
            market_returns: 市场收益率序列
            risk_free: 无风险利率

        Returns:
            alpha 值
        """
        beta = self.calc_beta(market_returns)
        stock_returns = self.calc_returns()
        market_excess = market_returns - risk_free / 252
        stock_excess = stock_returns - risk_free / 252

        alpha = stock_returns.mean() - (risk_free / 252 + beta * market_excess.mean())
        return alpha * 252  # 年化 alpha
