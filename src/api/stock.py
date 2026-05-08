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

    def get_fund_flow_data(self, symbol: str) -> dict:
        """
        获取个股资金流结构化数据（最新日 + 近5日趋势 + 融资融券）

        Args:
            symbol: 股票代码 (如 sz300274 或 300274)

        Returns:
            资金流数据字典
        """
        # 移除前缀
        if symbol.startswith('sh') or symbol.startswith('sz'):
            symbol_num = symbol[2:]
            prefix = symbol[:2]
        else:
            symbol_num = symbol
            prefix = 'sz' if symbol_num.startswith('3') or symbol_num.startswith('0') else 'sh'

        market_map = {'sh': 'sh', 'sz': 'sz'}
        market = market_map.get(prefix, 'sh')

        result = {
            'main_net_inflow': None,
            'main_pct': None,
            'super_order': None,
            'large_order': None,
            'mid_order': None,
            'small_order': None,
            'main_5day': None,
            'main_5day_trend': '持平',
            'margin_balance': None,
            'margin_change': None,
        }

        # 资金流数据
        try:
            df = ak.stock_individual_fund_flow(stock=symbol_num, market=market)
            if df is not None and not df.empty:
                # 列名映射（中文）
                col_map = {}
                for col in df.columns:
                    if '主力' in col and '净额' in col:
                        col_map['main_net'] = col
                    elif '主力' in col and '净占' in col:
                        col_map['main_pct'] = col
                    elif '超大单' in col and '净额' in col:
                        col_map['super'] = col
                    elif '大单' in col and '净额' in col:
                        col_map['large'] = col
                    elif '中单' in col and '净额' in col:
                        col_map['mid'] = col
                    elif '小单' in col and '净额' in col:
                        col_map['small'] = col

                if col_map.get('main_net'):
                    latest = df.iloc[-1]
                    result['main_net_inflow'] = _safe_num(latest[col_map['main_net']])
                    result['main_pct'] = _safe_num(latest.get(col_map.get('main_pct', ''), 0))
                    result['super_order'] = _safe_num(latest.get(col_map.get('super', ''), 0))
                    result['large_order'] = _safe_num(latest.get(col_map.get('large', ''), 0))
                    result['mid_order'] = _safe_num(latest.get(col_map.get('mid', ''), 0))
                    result['small_order'] = _safe_num(latest.get(col_map.get('small', ''), 0))

                    # 近5日主力净流入累计
                    if len(df) >= 5:
                        last5 = df.tail(5)
                        main_col = col_map['main_net']
                        result['main_5day'] = last5[main_col].sum()
                        inflow_days = (last5[main_col] > 0).sum()
                        if inflow_days >= 4:
                            result['main_5day_trend'] = '持续流入'
                        elif inflow_days <= 1:
                            result['main_5day_trend'] = '持续流出'
                        elif inflow_days == 3:
                            result['main_5day_trend'] = '偏流入'
                        elif inflow_days == 2:
                            result['main_5day_trend'] = '偏流出'
        except Exception as e:
            print(f"  [WARN] 资金流: {e}")

        # 融资融券数据
        try:
            df_margin = ak.stock_margin_detail_em(symbol=symbol_num)
            if df_margin is not None and not df_margin.empty:
                col_map_m = {}
                for col in df_margin.columns:
                    if '融资余额' in col:
                        col_map_m['balance'] = col
                    elif '融资' in col and '变动' in col:
                        col_map_m['change'] = col

                if col_map_m.get('balance'):
                    latest = df_margin.iloc[-1]
                    result['margin_balance'] = _safe_num(latest[col_map_m['balance']])
                    if col_map_m.get('change'):
                        result['margin_change'] = _safe_num(latest[col_map_m['change']])
        except Exception as e:
            print(f"  [WARN] 融资融券: {e}")

        return result


def _safe_num(val, default=None):
    """安全转数字"""
    try:
        v = float(str(val).replace(',', '').replace('%', ''))
        return v
    except (ValueError, TypeError):
        return default
