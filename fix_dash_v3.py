#!/usr/bin/env python3
"""Re-apply 9 changes to dashboard_v2.html - line-number based."""
import re

path = '/home/admin/.openclaw/workspace/daily_stock_analysis/templates/dashboard_v2.html'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Change 1: Remove CSS rules for .rpt-icon (line 43) and .rpt-refresh (keep .rpt-icon definition)
# Change 2: Remove .tech-row CSS rules (lines 60, 133)
for i, line in enumerate(lines):
    stripped = line.strip()
    # Nullify rpt classes
    if stripped.startswith('.rpt-icon{') or stripped.startswith('.rpt-icon:hover'):
        lines[i] = ''
    if stripped.startswith('.tech-row') and ('grid-template' in stripped or '}' in stripped):
        lines[i] = ''

# Change 3: Table row (line 359) - replace openReport/rpt-icon/rpt-refresh with refresh button
for i, line in enumerate(lines):
    if 'stock-name" onclick="openReport' in line and 'rpt-icon' in line:
        # Extract the code pattern: uid = r.code
        # Old: '<td class="sn"><span class="stock-name" onclick="openReport(...)">NAME</span><span class="rpt-icon"...>➖</span><span class="rpt-refresh" onclick="regenerateReport(...)">🔄</span></td>'
        # New: '<td class="sn"><span class="stock-name">NAME</span><button class="btn btn-primary btn-xs" onclick="refreshStock(${code})" style="padding:0 5px;font-size:10px;margin-left:4px;line-height:1.6">🔄</button><button class="btn btn-sm" onclick="editStock(cd)" style="padding:0 5px;font-size:10px;margin-left:2px">✏️</button><button class="btn btn-sm" onclick="delStock(cd)" style="padding:0 5px;font-size:10px;margin-left:2px;color:#c0392b">✖️</button></td>'
        lines[i] = "      '<td class=\"sn\"><span class=\"stock-name\">' + esc(r.name) + '</span>' +\n"
        lines[i] += "      '<button class=\"btn btn-primary btn-xs\" onclick=\"refreshStock(\\'\" + r.code + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:4px;line-height:1.6\">&#x1F504;</button>' +\n"
        lines[i] += "      '<button class=\"btn btn-sm\" onclick=\"editStock(\\'\" + esc(r.code) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px\">&#x270F;&#xFE0F;</button>' +\n"
        lines[i] += "      '<button class=\"btn btn-sm\" onclick=\"delStock(\\'\" + esc(r.code) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px;color:#c0392b\">&#x2716;</button></td>' +\n"
        break

print("Change 3 (table row) done")

# Change 4: Card top (line ~414) - replace stock-name onclick with plain + refresh
for i, line in enumerate(lines):
    if 'stock-name" onclick="openReport' in line and 'rpt-icon' in line and 'rpt-refresh' in line:
        # This is the card header line
        lines[i] = "        '<span class=\"stock-name\" style=\"font-weight:700;font-size:12px;color:#2d3436\">' + nm + '</span>' +\n"
        # Insert refresh + edit + del after the stock-name line
        # We need to skip 2 more lines (rpt-icon and rpt-refresh)
        if i+1 < len(lines) and 'rpt-icon' in lines[i+1]:
            lines[i+1] = ''
        if i+2 < len(lines) and 'rpt-refresh' in lines[i+1] or (i+2 < len(lines) and 'regenerateReport' in lines[i+2]):
            lines[i+2] = ''
        break

print("Change 4 (card top) ink")

# Actually, let me do this differently - find the card top block more precisely
for i, line in enumerate(lines):
    if 'stock-name" onclick="openReport' in line and 'font-weight:700;font-size:12px;color:#2d3436;cursor:pointer' in line:
        lines[i] = "        '<span class=\"stock-name\" style=\"font-weight:700;font-size:12px;color:#2d3436\">' + nm + '</span>' +\n"
        # The next 2 lines should be rpt-icon and rpt-refresh
        if i+1 < len(lines):
            lines[i+1] = ''
        if i+2 < len(lines):
            lines[i+2] = ''
        # Add new buttons
        # We'll insert after this block - the line with '</a>' is at i+?
        break

