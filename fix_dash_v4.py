#!/usr/bin/env python3
"""Re-apply 9 dashboard changes by reading exact bytes."""
import os

path = '/home/admin/.openclaw/workspace/daily_stock_analysis/templates/dashboard_v2.html'
bak = path + '.bak2'
os.system(f'cp {path} {bak}')
print(f'Backup: {bak}')

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Change 1: Remove CSS .rpt-icon and .tech-row lines
new_lines = []
for line in lines:
    s = line.strip()
    if s.startswith('.rpt-icon{') or s.startswith('.rpt-icon:hover') or s.startswith('.rpt-refresh'):
        new_lines.append('\n')  # keep blank line
    elif s.startswith('.tech-row{display:') or s.startswith('.tech-row{grid-template-columns:repeat(3,'):
        new_lines.append('\n')
    else:
        new_lines.append(line)
lines = new_lines

# Find the table row line with stock-name onclick
for i, line in enumerate(lines):
    if "'<td class=\"sn\"><span class=\"stock-name\" onclick=\"openReport(\\'" in line:
        old_line = line
        
        # Extract the code var name (r.code or uid)
        # Pattern: onclick=\"openReport(\'\" + X + \"','\" + Y + \"')\"
        code_var = None
        name_var = None
        
        # The line looks like: '<td class="sn"><span class="stock-name" onclick="openReport(\'" + r.code + "','" + jsEsc(r.name) + "')\">" + esc(r.name) + '</span><span class="rpt-icon" id="rpt-' + r.code + '">➖</span><span class="rpt-refresh" onclick="regenerateReport(\'" + r.code + "')\" title=\"刷新报告\">🔄</span></td>' +
        
        lines[i] = "      '<td class=\"sn\"><span class=\"stock-name\">' + esc(r.name) + '</span>" + \
            "<button class=\"btn btn-primary btn-xs\" onclick=\"refreshStock(\\'\" + r.code + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:4px;line-height:1.6\">&#x1F504;</button>" + \
            "<button class=\"btn btn-sm\" onclick=\"editStock(\\'\" + esc(r.code) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px\">&#x270F;&#xFE0F;</button>" + \
            "<button class=\"btn btn-sm\" onclick=\"delStock(\\'\" + esc(r.code) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px;color:#c0392b\">&#x2716;</button></td>' +\n"
        break

# Find card header line
for i, line in enumerate(lines):
    if "'<span class=\"stock-name\" onclick=\"openReport(\\'" in line and 'font-weight:700;font-size:12px' in line:
        # This is the card header - replace it and the following 2 lines
        lines[i] = "        '<span class=\"stock-name\" style=\"font-weight:700;font-size:12px;color:#2d3436\">' + nm + '</span>" + \
            "<button class=\"btn btn-primary btn-xs\" onclick=\"refreshStock(\\'\" + uid + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:auto;line-height:1.6\">&#x1F504; 刷新</button>" + \
            "<button class=\"btn btn-sm\" onclick=\"editStock(\\'\" + esc(uid) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px\">&#x270F;&#xFE0F;</button>" + \
            "<button class=\"btn btn-sm\" onclick=\"delStock(\\'\" + esc(uid) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px;color:#c0392b\">&#x2716;</button>' +\n"
        # Blank out the next two lines (rpt-icon and rpt-refresh)
        if i+1 < len(lines):
            lines[i+1] = '\n'
        if i+2 < len(lines):
            lines[i+2] = '\n'
        # Also delete leftover lines that start with '        \'<span class=\"rpt'
        break

# Find watchlist card line
for i, line in enumerate(lines):
    if "'<span class=\"name stock-name\" style=\"font-size:12px\" onclick=\"openReport(\\'" in line:
        lines[i] = "          '<span class=\"name stock-name\" style=\"font-size:12px\">' + esc(s.name) + '</span>" + \
            "<button class=\"btn btn-primary btn-xs\" onclick=\"refreshWlStock(\\'\" + esc(s.code) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:4px;line-height:1.6\">&#x1F504;</button>" + \
            "<button class=\"btn btn-sm\" onclick=\"delWlStock(\\'\" + esc(s.code) + \"','\" + esc(g.name) + \"')\" style=\"padding:0 5px;font-size:10px;margin-left:2px;color:#c0392b\">&#x2716;</button>' +\n"
        # Remove the rpt-icon line after this
        if i+1 < len(lines) and 'rpt-icon' in lines[i+1]:
            lines[i+1] = '\n'
        break

