# -*- coding: utf-8 -*-
import ast
with open(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\_test_run.py', encoding='utf-8') as f:
    code = f.read()
try:
    ast.parse(code)
    print('Syntax check PASSED')
    print(f'Total lines: {len(code.splitlines())}')
except SyntaxError as e:
    print(f'Syntax ERROR: {e}')
    print(f'  File {e.filename}, line {e.lineno}, col {e.offset}')
    # Show context
    lines = code.splitlines()
    start = max(0, e.lineno - 3)
    for i in range(start, min(len(lines), e.lineno + 2)):
        marker = '>>> ' if i + 1 == e.lineno else '    '
        print(f'{marker}{i+1}: {lines[i][:120]}')
