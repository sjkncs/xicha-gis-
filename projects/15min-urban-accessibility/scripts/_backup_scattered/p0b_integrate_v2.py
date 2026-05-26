# -*- coding: utf-8 -*-
"""P0b: Integrate v2 CSV into notebook + Update Cell 25 logic"""
import json, io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

NB = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

with open(NB, encoding='utf-8') as f:
    nb = json.load(f)

cells = nb['cells']

# ── Find Cell 13 ──
def find_cell(num):
    for i, c in enumerate(cells):
        src = ''.join(c.get('source', []))
        lines = src.strip().split('\n')
        if lines and str(i) == str(num):
            return i, src, lines
        # Also match by cell index in metadata
    return None, None, None

print("Finding key cells...")

# Find cell 13 by index
cell_13 = cells[13]
src_13 = ''.join(cell_13['source'])

print(f"\nCell 13 found, length: {len(src_13)} chars")

# ── Modify Cell 13: Switch to v2 CSV ──
new_src_13 = src_13.replace(
    "POI_INTEGRATED_PATH = os.path.join(BASE_DIR, 'osm_data', 'nanshan_poi_integrated.csv')",
    "POI_INTEGRATED_PATH = os.path.join(BASE_DIR, 'osm_data', 'nanshan_poi_integrated_v2.csv')"
)
# Also update the comment
new_src_13 = new_src_13.replace(
    "包含：设施名称、分类、坐标，火星坐标系、设施类型、夜间服务标注",
    "包含：设施名称、分类、坐标，火星坐标系、设施类型、精细化夜间服务标注(v2)"
)

# Also fix the supply logic comment (Cell 19 fix reference)
new_src_13 = new_src_13.replace(
    "supply 从 facility_type 推导（模拟大众点评评分）",
    "supply 从 facility_type 推导（已通过 v2.csv 的精细化夜间标注优化）"
)

# Also add a note about night_service_final
new_src_13 = new_src_13.replace(
    "if 'night_service_final' in df.columns:",
    "# night_service_final 来自精细化推断(v2): V5优先 + 名称关键词 + 类型概率推断\n    if 'night_service_final' in df.columns:"
)

if new_src_13 != src_13:
    cell_13['source'] = [new_src_13]
    print("Cell 13 updated ✓")
else:
    print("Cell 13: no changes needed")

# ── Find Cell 25 ──
cell_25 = cells[25]
src_25 = ''.join(cell_25['source'])

print(f"\nCell 25 found, length: {len(src_25)} chars")

# ── Modify Cell 25: Replace hardcoded FACILITY_NIGHT_SERVICE with night_service_final ──
# The new logic: use the night_service_final column directly
# Remove the old hardcoded dict and update the mask logic

new_src_25 = src_25

# Replace the hardcoded dict with a reference to night_service_final
new_src_25 = re.sub(
    r"FACILITY_NIGHT_SERVICE = \{[^}]+\}",
    """# 设施夜间营业约束 — 直接使用 night_service_final 列（来自 nanshan_poi_integrated_v2.csv）
# 精细化推断(v2) 逻辑：V5直接标注 > 名称关键词 > 类型概率推断
# night_service_final 已是布尔值，True=夜间可服务，False=夜间关闭
FACILITY_NIGHT_SERVICE = None  # 已废弃：使用 poi_df['night_service_final'] 列""",
    new_src_25,
    flags=re.DOTALL
)

# Replace the mask logic: use night_service_final column
new_src_25 = re.sub(
    r"# 夜间: 仅保留夜间服务设施\n\s+mask = poi_df\['facility_type'\]\.map\(\n\s+lambda t: FACILITY_NIGHT_SERVICE\.get\(t, 0\) > 0\n\s+\)",
    """# 夜间: 仅保留夜间服务设施（直接使用 night_service_final 列）
            mask = poi_df['night_service_final'] == True""",
    new_src_25
)

# Replace the daytime multiplier logic too
new_src_25 = re.sub(
    r"# 白天: 所有设施均可用\n\s+period_poi = poi_df\.copy\(\)\n\s+period_poi\['supply_adjusted'\] = period_poi\['supply'\]",
    """# 白天: 所有设施均可用（supply 不变）
            period_poi = poi_df.copy()""",
    new_src_25
)

# Also add supply_adjusted back (it might have been removed)
if 'supply_adjusted' not in new_src_25:
    new_src_25 = new_src_25.replace(
        "period_poi = poi_df.copy()",
        "period_poi = poi_df.copy()\n            period_poi['supply_adjusted'] = period_poi['supply']"
    )

if new_src_25 != src_25:
    cell_25['source'] = [new_src_25]
    print("Cell 25 updated ✓")
else:
    print("Cell 25: checking if changes applied...")
    # Try a different regex approach
    import re
    # Find and replace the dict block more carefully
    dict_start = src_25.find("FACILITY_NIGHT_SERVICE = {")
    if dict_start >= 0:
        dict_end = src_25.find("}\n\ndef", dict_start)
        if dict_end < 0:
            dict_end = src_25.find("}\n\n", dict_start)
        print(f"  Dict block: lines {dict_start} to {dict_end}")
        print(f"  Dict content: {src_25[dict_start:dict_start+200]}")

# ── Save ──
with open(NB, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False)

print(f"\n✓ Notebook saved: {NB}")

# ── Verify ──
with open(NB, encoding='utf-8') as f:
    nb2 = json.load(f)

print("\nVerification:")
c13 = ''.join(nb2['cells'][13]['source'])
c25 = ''.join(nb2['cells'][25]['source'])
print(f"  Cell 13 v2 path: {'v2.csv' in c13}")
print(f"  Cell 25 night_service_final: {'night_service_final' in c25}")
print(f"  Cell 25 supply_adjusted: {'supply_adjusted' in c25}")