# Hmm, this approach is getting complex. Let me use a more surgical approach.
# Read the file as string for targeted replacements.

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Change 1: CSS classes for rpt
content = content.replace(
    '.rpt-icon{font-size:11px;cursor:pointer;margin-left:3px;opacity:0.7;vertical-align:middle}\n.rpt-icon:hover{opacity:1}\n',
    ''
)

# Change 2: CSS tech-row lines
content = content.replace(
    '.tech-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:6px;margin-bottom:10px}\n',
    ''
)
content = content.replace(
    '.tech-row{grid-template-columns:repeat(3,1fr);gap:2px}\n',
    ''
)

# Change 3: Table row - the big one
# Old table row
old_table_row = (
    "      '<td class=\"sn\"><span class=\"stock-name\" onclick=\"openReport(\\'\" + r.code + \"','\" + jsEsc(r.name) + \"')\">\" + esc(r.name) + '</span><span class=\"rpt-icon\" id=\"rpt-' + r.code + '\">➖</span><span class=\"rpt-refresh\" onclick=\"regenerateReport(\\'\" + r.code + \"')\" title=\"刷新报告\">&#x1F504;</span></td>' +\n"
    "      '<td>' + (r.sector || '-') + '</td>' +"
)
new_table_row = (
    "      '<td class=\"sn\"><span class=\"stock-name\">' + esc(r.name) + '</span>' +\n"
    "      '<button class=\"btn btn-primary btn-xs\" onclick=\"refreshStock(\\'\" + r.code + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:4px;line-height:1.6\">&#x1F504;</button>' +\n"
    "      '<button class=\"btn btn-sm\" onclick=\"editStock(\\'\" + esc(r.code) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px\">&#x270F;&#xFE0F;</button>' +\n"
    "      '<button class=\"btn btn-sm\" onclick=\"delStock(\\'\" + esc(r.code) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px;color:#c0392b\">&#x2716;</button></td>' +\n"
    "      '<td>' + (r.sector || '-') + '</td>' +"
)

if old_table_row in content:
    content = content.replace(old_table_row, new_table_row, 1)
    print("Change 3 (table row) done")
else:
    print("WARN: table row pattern not found!")
    # Try to find partial match
    idx = content.find('stock-name" onclick="openReport')
    if idx >= 0:
        print(f"  stock-name onclick found at {idx}")
    idx = content.find('rpt-icon\" id=\"rpt-')
    if idx >= 0:
        print(f"  rpt-icon found at {idx}")

# Change 4: Card top header
old_card_header = (
    "        '<span class=\"stock-name\" onclick=\"openReport(\\'\" + uid + \"','\" + nm + \"')\" style=\"font-weight:700;font-size:12px;color:#2d3436;cursor:pointer\">\" + nm + '</span>' +\n"
    "        '<span class=\"rpt-icon\" id=\"rpt-' + uid + '\" style=\"font-size:10px\">➖</span>' +\n"
    "        '<span class=\"rpt-refresh\" onclick=\"regenerateReport(\\'\" + uid + \"')\" title=\"刷新报告\" style=\"font-size:11px;cursor:pointer;margin-left:2px\">&#x1F504;</span>' +"
)
new_card_header = (
    "        '<span class=\"stock-name\" style=\"font-weight:700;font-size:12px;color:#2d3436\">' + nm + '</span>' +\n"
    "        '<button class=\"btn btn-primary btn-xs\" onclick=\"refreshStock(\\'\" + uid + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:auto;line-height:1.6\">&#x1F504; 刷新</button>' +\n"
    "        '<button class=\"btn btn-sm\" onclick=\"editStock(\\'\" + esc(uid) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px\">&#x270F;&#xFE0F;</button>' +\n"
    "        '<button class=\"btn btn-sm\" onclick=\"delStock(\\'\" + esc(uid) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px;color:#c0392b\">&#x2716;</button>' +"
)

if old_card_header in content:
    content = content.replace(old_card_header, new_card_header, 1)
    print("Change 4 (card header) done")
else:
    print("WARN: card header pattern not found!")

