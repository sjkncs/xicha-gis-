"""测试修复后的pipeline"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"e:\xicha gis 智能定位\自选年份")
import full_pipeline

# 清空旧缓存
import os
cache = full_pipeline.CACHE_DIR / "regeocode_cache.json"
if cache.exists():
    os.remove(cache)

# 测试
points = full_pipeline.load_sample_points()
print(f"加载: {len(points)} 个点")

results = full_pipeline.batch_regeocode_all(points[:5], delay=0.2)
for i, r in enumerate(results):
    if r:
        print(f"  [{i}] {r.get('district','')}{r.get('township','')}{r.get('neighborhood','')}")
    else:
        print(f"  [{i}] 失败")
