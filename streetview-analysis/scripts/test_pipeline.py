"""快速验证 pipeline 各环节是否正常工作"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"e:\xicha gis 智能定位\自选年份")

import full_pipeline
print("Module loaded OK")
print(f"AMAP_KEY: {full_pipeline.AMAP_KEY[:8]}...")

# 1. 加载采样点
points = full_pipeline.load_sample_points()
print(f"\nStep 1: 加载了 {len(points)} 个采样点")
print(f"  前3个: {[(p['lng'], p['lat'], p['urban_form']) for p in points[:3]]}")

# 2. 逆地理编码前3个
print("\nStep 2: 逆地理编码测试（前3个）")
results = full_pipeline.batch_regeocode_all(points[:3], delay=0.2)
for i, r in enumerate(results):
    if r:
        print(f"  [{i}] {r.get('district','')}{r.get('township','')}{r.get('neighborhood','')}")
        print(f"      {r.get('formatted_address','')[:50]}")
    else:
        print(f"  [{i}] 失败")

# 3. 归档路径生成
print("\nStep 3: 归档路径生成")
for i, (pt, addr) in enumerate(zip(points[:3], results)):
    path = full_pipeline.make_archive_path(addr, pt["urban_form"], pt["lng"], pt["lat"])
    print(f"  [{i}] {path}")

# 4. 测试下载（第一个点，2022年）
print("\nStep 4: 测试下载（第一个点 113.9263685,22.5129279）")
test_pt = points[0]
test_result = full_pipeline.download_one_point(test_pt, test_pt["urban_form"], results[0])
print(f"  下载结果: {len(test_result)} 个文件")
for r in test_result:
    print(f"    heading={r.get('heading_label')} year={r.get('year')} success={r.get('success')}")
