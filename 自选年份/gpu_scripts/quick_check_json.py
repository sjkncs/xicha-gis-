#!/usr/bin/env python3
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'e:\xicha gis 智能定位\自选年份\gpu_scripts\results\all_results_fixed.json','r',encoding='utf-8') as f:
    data = json.load(f)

for r in data[:5]:
    print(repr(r['image']))
    print('  score=%.1f n_obs=%d cats=%s' % (r['accessibility_score'], r['total_obstacles'], r['categories']))
    print()
