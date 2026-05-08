#!/bin/bash
cd /home/admin/.openclaw/workspace/daily_stock_analysis
source .venv/bin/activate
python -c "from src.daily_collector import run_postmarket_report; run_postmarket_report()"
