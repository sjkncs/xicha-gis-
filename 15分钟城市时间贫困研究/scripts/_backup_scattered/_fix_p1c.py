# -*- coding: utf-8 -*-
"""Fix NS_BBOX key quotes and run matching"""
import ast, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\p1c_match.py"
with open(path, 'rb') as f:
    data = f.read()

# Fix the NS_BBOX line - the Chinese quotes got corrupted
fixed = data.replace(
    b'{"south":22.45, "north":22.55, "west":113.85, "east":114.05}',
    b'{"south":22.45, "north":22.55, "west":113.85, "east":114.05}'
)
if fixed != data:
    print("Fixed NS_BBOX line")
    data = fixed

# Also fix the village query condition
# Make the bbox filter work with plain string keys
fixed2 = data.replace(
    b'NS_BBOX["south"]',
    b'NS_BBOX["south"]'
)
# Just check the keys are ASCII
print("Checking syntax...")
text = data.decode('utf-8')
try:
    ast.parse(text)
    print("Syntax OK, running...")
except SyntaxError as e:
    print(f"Syntax error at line {e.lineno}: {e.msg}")
    lines = text.split('\n')
    for i in range(max(0,e.lineno-3), min(len(lines),e.lineno+3)):
        print(('>>>' if i+1==e.lineno else '   ') + lines[i][:100])

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
