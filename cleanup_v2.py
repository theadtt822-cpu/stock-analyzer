#!/usr/bin/env python3
"""Remove remaining old patterns: rpt-refresh, tech-row, etc."""
import os

path = '/home/admin/.openclaw/workspace/daily_stock_analysis/templates/dashboard_v2.html'
os.system(f'cp {path} {path}.bak3')

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove the card-top rpt-refresh line (contains regenerateReport and rpt-refresh)
for i, line in enumerate(lines):
    if 'class="rpt-refresh"' in line and 'regenerateReport' in line and 'uid' in line:
        lines[i] = '\n'
        print(f"Removed line {i+1}: card-top rpt-refresh")

# Remove the watchlist rpt-refresh line
for i, line in enumerate(lines):
    if 'class="rpt-refresh"' in line and 'regenerateReport' in line and 'esc(s.code)' in line:
        lines[i] = '\n'
        print(f"Removed line {i+1}: watchlist rpt-refresh")

# Remove the reportLink function rpt-refresh (template literal)
for i, line in enumerate(lines):
    if 'rpt-refresh' in line and 'regenerateReport' in line and '${code}' in line:
        lines[i] = '\n'
        print(f"Removed line {i+1}: reportLink template literal rpt-refresh")

# Remove tech-row div from StockHolmes card (the one generating MA5/MA10/etc)
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith("'<div class=\"tech-row\" style=\"margin-top:4px\">'") or \
       stripped.startswith("'<div class=\"tech-row\"") or \
       stripped == "'</div>' +":
        lines[i] = '\n'
        # Also blank the MA lines that follow
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if s == "'</div>' +":
                lines[j] = '\n'
                break
            if any(x in s for x in ['MA5', 'MA10', 'MA20', 'MACD', 'RSI', 'tech-item']):
                lines[j] = '\n'
            j += 1

# Write clean version
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

# Verify
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

patterns = {
    'rpt-refresh (any)': 'rpt-refresh',
    'regenerateReport (call)': 'regenerateReport',
    'tech-row div': 'class="tech-row"',
}
all_clean = True
for name, pat in patterns.items():
    count = content.count(pat)
    status = 'OK' if count == 0 else f'WARN({count})'
    if count > 0:
        all_clean = False
    print(f'  {status}: {name}')

print(f'All clean: {all_clean}')