# Change 5: Watchlist card
old_wl_card = (
    "          '<span class=\"name stock-name\" style=\"font-size:12px\" onclick=\"openReport(\\'\" + s.code + \"','\" + jsEsc(s.name) + \"')\">\" + esc(s.name) + '</span>' +\n"
    "          '<span class=\"rpt-icon\" id=\"rpt-wl-' + s.code + '\">➖</span>' +\n"
)
new_wl_card = (
    "          '<span class=\"name stock-name\" style=\"font-size:12px\">' + esc(s.name) + '</span>' +\n"
    "          '<button class=\"btn btn-primary btn-xs\" onclick=\"refreshWlStock(\\'\" + esc(s.code) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:4px;line-height:1.6\">&#x1F504;</button>' +\n"
    "          '<button class=\"btn btn-sm\" onclick=\"delWlStock(\\'\" + esc(s.code) + \"','\" + esc(g.name) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px;color:#c0392b\">&#x2716;</button>' +\n"
)

if old_wl_card in content:
    content = content.replace(old_wl_card, new_wl_card, 1)
    print("Change 5 (watchlist card) done")
else:
    print("WARN: watchlist card pattern not found!")

# Change 6: reportLink returns empty
content = content.replace(
    "function reportLink(code, name, small, isWl) {\n"
    "  var id = isWl ? 'rpt-wl-' + code : 'rpt-' + code;\n"
    "  var cls = small ? 'rpt-xs' : '';\n"
    "  return '<a id=\"' + id + '\" href=\"javascript:void(0)\" class=\"rl nr ' + cls + '\" onclick=\"fetchReport(\\'\" + code + \"','\" + jsEsc(name) + \"','\" + id + \"')\">📄 个股报告</a>';\n"
    "}",
    "function reportLink(code, name, small, isWl) {\n"
    "  return '';\n"
    "}"
)
print("Change 6 (reportLink) done")

# Change 7: Remove tech-row from StockHolmes card
old_tech_row = re.compile(
    r"        // 技术指标行.*?"
    r"<div class=\"tech-row\" id=\"tr-" + re.escape(r"'+ uid +") + r"_tech\">.*?"
    r"</div>",
    re.DOTALL
)

# Simpler - find and remove the exact tech-row JS generation code
tech_start = "        // 技术指标行\n        '<div class=\"tech-row\" id=\"tr-' + uid + '_tech\">' +"
tech_end = "        '</div>' +"
if tech_start in content:
    start_idx = content.find(tech_start)
    end_idx = content.find(tech_end, start_idx)
    if end_idx >= 0:
        end_idx = end_idx + len(tech_end)
        tech_block = content[start_idx:end_idx]
        print(f"  Found tech-row block: {len(tech_block)} chars")
        content = content[:start_idx] + content[end_idx:]
        print("Change 7 (tech-row removal) done")
    else:
        print("WARN: tech-row end not found")
else:
    print("WARN: tech-row start not found")
    # Try partial match
    idx = content.find('技术指标行')
    if idx >= 0:
        print(f"  Found '技术指标行' at {idx}")
        # Show context
        print(f"  Context: {repr(content[idx:idx+100])}")

# Change 8: Add refreshStock and refreshWlStock functions before fetchIntraday
new_functions = """
// ===== Single Stock Refresh =====
function refreshStock(code) {
  if (!code) return;
  var btn = event && event.target;
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  fetch('/api/' + UK + '/portfolio/refresh-single/' + code)
    .then(function(r) { return r.json(); })
    .then(function(r) {
      if (r.success) { toast(code + ' 已刷新', 'success'); loadP(); }
      else { toast(r.error || '刷新失败: ' + code, 'error'); }
    })
    .catch(function(e) { toast('刷新失败: ' + e.message, 'error'); })
    .finally(function() { if (btn) setTimeout(function() { btn.disabled = false; btn.innerHTML = '\\u{1F504}'; }, 3000); });
}

function refreshWlStock(code) {
  if (!code) return;
  var btn = event && event.target;
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  fetch('/api/' + UK + '/watchlist/refresh-single/' + code)
    .then(function(r) { return r.json(); })
    .then(function(r) {
      if (r.success) { toast(code + ' 已刷新', 'success'); loadW(); }
      else { toast(r.error || '刷新失败: ' + code, 'error'); }
    })
    .catch(function(e) { toast('刷新失败: ' + e.message, 'error'); })
    .finally(function() { if (btn) setTimeout(function() { btn.disabled = false; btn.innerHTML = '\\u{1F504}'; }, 3000); });
}

// ===== Fetch Intraday =====
"""

