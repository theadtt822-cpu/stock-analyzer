#!/usr/bin/env python3
"""
飞书消息解析 - KOL荐股录入
当用户通过飞书发送荐股信息时，自动解析并录入到 KOL Tracker
"""

import re
import json
import urllib.request
import sys

KOL_API_BASE = 'http://localhost:8082/api/tiantian'

# ===== KOL 名称映射 =====
KOL_ALIASES = {
    '天盈': 'xhs_tianying',
    '金猫': 'xhs_jinmao',
    '金猫理财': 'xhs_jinmao',
    '擒龙': 'xhs_qinglong',
    '擒龙青鹰': 'xhs_qinglong',
    '青鹰': 'xhs_qinglong',
    '趋势孙哥': 'xhs_sunge',
    '孙哥': 'xhs_sunge',
    '求道': 'xhs_qiudao',
    '求道作手': 'xhs_qiudao',
    '观潮': 'xhs_guanchao',
    'rice': 'rice',
    'Rice': 'rice',
    'RICE': 'rice',
}

# ===== 股票代码正则 =====
# 匹配 6位数字代码
CODE_PATTERN = r'(?:代码|:|：|#)?\s*([036]\d{5})\b'
# 匹配股票名称
NAME_PATTERN = r'([^\s:：,，;；、]+)(?:股份|科技|集团|药业|电气|电子|通信|能源|电力|银行|保险|地产|置业|建设|发展|实业|控股|材料|生物|环境|健康|传媒|文化|教育|网络|软件|硬件|数据|精密|精密|制造|工业|汽车|运输|物流|零售|百货|商业|食品|农业|林业|矿业|钢铁|化工|塑胶|纺织|服装|印刷|包装|纸业|家具|装饰|装修|建材|旅游|酒店|餐饮|娱乐|体育|广告|咨询|服务|投资|管理|资产|资本|金融|期货|证券|基金|信托|担保|租赁|环保|节能|新能源|新材料|新能车|锂电池|光伏|半导体|芯片|人工智能|机器人|区块链|元宇宙|web3|5G|物联网|云计算|大数据|虚拟现实|增强现实|混合现实|数字孪生|智能制造|智能驾驶|智能网联|自动驾驶|新能源车|电动车|氢能源|储能|风电|核电|水电|火电|电网|特高压|换电|充电桩|充电桩设备|电池|正极|负极|隔膜|电解液|锂电|钠电|光伏设备|光伏玻璃|硅料|硅片|电池片|组件|逆变器|支架|跟踪器|储能系统|储能电池|储能变流器|储能集成|风电整机|风电叶片|风电轴承|风电铸件|风电法兰|风电塔筒|海上风电|陆上风电|风电运营|风电开发|风电建设|风电施工|风电设计|风电咨询|风电监理|风电检测|风电运维|风电后市场)'

# ===== 解析函数 =====
def detect_kol(text):
    """检测 KOL 来源"""
    text_lower = text.lower()
    for alias, source_id in KOL_ALIASES.items():
        if alias.lower() in text_lower:
            return alias, source_id
    return None, None

def detect_stock_code(text):
    """检测股票代码"""
    m = re.search(CODE_PATTERN, text)
    if m:
        return m.group(1)
    return None

def detect_date(text):
    """检测日期"""
    patterns = [
        r'(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})',
        r'(\d{1,2}月\d{1,2}日)',
        r'(今天|今日|昨天|前天)',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return None

def parse_kol_message(text):
    """
    解析飞书消息中的荐股信息
    返回 dict 或 None
    """
    if not text or len(text.strip()) < 5:
        return None
    
    # 检测是否是荐股相关消息
    keywords = ['推荐', '荐股', '关注', '买入', '目标', '看涨', '看多', '机会', '机会', '机会', '关注', '标的', '票', '股', 'KOL', '博主', 'rice', 'rice说', 'rice分享']
    if not any(kw in text for kw in keywords) and not re.search(CODE_PATTERN, text):
        return None

    kol_name, source_id = detect_kol(text)
    code = detect_stock_code(text)
    
    result = {
        'text': text[:500],
        'kol_name': kol_name,
        'source_id': source_id,
        'stock_code': code,
        'stock_name': None,
        'date': detect_date(text),
        'reason': None,
        'operation': None,
    }

    # 如果用 LLM 解析更准确
    llm_result = llm_parse(text)
    if llm_result:
        result.update(llm_result)

    return result

def llm_parse(text):
    """用本地 LLM 解析荐股信息"""
    prompt = f"""你是一个股票推荐信息解析助手。请从以下文本中提取荐股信息，按 JSON 格式输出：

{{
  "stock_code": "6位数字股票代码，如果有的话，没有则null",
  "stock_name": "股票名称，如果有的话，没有则null", 
  "source_id": "来源ID（天盈=xhs_tianying, 金猫理财=xhs_jinmao, 擒龙青鹰=xhs_qinglong, 趋势孙哥=xhs_sunge, 求道作手=xhs_qiudao, 观潮=xhs_guanchao, rice=rice，没有则null）",
  "date": "推荐日期 YYYY-MM-DD 格式，如果有的话，没有则null",
  "reason": "推荐理由（50字以内），没有则null",
  "operation": "操作建议（如买入/卖出/仓位/目标价等），没有则null"
}}

文本内容：
{text[:2000]}

请严格输出 JSON，不要其他内容。"""

    try:
        payload = json.dumps({
            "model": "openclaw",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 500,
        }).encode('utf-8')
        req = urllib.request.Request(
            'http://localhost:15126/v1/chat/completions',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer a425fdf94a7567401179a00d3eade5e2',
            },
            method='POST',
        )
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode('utf-8'))
        content = result['choices'][0]['message']['content']
        
        if '```' in content:
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
        
        return json.loads(content.strip())
    except Exception as e:
        print(f'[LLM parse error] {e}')
        return None

def add_to_kol_tracker(parsed):
    """将解析结果录入 KOL Tracker"""
    if not parsed.get('stock_code') or not parsed.get('stock_name'):
        return False, "未识别到股票代码/名称"
    
    rec = {
        'source_id': parsed.get('source_id', ''),
        'stock_code': parsed['stock_code'],
        'stock_name': parsed['stock_name'],
        'recommend_date': parsed.get('date') or '2026-05-07',
        'reason': parsed.get('reason', ''),
        'operation': parsed.get('operation', ''),
        'status': 'tracking',
        'tracking': {},
    }

    try:
        payload = json.dumps({'rec': rec}).encode('utf-8')
        req = urllib.request.Request(
            f'{KOL_API_BASE}/kol/recommendations',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        if data.get('ok'):
            return True, f"✅ 已录入 {rec['stock_name']}({rec['stock_code']}) 来源:{parsed.get('kol_name','未知')}"
        return False, data.get('error', '录入失败')
    except Exception as e:
        return False, str(e)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        text = ' '.join(sys.argv[1:])
    else:
        text = sys.stdin.read()
    
    parsed = parse_kol_message(text)
    if not parsed:
        print("❌ 未识别到荐股信息")
        sys.exit(0)
    
    print(f"解析结果: {json.dumps(parsed, ensure_ascii=False, indent=2)}")
    
    success, msg = add_to_kol_tracker(parsed)
    print(f"录入: {msg}")
