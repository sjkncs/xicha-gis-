# -*- coding: utf-8 -*-
"""Direct fix for p0_rebuild_night.py using binary mode"""
import ast

path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\p0_rebuild_night.py"

with open(path, 'rb') as f:
    content_bytes = f.read()

lines = content_bytes.split(b'\n')
for i, line in enumerate(lines):
    if b'is_night_true(row.get' in line:
        print(f"Line {i+1} (raw bytes): {line}")
        print(f"Decoded: {line.decode('utf-8')}")

# Find the exact line and fix it
new_lines = []
fixed = False
for i, line in enumerate(lines):
    if b'is_night_true(row.get("night_service"))' in line and not fixed:
        # Fix: replace with correct call (one extra closing paren removed)
        fixed_line = line.replace(
            b'is_night_true(row.get("night_service"))',
            b'is_night_true(row.get("night_service"))'
        )
        print(f"\nFix applied at line {i+1}:")
        print(f"  Before: {line}")
        print(f"  After:  {fixed_line}")
        new_lines.append(fixed_line)
        fixed = True
    else:
        new_lines.append(line)

if not fixed:
    print("WARNING: The problematic line was NOT found! Let's check all is_night_true calls:")
    for i, line in enumerate(lines):
        if b'is_night_true' in line:
            print(f"  Line {i+1}: {line}")

# Also fix line 242 - the v5_matched bracket issue
new_lines2 = []
fixed2 = False
for i, line in enumerate(new_lines):
    if b'v5_matched"]) & (gaode["night_service"]' in line and not fixed2:
        # Fix: v5_matched"]==True
        fixed_line2 = line.replace(
            b'gaode[(gaode["v5_matched"]) & (gaode["night_service"].apply(is_night_true) == True)]',
            b'gaode[(gaode["v5_matched"]==True) & (gaode["night_service"].apply(is_night_true) == True)]'
        )
        print(f"\nFix 2 at line {i+1}:")
        print(f"  Before: {line}")
        print(f"  After:  {fixed_line2}")
        new_lines2.append(fixed_line2)
        fixed2 = True
    else:
        new_lines2.append(line)

# Write back
with open(path, 'wb') as f:
    f.write(b'\n'.join(new_lines2))

print(f"\nFile written. Checking syntax...")
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
try:
    ast.parse(text)
    print("Syntax check PASSED ✓")
except SyntaxError as e:
    print(f"Syntax error: {e}")
    lines = text.split('\n')
    for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+3)):
        marker = '>>> ' if i+1 == e.lineno else '    '
        print(f"{marker}{i+1}: {lines[i][:120]}")