# Find fetchIntraday
fetch_idx = content.find('function fetchIntraday')
if fetch_idx >= 0:
    # Insert before fetchIntraday
    content = content[:fetch_idx] + new_functions + content[fetch_idx:]
    print("Change 8 (refreshStock/refreshWlStock added) done")
else:
    print("WARN: fetchIntraday not found!")

# Change 9: Update button help descriptions
# Find the help section in header
old_help = (
    "    <div>&#x1F504; <b>刷新行情</b>: 腾讯API拉取所有股票最新价</div>\n"
    "    <div>&#x1F9E0; <b>DeepSeek AI</b>: 批量调用DeepSeek分析持仓</div>"
)
new_help = (
    "    <div>&#x1F504; <b>刷新行情</b>: 腾讯API拉取所有股票最新价+技术指标</div>\n"
    "    <div>&#x1F9E0; <b>DeepSeek AI</b>: 批量调用DeepSeek分析持仓技术面+资金面+估值面</div>\n"
    "    <div>&#x1F504; <b>个股刷新</b>: 卡片上的按钮，只刷新单只股票的全部数据</div>\n"
    "    <div>&#x1F4CB; <b>切换视图</b>: 表格/卡片视图切换</div>"
)

if old_help in content:
    content = content.replace(old_help, new_help, 1)
    print("Change 9 (help text) done")
else:
    print("WARN: help text not found!")
    # Try to find partial
    idx = content.find('刷新行情')
    if idx >= 0:
        print(f"  Found '刷新行情' at {idx}, context: {repr(content[idx-20:idx+80])}")

# Also make batchCheckReports a no-op and remove the old comment-out
# Remove orphaned content from earlier bad edit
bad_comment = "\n\n// 已废弃\n/*"
content = content.replace(bad_comment, '')

# Make batchCheckReports call a no-op
content = content.replace(
    "    batchCheckReports();\n",
    "    // batchCheckReports();\n"
)

# Comment out the batchCheckReports function itself
old_batch_func = (
    "async function batchCheckReports() {\n"
    "  if (!P || !P.results) return;\n"
    "  const codes = P.results.map(r => r.code);\n"
    "  try {\n"
    "    const r = await api('/reports/batch-check?codes=' + codes.join(','));\n"
    "    if (r.reports) {\n"
    "      Object.keys(r.reports).forEach(code => {\n"
    "        const url = r.reports[code];\n"
    "        const el = document.getElementById(rptEid(code));\n"
    "        if (el) {\n"
    "          el.textContent = url ? '\\u{1F4C4}' : '\\u2795';\n"
    "          el.title = url ? '\\u67E5\\u770B\\u4E2A\\u80A1\\u62A5\\u544A' : '\\u751F\\u6210\\u4E2A\\u80A1\\u62A5\\u544A';\n"
    "        }\n"
    "      });\n"
    "    }\n"
    "  } catch(e) { /* silent */ }\n"
    "}\n"
    "\n"
    "function rptEid(code) { return 'rpt-' + code; }\n"
    "\n"
)

if old_batch_func in content:
    content = content.replace(old_batch_func, '', 1)
    print("batchCheckReports removed (cleanup)")
else:
    print("WARN: batchCheckReports function not found!")

# Write the file
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nAll changes applied! Verifying...")
# Verification
# Check for remaining old patterns
for pattern_name, pattern in [
    ("stock-name onclick", 'stock-name" onclick="openReport'),
    ("rpt-icon in JS", "rpt-icon"),
    ("rpt-refresh in JS", "rpt-refresh"),
    ("tech-row", "tech-row"),
    ("regenerateReport call", "regenerateReport("),
    ("openReport(", "openReport("),
]:
    idx = content.find(pattern)
    if idx >= 0:
        line_no = content[:idx].count('\n') + 1
        print(f"  WARN: {pattern_name} still found at line {line_no}")
    else:
        print(f"  OK: {pattern_name} removed")

print("\nFile size:", len(content), "chars")
print("Done!")
