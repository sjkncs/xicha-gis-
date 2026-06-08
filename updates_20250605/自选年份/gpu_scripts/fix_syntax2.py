#!/usr/bin/env python3
src = r"E:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_offline.py"
dst = r"E:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_offline.py.new"

with open(src, "rb") as f:
    data = f.read().decode("utf-8", errors="replace")

lines = data.split("\n")
fixed = []
for line in lines:
    s = line.rstrip()
    # Remove trailing ) when the line ends in extra )
    if s.endswith(')")') or s.endswith(')")'):
        line = line[:-1]
    fixed.append(line)

new_data = "\n".join(fixed)
with open(dst, "w", encoding="utf-8") as f:
    f.write(new_data)
print("Written to", dst)

import ast
try:
    ast.parse(new_data)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Still bad line {e.lineno}: {e.msg}")
    print(" ", e.text)
