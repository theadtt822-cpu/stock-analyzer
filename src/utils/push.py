"""
Server酱 微信推送工具
"""
import urllib.request
import urllib.parse


SENDKEY = "SCT345543TO9QuMNw7lATztVrqrKmToI4k"
API_URL = f"https://sctapi.ftqq.com/{SENDKEY}.send"


def push(title: str, desp: str = "") -> dict:
    """
    推送消息到微信

    Args:
        title: 消息标题
        desp: 消息内容（支持 Markdown）

    Returns:
        推送结果字典
    """
    data = urllib.parse.urlencode({'title': title, 'desp': desp}).encode('utf-8')
    req = urllib.request.Request(API_URL, data=data)
    try:
        resp = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        return eval(resp)
    except Exception as e:
        return {'code': -1, 'message': str(e)}
