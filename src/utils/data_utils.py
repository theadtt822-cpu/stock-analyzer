"""
数据处理工具
"""
import pandas as pd
import numpy as np
from typing import Optional


def clean_stock_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗股票数据

    Args:
        df: 原始数据 DataFrame

    Returns:
        清洗后的 DataFrame
    """
    # 删除重复行
    df = df.drop_duplicates()

    # 删除空值
    df = df.dropna()

    # 数据类型转换
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 按日期排序
    if 'date' in df.columns:
        df = df.sort_values('date').reset_index(drop=True)

    return df


def normalize_price(df: pd.DataFrame, price_col: str = 'close') -> pd.DataFrame:
    """
    价格标准化

    Args:
        df: 数据 DataFrame
        price_col: 价格列名

    Returns:
        添加标准化价格的 DataFrame
    """
    df = df.copy()
    df['normalized_price'] = df[price_col] / df[price_col].iloc[0]
    return df


def filter_by_date(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """
    按日期过滤数据

    Args:
        df: 数据 DataFrame
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)

    Returns:
        过滤后的 DataFrame
    """
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        df = df[mask]
    return df
