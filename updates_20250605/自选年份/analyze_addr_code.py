"""
分析 n188 的统一地址编码结构，解析出行政区划层级
440305 = 广东省深圳市南山区
目标：解析出 街道/社区
"""
import csv
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
n188_path = SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview" / "samples" / "sample_points_n188.csv"

# 读取所有行
rows = []
with open(n188_path, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

print(f"Total rows: {len(rows)}")

# 分析统一地址编码结构
# 格式: 440305 + 007 + 015 + 01 + 001 + 001 + 37
# 广东省(44)深圳市(03)南山区(05) + 街道(3位) + 社区(3位) + ...具体楼栋
print("\n=== 地址编码分析 ===")
for row in rows[:20]:
    addr_code = row.get("统一地址编码", "")
    addr = row.get("常用地址", "")
    name = row.get("名称", "")
    if len(addr_code) >= 12:
        # 440305(省市区) + 3位街道 + 3位社区 + 3位网格 + 3位楼栋
        district = addr_code[:6]
        street = addr_code[6:9]
        community = addr_code[9:12]
        grid = addr_code[12:15]
        building = addr_code[15:]
        print(f"编码: {addr_code}")
        print(f"  区街社: {district}-{street}-{community}-{grid}-{building}")
        print(f"  地址: {addr} | {name}")
    else:
        print(f"短码: {addr_code} -> {addr}")
    print()
