#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
每日定时报告调度器

三个定时任务：
- 08:30  盘前预测报告（隔夜外盘 + 期货 + 政策 + 板块预测 + 综合研判）
- 11:30  午间新闻汇总（A股/美股要闻 + 经济指标 + 投行观点）
- 15:30  收盘复盘报告（指数 + 板块排行 + 涨跌停 + 技术分析 + 明日展望）

用法：
    python daily_scheduler.py           # 启动定时调度
    python daily_scheduler.py --now     # 立即运行一次所有报告
"""
import sys
import os
import logging
from datetime import datetime

# 设置中文显示
import matplotlib
matplotlib.use('Agg')

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.daily_collector import (
    run_premarket_report,
    run_news_report,
    run_postmarket_report,
)

from generate_index import generate_index

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scheduler.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def wrap(fn):
    """执行报告后自动刷新汇总页"""
    def inner():
        fn()
        path = generate_index()
        print(f"  汇总页已更新: {path}")
    return inner


def main():
    if "--now" in sys.argv:
        print("立即运行所有报告...")
        run_premarket_report()
        run_news_report()
        run_postmarket_report()
        generate_index()
        print("\n全部完成！")
        return

    print("=" * 60)
    print("每日报告定时调度器")
    print("=" * 60)
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n定时任务:")
    print("  08:30  盘前预测报告")
    print("  11:30  午间新闻汇总")
    print("  15:30  收盘复盘报告")
    print("\n按 Ctrl+C 停止调度器\n")

    scheduler = BlockingScheduler(timezone="Asia/Shanghai")

    # 盘前预测 - 每个工作日 08:30
    scheduler.add_job(
        wrap(run_premarket_report),
        CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone="Asia/Shanghai"),
        id="premarket",
        name="盘前预测报告",
        replace_existing=True,
    )

    # 午间新闻 - 每个工作日 11:30
    scheduler.add_job(
        wrap(run_news_report),
        CronTrigger(day_of_week="mon-fri", hour=11, minute=30, timezone="Asia/Shanghai"),
        id="news",
        name="午间新闻汇总",
        replace_existing=True,
    )

    # 收盘复盘 - 每个工作日 15:30
    scheduler.add_job(
        wrap(run_postmarket_report),
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30, timezone="Asia/Shanghai"),
        id="postmarket",
        name="收盘复盘报告",
        replace_existing=True,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n调度器已停止")


if __name__ == "__main__":
    main()
