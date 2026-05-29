"""测试百度街景下载"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"e:\xicha gis 智能定位\自选年份")
import full_pipeline

# 测试已知可用的坐标
test_pt = {
    "lng": 113.9263685,
    "lat": 22.5129279,
    "idx": 0,
    "urban_form": "Open/Other",
    "road_name": "登良路",
}
test_addr = {
    "district": "南山区",
    "township": "粤海街道",
    "neighborhood": "",
    "formatted_address": "广东省深圳市南山区粤海街道登良路",
}
test_form = "Open/Other"

print(f"测试下载: lng={test_pt['lng']}, lat={test_pt['lat']}")
print(f"街道: {test_addr.get('township')}, 形态: {test_form}")

# 获取 SID
print("\nStep 1: 获取 SID...")
sid = full_pipeline.xy_to_sid(test_pt["lng"], test_pt["lat"])
print(f"SID: {sid[:20] if sid else 'None'}...")

if sid:
    print("\nStep 2: 下载影像 (2022年, heading=0)...")
    result = full_pipeline.sid_to_date_img(sid, test_pt["lng"], test_pt["lat"], 0, 2022)
    if result and result.get("content"):
        print(f"成功! year={result['year']}, size={len(result['content'])}")
        # 保存测试
        test_path = full_pipeline.ARCHIVE_DIR / "test.jpg"
        full_pipeline.ARCHIVE_DIR.mkdir(exist_ok=True)
        with open(test_path, "wb") as f:
            f.write(result["content"])
        print(f"保存: {test_path}")
    else:
        print("失败!")

# 测试完整下载流程
print("\nStep 3: 完整流程 download_one_point...")
all_results = full_pipeline.download_one_point(test_pt, test_form, test_addr)
print(f"结果: {len(all_results)} 个文件")
for r in all_results:
    print(f"  heading={r.get('heading_label')} year={r.get('year')} success={r.get('success')}")
