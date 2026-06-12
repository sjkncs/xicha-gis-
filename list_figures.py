# -*- coding: utf-8 -*-
"""List all relevant figures for the report"""
import os, glob

base = r'E:\xicha gis 智能定位'

# Find all figures in 15min project
fig_patterns = [
    os.path.join(base, 'projects', '15min-urban-accessibility', '**', '*.png'),
    os.path.join(base, 'projects', '15min-urban-accessibility', '**', '*.jpg'),
]

results = []
for p in fig_patterns:
    for f in glob.glob(p, recursive=True):
        if 'node_modules' in f or '.git' in f:
            continue
        rel = f.replace(base, '').lstrip('\\')
        results.append((f, rel))

results.sort()
for f, rel in results:
    print(rel)
