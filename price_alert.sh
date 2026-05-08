#!/bin/bash
# 价格监控告警脚本
# 检查天通股份和沃格光电价格，触发时发送飞书提醒

cd /home/admin/.openclaw/workspace/daily_stock_analysis

# 运行价格监控
RESULT=$(/home/admin/.openclaw/workspace/.venv/bin/python3.11 price_monitor.py 2>/dev/null)

if echo "$RESULT" | head -1 | grep -q "ALERT"; then
    # 有告警，发送到飞书
    ALERT_MSG=$(echo "$RESULT" | tail -n +2)
    
    # 使用openclaw gateway发送消息
    OPENCLAW_GW=$(cat /home/admin/.openclaw/gateway.json 2>/dev/null | python3.11 -c "
import json,sys
try:
    cfg=json.load(sys.stdin)
    acc=cfg.get('channels',{}).get('feishu',{}).get('accounts',{}).get('tiantian',{})
    print(f\"{acc.get('appId','')}|{acc.get('appSecret','')}\")
except: print('')
" 2>/dev/null)
    
    if [ -n "$OPENCLAW_GW" ]; then
        APP_ID=$(echo "$OPENCLAW_GW" | cut -d'|' -f1)
        APP_SECRET=$(echo "$OPENCLAW_GW" | cut -d'|' -f2)
        
        # 获取tenant token
        TOKEN=$(curl -s -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
            -H "Content-Type: application/json" \
            -d "{\"app_id\":\"$APP_ID\",\"app_secret\":\"$APP_SECRET\"}" | \
            python3.11 -c "import json,sys; print(json.load(sys.stdin).get('tenant_access_token',''))")
        
        if [ -n "$TOKEN" ]; then
            # 发送消息给邓天天
            curl -s -X POST "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id" \
                -H "Authorization: Bearer $TOKEN" \
                -H "Content-Type: application/json" \
                -d "{
                    \"receive_id\": \"ou_0b30fb807b98f8f5c18865912b8975cf\",
                    \"msg_type\": \"text\",
                    \"content\": \"{\\\"text\\\": \"$(echo "$ALERT_MSG" | sed 's/"/\\"/g')\"}\"
                }"
            echo "Sent alert: $ALERT_MSG"
        fi
    fi
fi
