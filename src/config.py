"""
-------
 warn ning: This is a template file. Please update with your actual information.
-------
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """配置类"""

    # 数据目录
    DATA_DIR = os.getenv("DATA_DIR", "./data")

    # 日志级别
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # AKShare 配置
    AK_TOKEN = os.getenv("AK_TOKEN", "")

    # 数据源配置
    SOURCES = {
        "akshare": {
            "name": "AKShare",
            "url": "https://akshare.akshare.xyz/"
        }
    }

    # 可用的股票代码列表
    STOCK_LIST = {
        "sh600000": "浦发银行",
        "sh600036": "招商银行",
        "sh600519": "贵州茅台",
        "sz000001": "平安银行",
        "sz000858": "五粮液"
    }

    @classmethod
    def init(cls):
        """初始化配置"""
        os.makedirs(cls.DATA_DIR, exist_ok=True)


# 初始化配置
Config.init()
