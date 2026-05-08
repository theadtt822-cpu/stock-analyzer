"""
日志模块
"""
import logging
import sys
from datetime import datetime
from typing import Optional


class Logger:
    """日志类"""

    def __init__(self, name: str = "stock_analysis", level: str = "INFO"):
        """
        初始化

        Args:
            name: 日志名称
            level: 日志级别
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))

        # 格式化
        formatter = logging.Formatter(
            '{"appName":"stock-market-analysis","time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
            datefmt='%Y-%m-%dT%H:%M:%S%z'
        )
        console_handler.setFormatter(formatter)

        # 添加处理器
        if not self.logger.handlers:
            self.logger.addHandler(console_handler)

    def info(self, message: str):
        """信息日志"""
        self.logger.info(message)

    def warning(self, message: str):
        """警告日志"""
        self.logger.warning(message)

    def error(self, message: str):
        """错误日志"""
        self.logger.error(message)

    def debug(self, message: str):
        """调试日志"""
        self.logger.debug(message)


# 默认日志实例
logger = Logger()
