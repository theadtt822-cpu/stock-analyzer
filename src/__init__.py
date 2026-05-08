"""
股票和市场分析项目
"""

__version__ = "0.1.0"
__author__ = "thea"

# 主模块
from .api.stock import StockData
from .api.market import MarketData

# 分析模块
from .analysis.tech_indicator import TechIndicator
from .analysis.factor_analyzer import FactorAnalyzer
from .analysis.visualizer import Visualizer

# 数据模块（可选）
# from .data.storage import DataStorage

# 工具模块
from .utils.data_utils import clean_stock_data, normalize_price, filter_by_date
from .logger import logger
from .config import Config

__all__ = [
    # 数据获取
    "StockData",
    "MarketData",
    # 分析
    "TechIndicator",
    "FactorAnalyzer",
    "Visualizer",
    # 数据模块（可选）
    # "DataStorage",
    # 工具
    "clean_stock_data",
    "normalize_price",
    "filter_by_date",
    "logger",
    "Config"
]
