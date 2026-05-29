import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'e:\xicha gis 智能定位\自选年份\gpu_scripts\results\sim_results_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

from collections import defaultdict
dir_obs = defaultdict(list)
for r in data:
    dir_obs[r['direction']].append(r['obstacle_score'])

for d in ['N', 'E', 'S', 'W']:
    vals = dir_obs[d]
    if vals:
        print(f"{d}: n={len(vals)}, mean={sum(vals)/len(vals):.1f}, max={max(vals):.1f}, min={min(vals):.1f}")

# Full summary stats
obs_scores = [r['obstacle_score'] for r in data]
print(f"\nOverall: mean={sum(obs_scores)/len(obs_scores):.1f}, median={sorted(obs_scores)[len(obs_scores)//2]:.1f}")
print(f"N={len(obs_scores)}")

# Direction
for d in ['N','E','S','W']:
    vals = dir_obs[d]
    mn = sum(vals)/len(vals)
    # dominant category - count detections per category per direction
    from collections import Counter
    cats = Counter()
    for r in data:
        if r['direction'] == d:
            for det in r['detections']:
                cats[det['coco_name']] += 1
    dom = cats.most_common(1)[0][0] if cats else 'none'
    print(f"{d}: n={len(vals)}, mean_obs={mn:.1f}, dominant={dom} ({cats.most_common(3)})")
