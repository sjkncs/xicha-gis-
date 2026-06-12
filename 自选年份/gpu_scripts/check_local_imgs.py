import json, os

with open(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\all_results_fixed.json", "r", encoding="utf-8") as f:
    data = json.load(f)

nanshan = [r for r in data if "/南山区/" in r["image"]]
print("南山区图片数:", len(nanshan))

local_root = r"e:\xicha gis 智能定位\自选年份\baidu_streetview\南山区"
if os.path.exists(local_root):
    streets = os.listdir(local_root)
    print("本地街道目录:", streets)
    for st in streets:
        st_path = os.path.join(local_root, st)
        if os.path.isdir(st_path):
            count = sum(len(files) for _, _, files in os.walk(st_path) if files)
            print(f"  {st}: {count} 张")
else:
    print("目录不存在:", local_root)

print()
print("第一张南山检测:")
r = nanshan[0]
print("JSON路径:", r["image"])
print("检测数量:", r["total_obstacles"])
for d in r["detections"][:3]:
    name = d["coco_name"]
    conf = d["conf"]
    zone = d["zone"]
    bbox = d["bbox"]
    print(f"  [{name}] conf={conf:.2f} zone={zone} bbox={[round(x,1) for x in bbox]}")

# 尝试从JSON路径映射到本地路径
# JSON: /root/autodl-tmp/.../南山区/南山/.../113.9263685_22.5129279/113.9263685_22.5129279_E_2022.jpg
# 本地: e:\xicha gis 智能定位\自选年份\baidu_streetview\南山区\南山\未知社区\OpenOther-开放其他\113.9263685_22.5129279\113.9263685_22.5129279_E_2022.jpg
img_path = r["image"]
parts = img_path.split("/")
print()
print("JSON路径分段:", parts)
