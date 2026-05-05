"""
市场数据获取
"""
import akshare as ak
import pandas as pd
from typing import Optional


class MarketData:
    """市场数据类"""

    def __init__(self):
        pass

    def _convert_to_english_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """将中文列名转换为英文"""
        if df.empty:
            return df

        # AKShare 常见的列名映射
        column_mapping = {
            '日期': 'date',
            '时间': 'time',
            '指数代码': 'code',
            '代码': 'code',
            '指数名称': 'name',
            '名称': 'name',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '涨跌幅': 'pct_change',
            '涨速': 'change_speed',
            '换手': 'turnover',
            ' turnover': 'turnover',
            '市盈率': 'pe_ratio',
            '市净率': 'pb_ratio',
        }

        new_columns = {}
        for col in df.columns:
            for chinese, english in column_mapping.items():
                if chinese in col:
                    new_columns[col] = english
                    break
            else:
                new_columns[col] = col

        df = df.rename(columns=new_columns)
        return df

    def get_index_list(self) -> pd.DataFrame:
        """
        获取指数列表

        Returns:
            指数列表 DataFrame
        """
        try:
            df = ak.index_stock_info()
            return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取指数列表失败: {e}")
            return pd.DataFrame()

    def get_index_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取指数日线数据

        Args:
            symbol: 指数代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            指数日线数据 DataFrame
        """
        try:
            df = ak.index_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date
            )
            return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取指数日线数据失败: {e}")
            return pd.DataFrame()

    def get_index_daily_tx(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取指数日线数据（英文列名）

        Args:
            symbol: 指数代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            指数日线数据 DataFrame (英文列名)
        """
        try:
            df = ak.index_zh_a_hist_tx(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )
            return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取指数日线数据失败: {e}")
            return pd.DataFrame()

    def get_market_board(self) -> pd.DataFrame:
        """
        获取行业板块

        Returns:
            板块数据 DataFrame
        """
        try:
            df = ak.stock_board_industry_name_em()
            return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取行业板块失败: {e}")
            return pd.DataFrame()

    def get_board_hist(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取板块历史数据

        Args:
            symbol: 板块名称
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            板块历史数据 DataFrame
        """
        try:
            df = ak.stock_board_industry_hist_em(symbol=symbol)
            return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取板块历史数据失败: {e}")
            return pd.DataFrame()

    def get_market_turnover(self) -> pd.DataFrame:
        """
        获取市场成交额

        Returns:
            成交额数据 DataFrame
        """
        try:
            df = ak.stock_market_view()
            return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取市场成交额失败: {e}")
            return pd.DataFrame()

    def get_margin_trading(self, symbol: str = "sh") -> pd.DataFrame:
        """
        获取融资融券数据

        Args:
            symbol: 市场标识 (sh, sz, szrs)

        Returns:
            融资融券数据 DataFrame
        """
        try:
            df = ak.stock_margin_trading_balance_em(symbol=symbol)
            return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取融资融券数据失败: {e}")
            return pd.DataFrame()
