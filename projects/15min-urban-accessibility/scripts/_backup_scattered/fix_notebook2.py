# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# === FIX 1: POI Cell (index 13) ===
# Replace the generate_supplementary_poi logic with real integrated POI loading
cell13 = nb['cells'][13]
new_source = [
    "# ============================================================================\n",
    "# 加载真实 POI 数据（nanshan_poi_integrated.csv）\n",
    "# 数据来源：final_integrate.py（高德 API 采集 + ground truth 融合）\n",
    "# 包含：设施名称、分类、坐标、火星坐标系、设施类型、夜间服务标注\n",
    "# ============================================================================\n",
    "\n",
    "POI_INTEGRATED_PATH = os.path.join(BASE_DIR, 'osm_data', 'nanshan_poi_integrated.csv')\n",
    "\n",
    "def load_real_poi(path):\n",
    "    \"\"\"\n",
    "    加载 nanshan_poi_integrated.csv 并进行列映射\n",
    "    列映射：\n",
    "      gcj_lon -> lng, gcj_lat -> lat\n",
    "      facility_type (已有) 保留\n",
    "      night_service_final -> night_service\n",
    "      supply 从 facility_type 推导（模拟大众点评评分）\n",
    "    \"\"\"\n",
    "    df = pd.read_csv(path)\n",
    "    print(f\"Loaded POI records: {len(df):,}个\")\n",
    "    \n",
    "    # 列映射（GCJ-02 坐标系）\n",
    "    df = df.rename(columns={'gcj_lon': 'lng', 'gcj_lat': 'lat'})\n",
    "    \n",
    "    # 南山区边界过滤（bbox 内）\n",
    "    df = df[\n",
    "        (df['lng'] > BBOX['west']) & (df['lng'] < BBOX['east']) &\n",
    "        (df['lat'] > BBOX['south']) & (df['lat'] < BBOX['north'])\n",
    "    ].copy()\n",
    "    print(f\"Within BBOX: {len(df):,}个\")\n",
    "    \n",
    "    # 夜间服务列\n",
    "    if 'night_service_final' in df.columns:\n",
    "        df['night_service'] = df['night_service_final'].astype(bool)\n",
    "    else:\n",
    "        df['night_service'] = False\n",
    "    \n",
    "    # 供给水平（supply）：从设施类型推导，模拟大众点评评分归一化\n",
    "    SUPPLY_MAP = {\n",
    "        '医疗保健': 1.8, '药店': 1.5, 'hospital': 1.8, 'clinic': 1.4, 'pharmacy': 1.5,\n",
    "        '便利店': 1.2, 'convenience': 1.2, 'supermarket': 1.6, '超市': 1.6,\n",
    "        '银行': 1.3, 'bank': 1.3, 'ATM': 1.4, 'atm': 1.4,\n",
    "        '学校': 1.5, 'school': 1.5, 'kindergarten': 1.4, '幼儿园': 1.4,\n",
    "        '大学': 1.5, 'university': 1.5,\n",
    "        '公交站': 1.8, 'bus_stop': 1.8, 'subway': 1.9,\n",
    "        '交通设施': 1.7, '地铁站': 1.9, '地铁': 1.9,\n",
    "        '休闲娱乐': 1.4, '餐饮服务': 1.3, '购物服务': 1.2,\n",
    "        '住宿服务': 1.3, '政府机构': 1.5, '公共设施': 1.4,\n",
    "        '生活服务': 1.2, '公司企业': 1.0,\n",
    "        '商务写字楼': 1.1, '其他': 1.0,\n",
    "    }\n",
    "    def get_supply(ftype):\n",
    "        base = SUPPLY_MAP.get(str(ftype), 1.0)\n",
    "        return base + np.random.uniform(-0.2, 0.2)\n",
    "    \n",
    "    if 'supply' not in df.columns or df['supply'].isna().all():\n",
    "        np.random.seed(42)\n",
    "        df['supply'] = df['facility_type'].apply(get_supply).clip(0.3, 2.0)\n",
    "    \n",
    "    # 保留必要列\n",
    "    keep_cols = ['name', 'facility_type', 'lng', 'lat', 'night_service', 'supply', 'category1', 'category2']\n",
    "    keep_cols = [c for c in keep_cols if c in df.columns]\n",
    "    df = df[keep_cols].copy()\n",
    "    df['source'] = 'Gaode+GroundTruth'\n",
    "    \n",
    "    return df\n",
    "\n",
    "if os.path.exists(POI_INTEGRATED_PATH):\n",
    "    poi_df = load_real_poi(POI_INTEGRATED_PATH)\n",
    "    print(\"\\n[OK] 使用真实 POI 数据（nanshan_poi_integrated.csv）\")\n",
    "else:\n",
    "    print(f\"[WARN] POI 文件不存在: {POI_INTEGRATED_PATH}\")\n",
    "    print(\"回退到模拟数据...\")\n",
    "    poi_df = generate_supplementary_poi(BBOX)\n",
    "\n",
    "print(f\"\\n最终 POI 数据集: {len(poi_df):,} 个设施\")\n",
    "print(\"\\n设施类型分布:\")\n",
    "print(poi_df['facility_type'].value_counts().to_string())\n",
    "print(f\"\\n夜间服务设施: {poi_df['night_service'].sum():,}个 ({poi_df['night_service'].mean()*100:.1f}%)\")\n",
]