# Change reportLink function
for i, line in enumerate(lines):
    if "function reportLink(code, name, small, isWl) {" in line:
        lines[i] = "function reportLink(code, name, small, isWl) {\n"
        lines[i] += "  return '';\n"
        lines[i] += "}\n"
        break

# Remove tech-row from StockHolmes card  
for i, line in enumerate(lines):
    if "// 技术指标行" in line:
        # Blank out the tech-row generation lines until '</div>' is found
        lines[i] = '\n'
        j = i + 1
        while j < len(lines):
            lines[j] = '\n'
            if "'</div>' +" in lines[j].strip():
                break
            j += 1
        break

# Add refreshStock/refreshWlStock before fetchIntraday
funcs = """// ===== Single Stock Refresh =====
function refreshStock(code) {
  if (!code) return;
  var btn = event && event.target;
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  fetch('/api/' + UK + '/portfolio/refresh-single/' + code)
    .then(function(r) { return r.json(); })
    .then(function(r) {
      if (r.success) { toast(code + ' \\u5DF2\\u5237\\u65B0', 'success'); loadP(); }
      else { toast(r.error || '\\u5237\\u65B0\\u5931\\u8D25: ' + code, 'error'); }
    })
    .catch(function(e) { toast('\\u5237\\u65B0\\u5931\\u8D25: ' + e.message, 'error'); })
    .finally(function() { if (btn) setTimeout(function() { btn.disabled = false; btn.innerHTML = '\\u{1F504}'; }, 3000); });
}

function refreshWlStock(code) {
  if (!code) return;
  var btn = event && event.target;
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  fetch('/api/' + UK + '/watchlist/refresh-single/' + code)
    .then(function(r) { return r.json(); })
    .then(function(r) {
      if (r.success) { toast(code + ' \\u5DF2\\u5237\\u65B0', 'success'); loadW(); }
      else { toast(r.error || '\\u5237\\u65B0\\u5931\\u8D25: ' + code, 'error'); }
    })
    .catch(function(e) { toast('\\u5237\\u65B0\\u5931\\u8D25: ' + e.message, 'error'); })
    .finally(function() { if (btn) setTimeout(function() { btn.disabled = false; btn.innerHTML = '\\u{1F504}'; }, 3000); });
}

"""

for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('function fetchIntraday'):
        lines.insert(i, funcs)
        break

# Update help text
for i, line in enumerate(lines):
    if '刷新行情' in line and '腾讯API' in line and '技术指标' not in line:
        if '个股刷新' not in line:
            lines[i] = "    <div>&#x1F504; <b>刷新行情</b>: 腾讯API拉取所有股票最新价+技术指标</div>\n"
            lines.insert(i+1, "    <div>&#x1F504; <b>个股刷新</b>: 卡片上的按钮，只刷新单只股票的全部数据</div>\n")
            lines.insert(i+2, "    <div>&#x1F4CB; <b>切换视图</b>: 表格/卡片视图切换</div>\n")
        break

# Comment out batchCheckReports
for i, line in enumerate(lines):
    if 'batchCheckReports()' in line:
        if line.strip().startswith('//'):
            pass
        else:
            lines[i] = line.replace('batchCheckReports()', '// batchCheckReports()')
        break

# Remove the batchCheckReports function and rptEid
in_batch_func = False
new_lines2 = []
for line in lines:
    s = line.strip()
    if s == 'async function batchCheckReports() {':
        in_batch_func = True
        continue
    if in_batch_func:
        if s == '}' or s == '}':
            in_batch_func = False
        continue
    if s == "function rptEid(code) { return 'rpt-' + code; }":
        continue
    new_lines2.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines2)

print(f'Written: {len(new_lines2)} lines')
print('Done!')
