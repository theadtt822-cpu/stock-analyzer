#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成报告汇总入口页
扫描 output/ 目录下所有报告文件，生成带日期索引的 HTML 导航页
"""
import os
import glob
from datetime import datetime

REPORT_DIR = os.path.join(os.path.dirname(__file__), "output")


def _file_mtime(path):
    return datetime.fromtimestamp(os.path.getmtime(path))


def _file_size(path):
    size = os.path.getsize(path)
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    elif size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def generate_index():
    if not os.path.isdir(REPORT_DIR):
        os.makedirs(REPORT_DIR, exist_ok=True)

    # 按类型分组
    groups = {
        "盘前预测": {"prefix": "premarket_", "emoji": "🌅", "files": []},
        "午间新闻": {"prefix": "news_", "emoji": "📰", "files": []},
        "收盘复盘": {"prefix": "postmarket_", "emoji": "📊", "files": []},
        "个股技术报告": {"prefix": "analysis_report", "emoji": "📈", "files": []},
        "个股综合图": {"prefix": "07_analysis_report", "emoji": "🖼️", "files": []},
        "其他": {"prefix": None, "emoji": "📁", "files": []},
    }

    known_prefixes = [g["prefix"] for g in groups.values() if g["prefix"]]

    for f in sorted(os.listdir(REPORT_DIR)):
        full = os.path.join(REPORT_DIR, f)
        if not os.path.isfile(full):
            continue
        if not (f.endswith(".html") or f.endswith(".png")):
            continue

        placed = False
        for group in groups.values():
            if group["prefix"] and f.startswith(group["prefix"]):
                group["files"].append((f, _file_mtime(full), _file_size(full)))
                placed = True
                break
        if not placed:
            groups["其他"]["files"].append((f, _file_mtime(full), _file_size(full)))

    # 按修改时间倒序排列
    for g in groups.values():
        g["files"].sort(key=lambda x: x[1], reverse=True)

    # 提取所有日期
    all_dates = set()
    for g in groups.values():
        for fname, _, _ in g["files"]:
            # 从文件名提取日期
            for part in fname.replace("_", "-").split("-"):
                if len(part) == 8 and part.isdigit():
                    all_dates.add(part)
                    break
                if len(part) == 10 and part[:4].isdigit():
                    all_dates.add(part.replace("-", ""))
                    break

    # 生成 HTML
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>股票分析报告汇总</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'Microsoft YaHei', 'PingFang SC', sans-serif; background: #f0f2f5; color: #333; padding: 16px; }
.container { max-width: 900px; margin: 0 auto; }
.header { background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px; }
.header h1 { font-size: 22px; margin-bottom: 4px; }
.header .date { font-size: 13px; opacity: 0.7; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 16px; padding: 20px; }
.card h2 { font-size: 16px; color: #333; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px; margin-bottom: 12px; }
.file-list { list-style: none; }
.file-item { display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid #f5f5f5; gap: 12px; }
.file-item:last-child { border-bottom: none; }
.file-icon { font-size: 18px; width: 28px; text-align: center; flex-shrink: 0; }
.file-name { flex: 1; font-size: 14px; }
.file-name a { color: #1a1a2e; text-decoration: none; }
.file-name a:hover { color: #4a90d9; text-decoration: underline; }
.file-date { font-size: 12px; color: #999; white-space: nowrap; }
.file-size { font-size: 12px; color: #bbb; white-space: nowrap; width: 60px; text-align: right; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; background: #e8f0fe; color: #4a90d9; margin-right: 4px; }
.empty { color: #999; padding: 12px 0; font-size: 14px; }
.stats { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 12px; }
.stat-item { background: rgba(255,255,255,0.1); border-radius: 8px; padding: 8px 16px; }
.stat-item .num { font-size: 20px; font-weight: bold; }
.stat-item .label { font-size: 12px; opacity: 0.6; }
@media (max-width: 600px) {
    .file-item { flex-wrap: wrap; }
    .file-size { width: auto; text-align: left; }
}
</style>
</head>
<body>
<div class="container">
<div class="header">
    <h1>股票分析报告汇总</h1>
    <div class="date">最后更新: """ + datetime.now().strftime('%Y-%m-%d %H:%M') + """</div>
    <div class="stats">"""

    total = sum(len(g["files"]) for g in groups.values())
    html += f"""
        <div class="stat-item"><div class="num">{total}</div><div class="label">报告总数</div></div>
        <div class="stat-item"><div class="num">{len(all_dates)}</div><div class="label">交易日</div></div>"""

    html += """
    </div>
</div>
"""

    for title, g in groups.items():
        if not g["files"]:
            continue
        html += f"""
<div class="card">
    <h2>{g['emoji']} {title} ({len(g['files'])})</h2>
    <ul class="file-list">"""
        for fname, mtime, size in g["files"]:
            date_str = mtime.strftime('%Y-%m-%d %H:%M')
            html += f"""
        <li class="file-item">
            <span class="file-icon">{g['emoji']}</span>
            <span class="file-name"><a href="{fname}">{fname}</a></span>
            <span class="file-date">{date_str}</span>
            <span class="file-size">{size}</span>
        </li>"""
        html += """
    </ul>
</div>"""

    html += """
<div style="text-align:center;padding:16px;color:#999;font-size:12px">
    本报告汇总由系统自动生成，数据仅供参考，不构成投资建议<br>
""" + f"""生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>
</div>
</body>
</html>"""

    index_path = os.path.join(REPORT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    return index_path


if __name__ == "__main__":
    path = generate_index()
    print(f"汇总页已生成: {path}")
