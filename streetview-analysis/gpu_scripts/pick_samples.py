import json, os, shutil, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'e:\xicha gis 智能定位\自选年份\gpu_scripts\results\sim_results_v2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total: {len(data)} images")
print(f"\nObstacle score distribution:")
for r in sorted(data, key=lambda x: x.get('obstacle_score', 0)):
    print(f"  {r['coords']}_{r['direction']}: obs={r['obstacle_score']:.1f}, pass={r['passability']*100:.1f}%, n_dets={r['n_dets']}")

print(f"\nImages WITH detections (n_dets > 0):")
has_dets = [r for r in data if r['n_dets'] > 0]
for r in sorted(has_dets, key=lambda x: x['obstacle_score'], reverse=True):
    names = [d['coco_name'] for d in r['detections']]
    print(f"  {r['coords']}_{r['direction']}: obs={r['obstacle_score']:.1f}, pass={r['passability']*100:.1f}%, dets={names}")
