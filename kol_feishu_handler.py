#!/usr/bin/env python3
"""
飞书 KOL 荐股消息处理器
- 检查飞书新消息
- 解析荐股信息并录入 KOL Tracker
- 发送确认回执
"""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime

# 飞书凭证（天天的bot）
FEISHU_APP_ID = 'cli_a971acd6453c9bd3'
FEISHU_APP_SECRET = '4mDKnq52Yz99J0kbRIp4wfWjgpp1wO2j'

KOL_PARSER = '/home/admin/.openclaw/workspace/daily_stock_analysis/kol_feishu_parser.py'
STATE_FILE = '/tmp/kol_feishu_last_msg_id.json'

def get_access_token():
    url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
    payload = json.dumps({
        'app_id': FEISHU_APP_ID,
        'app_secret': FEISHU_APP_SECRET,
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode('utf-8'))
    return data.get('tenant_access_token', '')

def get_last_message_id():
    try:
        with open(STATE_FILE) as f:
            return json.load(f).get('last_msg_id', '')
    except:
        return ''

def save_last_message_id(msg_id):
    with open(STATE_FILE, 'w') as f:
        json.dump({'last_msg_id': msg_id, 'time': datetime.now().isoformat()}, f)

def get_messages(last_msg_id=''):
    """获取最近消息"""
    token = get_access_token()
    if not token:
        print("❌ 获取 token 失败")
        return []
    
    # 获取所有包含机器人的会话
    url = 'https://open.feishu.cn/open-apis/im/v1/chats?page_size=50'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    resp = urllib.request.urlopen(req, timeout=10)
    chats = json.loads(resp.read().decode('utf-8')).get('data', {}).get('items', [])
    
    all_messages = []
    for chat in chats:
        chat_id = chat.get('chat_id')
        if not chat_id:
            continue
        
        # 获取该会话的消息
        params = {'container_id_type': 'chat', 'container_id': chat_id, 'page_size': 20}
        if last_msg_id:
            params['start_id'] = last_msg_id
            params['sort_type'] = 'ByCreateTimeAsc'
        
        msg_url = 'https://open.feishu.cn/open-apis/im/v1/messages?' + urllib.parse.urlencode(params)
        msg_req = urllib.request.Request(msg_url, headers={'Authorization': f'Bearer {token}'})
        try:
            msg_resp = urllib.request.urlopen(msg_req, timeout=10)
            msg_data = json.loads(msg_resp.read().decode('utf-8')).get('data', {}).get('items', [])
            # 只处理用户消息（不是机器人自己的）
            for m in msg_data:
                if m.get('sender', {}).get('sender_type') == 'user':
                    all_messages.append(m)
        except:
            pass
    
    # 按时间排序
    all_messages.sort(key=lambda x: x.get('create_time', ''))
    return all_messages

def send_reply(chat_id, text):
    token = get_access_token()
    if not token:
        return False
    
    url = f'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id'
    body = {
        'receive_id': chat_id,
        'msg_type': 'text',
        'content': json.dumps({'text': text}),
    }
    payload = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status == 200
    except:
        return False

def parse_and_add(text, chat_id):
    """解析文本并录入 KOL Tracker"""
    import subprocess
    try:
        result = subprocess.run(
            ['/usr/bin/python3.11', KOL_PARSER, text],
            capture_output=True, text=True, timeout=120
        )
        output = result.stdout.strip()
        
        if '✅ 已录入' in output:
            # 提取最后一行作为回复
            reply = output.split('\n')[-1]
            send_reply(chat_id, reply)
            return True, reply
        elif '未识别到荐股信息' in output:
            # 只有明显的荐股关键词才回复
            keywords = ['推荐', '荐股', '关注', '目标价', '买入', 'rice', '天盈', '金猫', '青鹰', '孙哥', '求道', '观潮']
            if any(kw in text for kw in keywords):
                send_reply(chat_id, '未识别到荐股信息。格式建议：\n[博主名]推荐 [股票代码] [股票名称]\n推荐理由：...\n操作建议：...')
            return False, '未识别'
        else:
            return False, output
    except Exception as e:
        return False, str(e)

def main():
    print(f"[{datetime.now().isoformat()}] 开始检查飞书消息...")
    
    last_msg_id = get_last_message_id()
    messages = get_messages(last_msg_id)
    
    print(f"获取到 {len(messages)} 条新消息")
    
    processed = 0
    for msg in messages:
        msg_id = msg.get('message_id', '')
        chat_id = msg.get('chat_id', '')
        content = json.loads(msg.get('content', '{}'))
        text = content.get('text', '')
        
        if not text.strip():
            continue
        
        print(f"处理消息: {text[:100]}...")
        success, result = parse_and_add(text, chat_id)
        if success:
            processed += 1
            print(f"✅ {result}")
        
        save_last_message_id(msg_id)
    
    print(f"处理完成，成功录入 {processed} 条")

if __name__ == '__main__':
    main()
