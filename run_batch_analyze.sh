#!/bin/bash
cd /home/admin/.openclaw/workspace/daily_stock_analysis
source .venv/bin/activate
python batch_analyze.py "$@"
