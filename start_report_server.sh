#!/bin/bash
cd /home/admin/.openclaw/workspace/daily_stock_analysis
nohup python3.11 report_server.py > /tmp/report_server.log 2>&1 &
echo "Server started with PID: $!"
sleep 2
curl -s http://localhost:8080/ | head -5
