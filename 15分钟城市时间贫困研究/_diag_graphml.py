# -*- coding: utf-8 -*-
import sys, io, subprocess
# Patch stdout/stderr for UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

script = r'''
import sys
sys.path.insert(0, r'E:\xicha gis 智能定位\15分钟城市时间贫困研究')
from generate_real_figures import *
'''

result = subprocess.run(
    [sys.executable, '-c', script],
    capture_output=True, text=True, encoding='utf-8', errors='replace',
    cwd=r'E:\xicha gis 智能定位\15分钟城市时间贫困研究'
)
print(result.stdout)
print(result.stderr)