cell13['source'] = new_source
print("Cell 13 (POI) replaced successfully")

# === FIX 2: supply/rating cell (index 19) ===
# Change the supply generation to use facility_type derived values if 'supply' missing
cell19 = nb['cells'][19]
src19 = ''.join(cell19['source'])
new_src19_lines = []
for line in cell19['source']:
    # Replace the simulated supply/rating section
    if "if 'rating' not in poi_df.columns:" in line:
        new_src19_lines.append(
            "    # supply 已在 POI 加载阶段从 facility_type 推导\n"
        )
        new_src19_lines.append(
            "    if 'supply' not in poi_df.columns or poi_df['supply'].isna().all():\n"
        )
        new_src19_lines.append(
            "        poi_df['supply'] = 1.0  # fallback\n"
        )
        new_src19_lines.append(
            "        print('[NOTE] supply 使用默认值 1.0')\n"
        )
        new_src19_lines.append(
            "    else:\n"
        )
        new_src19_lines.append(
            "        poi_df['supply'] = poi_df['supply'].fillna(1.0)\n"
        )
    elif "'supply' = np.random.uniform(0.5, 1.0" in line or "'supply' = poi_df['rating'].fillna(0.5)" in line:
        # Skip these lines (replaced above)
        continue
    else:
        new_src19_lines.append(line)
cell19['source'] = new_src19_lines
print("Cell 19 (supply/rating) fixed")

# === FIX 3: Verify key column names used by 2SFCA and distance calc ===
# Check if NetworkDistanceCalculator uses 'lng'/'lat' or 'gcj_lon'/'gcj_lat'
# Based on the earlier analysis, poi_df uses 'lng'/'lat' so we need to ensure
# the integrated POI also has these columns (FIX 1 already handles this)

# === FIX 4: Check if poi_df gets filtered to only POIs within road network ===
# The road network covers full Shenzhen, poi_df is within BBOX which is also full Shenzhen
# This should be fine

# === FIX 5: Export pipeline - add SDI computation ===
# Find export cell
export_cell_idx = None
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))
    if 'SDI_elderly' in src or 'vulnerability_level' in src:
        export_cell_idx = i
        break

if export_cell_idx is not None:
    print(f"Export cell found at index {export_cell_idx}")
    # Show first 10 lines of export cell
    cell = nb['cells'][export_cell_idx]
    print("Export cell source (first 20 lines):")
    for j, line in enumerate(cell['source'][:20]):
        print(f"  {j}: {line.rstrip()[:100]}")
else:
    print("Export cell not found - will search by index")

# Save
with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False)
print("\nNotebook saved successfully!")
