"""
股票数据获取
"""
import akshare as ak
import pandas as pd
from typing import Optional
from datetime import datetime


class StockData:
    """股票数据类"""

    def __init__(self):
        pass

    def get_stock_info(self, symbol: str) -> pd.DataFrame:
        """
        获取股票基本信息

        Args:
            symbol: 股票代码 (如: sh600000)

        Returns:
            股票基本信息 DataFrame
        """
        try:
            df = ak.stock_individual_info_em(symbol=symbol)
            return df
        except Exception as e:
            print(f"获取股票信息失败: {e}")
            return pd.DataFrame()

    def _convert_to_english_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """将中文列名转换为英文"""
        if df.empty:
            return df

        # AKShare 常见的列名映射
        column_mapping = {
            '日期': 'date',
            '日期': 'date',
            '时间': 'time',
            '股票代码': 'code',
            '代码': 'code',
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
        has_amount = False
        for col in df.columns:
            for chinese, english in column_mapping.items():
                if chinese in col:
                    new_columns[col] = english
                    if english == 'amount':
                        has_amount = True
                    break
            else:
                new_columns[col] = col

        # 特殊处理：如果只有 amount 没有 volume，把 amount 重命名为 volume
        if has_amount and 'volume' not in new_columns.values():
            for old_col, new_col in list(new_columns.items()):
                if new_col == 'amount':
                    new_columns[old_col] = 'volume'
                    break

        df = df.rename(columns=new_columns)
        return df

    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取股票日线数据

        Args:
            symbol: 股票代码 (支持 sh600519 或 600519 格式)
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            日线数据 DataFrame (英文列名: date, open, close, high, low, amount)
        """
        try:
            # 移除可能的 sh/sz 前缀
            if symbol.startswith('sh') or symbol.startswith('sz'):
                symbol_num = symbol[2:]
            else:
                symbol_num = symbol

            # 尝试使用 tx 接口返回英文列名
            try:
                df = ak.stock_zh_a_hist_tx(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date
                )
                return self._convert_to_english_columns(df)
            except Exception:
                # 如果 tx 接口失败，使用 em 接口并转换列名
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date
                )
                return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取日线数据失败: {e}")
            return pd.DataFrame()

    def get_stock_hist_MIN(self, symbol: str, period: str = "5") -> pd.DataFrame:
        """
        获取股票分时数据

        Args:
            symbol: 股票代码
            period: 周期 (5, 15, 30, 60)

        Returns:
            分时数据 DataFrame
        """
        try:
            df = ak.stock_zh_a_hist_min_em(symbol=symbol, period=period)
            return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取分时数据失败: {e}")
            return pd.DataFrame()

    def get_stock_fund_flow(self, symbol: str) -> pd.DataFrame:
        """
        获取股票资金流

        Args:
            symbol: 股票代码

        Returns:
            资金流 DataFrame
        """
        try:
            df = ak.stock_individual_fund_flow(symbol=symbol)
            return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取资金流失败: {e}")
            return pd.DataFrame()

    def get_stock_fund_flow_individual(self, symbol: str) -> pd.DataFrame:
        """
        获取个股资金流向

        Args:
            symbol: 股票代码

        Returns:
            资金流向 DataFrame
        """
        try:
            df = ak.stock_individual_fund_flow(symbol=symbol)
            return self._convert_to_english_columns(df)
        except Exception as e:
            print(f"获取个股资金流向失败: {e}")
            return pd.DataFrame()
