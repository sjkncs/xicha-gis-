#!/usr/bin/env python3
"""Fix syntax errors in seg_inference_offline.py"""
import shutil, ast, sys

src = r"E:\xicha gis \u667a\u80fd\u5b9a\u4f4d\自选年份\gpu_scripts\seg_inference_offline.py"
dst = r"E:\xicha gis \u667a\u80fd\u5b9a\u4f4d\自选年份\gpu_scripts\seg_inference_offline.py.new"

try:
    with open(src, "rb") as f:
        raw = f.read()
    data = raw.decode("utf-8", errors="replace")
except Exception as e:
    print(f"Read error: {e}")
    sys.exit(1)

lines = data.split("\n")
fixed = []
for i, line in enumerate(lines):
    lineno = i + 1
    # Remove exactly one trailing ) that shouldn't be there
    # Strategy: look for patterns where )) or ))" or ))  appears at end of string literals
    stripped = line.rstrip()
    if stripped.endswith('))")') or stripped.endswith('))"")'):
        # Too many parens
        line = line[:-1]
    elif stripped.endswith(')))') and stripped.count('(') > stripped.count(')'):
        # More opens than closes, but still extra close at end
        line = line[:-1]
    elif stripped.endswith('))")"):
        line = line[:-1]
    fixed.append(line)

new_data = "\n".join(fixed)
try:
    ast.parse(new_data)
    print("Syntax OK after fix")
except SyntaxError as e:
    print(f"Still bad at line {e.lineno}: {e.msg}")
    print(f"  {e.text}")

with open(dst, "w", encoding="utf-8") as f:
    f.write(new_data)
print(f"Written to {dst}")
