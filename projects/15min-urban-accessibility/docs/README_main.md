# 深圳市南山区 15 分钟城市时间贫困研究

**— 基于改进两步移动搜索法 (Modified 2SFCA) 与路网可达性的时空公平性分析 —**

Target Journal: *Computers, Environment and Urban Systems* (CEUS, JCR Q1)

---

## 项目版本说明

本项目分为两个版本，**不删除任何历史文件**：

| 版本 | 文件夹 | 数据 | 状态 |
|------|--------|------|------|
| **v2（推荐使用）** | `v2_real_data/` | 真实人口数据（184.44万） | ✅ 当前最新 |
| v1（仅供参考） | `backup_v1_estimated/` | 估算人口数据（约160万） | ⚠️ 历史版本 |

### v2 真实数据版本（当前使用）
- **人口数据**：南山区2025年初常住人口 **184.44万**
- **数据来源**：深圳市南山区人民政府官网 https://www.szns.gov.cn/xxgk/sjfb/
- **路网**：深圳路网数据（真实路网，27,843条，密度28.0 km/km²）
- **分析方法**：网络 Dijkstra 最短路径（替代 Haversine 直线距离）

### v1 估算数据版本（仅供参考）
- **人口数据**：约160万（早期估算，非官方数据）
- **路网**：OSMnx 步行网络
- **分析方法**：Haversine 直线距离

---

## 研究目标

**核心问题**：揭示 15 分钟生活圈在统计可达性背后，对弱势群体（城中村居民、老年人、残障人士、儿童）的真实可达性鸿沟。

### 可达性"幻觉"现象

| 维度 | 统计视角 | 真实体验 |
|------|----------|----------|
| **问题定义** | GIS 测算的设施覆盖率良好 | 弱势群体实际可及性很差 |
| **原因** | 设施存在 ≠ 夜间可及 | 时间维度剥夺 |
| **典型案例** | 城中村周边设施密集 | 夜间 70% 设施关闭 |

---

## 核心指标体系

### 1. SAI (Spatial Accessibility Index) 空间可达性指数
- 标准化白天可达性 (0-1)
- 基于 Modified 2SFCA 方法计算

### 2. TPI (Time Poverty Index) 时间贫困指数
- **定义**：夜间相对剥夺率 (%)
- **公式**：`TPI = (夜间可达性 - 日间可达性) / 日间可达性 × 100%`
- **解释**：
  - TPI > 0：夜间可达性下降（时间剥夺）
  - TPI < 0：夜间可达性反而更好（夜间优势）

### 3. SAII (Spatio-temporal Accessibility Illusion Index) 时空可达性幻觉指数
- 复合剥夺指标：`SAII = SAI × |TPI|`
- 识别高白天可达性但夜间服务缺失的"幻觉区域"

### 4. 剥夺类型分类

| 类型 | 条件 | 含义 |
|------|------|------|
| **Temporal Illusion** | 高白天可达 + 高TPI | "白天天堂，夜间荒漠" |
| **Night Advantage** | 高白天可达 + 低/负TPI | 夜间设施充足 |
| **Dual Deprived** | 低白天可达 + 高TPI | 日夜双重剥夺 |
| **Well-Served** | 低白天可达 + 低TPI | 整体可达性低但稳定 |

---

## 项目结构

```
15分钟城市时间贫困研究/
│
├── 15min_urban_accessibility_SCI.ipynb   # 主分析 Notebook（SCI论文）
│
├── v2_real_data/                      # ★★★ 推荐使用：真实数据版本 ★★★
│   ├── p8_network_results.csv          # 真实数据分析结果
│   ├── p8_fig1_study_area.png         # Fig1 研究区概况 + 人口类型饼图
│   ├── p8_fig2_day_night.png         # Fig2 日夜间散点 + TPI分布直方图
│   ├── p8_fig3_spatial.png           # Fig3 空间分布四图（日间/夜间/TPI/SAII）
│   ├── p8_fig4_night_service.png     # Fig4 夜间服务覆盖 + SAII Top15
│   ├── p8_fig5_conclusion.png        # Fig5 发表级综合主图（六图合一）
│   ├── p8_fig6_supply_demand.png     # Fig6 供需平衡分析（日夜间对比）
│   ├── p8_fig7_saii_analysis.png    # Fig7 SAII时空幻觉专题分析
│   ├── p8_fig8_type_analysis.png      # Fig8 社区类型TPI分类对比
│   ├── p8_fig9_top_deprived.png       # Fig9 Top剥夺小区详细分析
│   └── scripts/p2_accessibility/
│       ├── p8_real_population.py              # 真实人口网络分析
│       ├── p8b_research_visualization_fixed.py # 研究级可视化（字体修复）
│       ├── p8b_research_visualization.py      # 研究级可视化
│       ├── p8c_supplementary_figures.py       # ★ v2补充图表（Fig6-10）
│       ├── p6_estimate_real_population.py     # 人口估算
│       └── check_all_data_quality.py          # 数据质量检查
│
├── backup_v1_estimated/                 # ⚠️ 历史版本（估算数据）
│   ├── p3_*.csv / p3_v3_*.png        # P3 历史图表
│   ├── p3b_*.csv / p3b_*.png         # P3b 历史图表
│   ├── p7_*.csv / p7_*.png           # P7 历史图表
│   └── scripts/                         # 旧版分析脚本
│
├── scripts/                            # ★ 分析工具集 ★
│   ├── data_collection/                # 数据采集
│   │   ├── p5_gaode_api.py              # 高德 POI API 采集
│   │   ├── p5b_analyze_night_service.py # 夜间服务推断
│   │   ├── p4_population_from_lights.py # 灯光遥感人口估算
│   │   ├── p4b_population_from_census.py # 普查人口估算
│   │   └── p5_meituan_dianping_api.py    # 美团数据采集
│   │
│   ├── analysis_tools/                 # 分析工具
│   │   ├── check_all_data_quality.py    # 全量数据质量检查
│   │   ├── check_boundary_files.py       # 边界文件检查
│   │   ├── core_framework.py           # 核心分析框架
│   │   └── spatio_temporal_*.py        # 时空可达性分析
│   │
│   ├── p2_accessibility/               # 可达性计算（旧版）
│   │   └── p2_verify*.py / p3_v3_visualization.py
│   │
│   ├── p3_illusion_analysis/          # 幻觉分析（旧版）
│   │   ├── p3_spatiotemporal.py
│   │   └── p3b_fix.py
│   │
│   ├── llm_integration/                # LLM 集成模块
│   │   ├── llm_client.py / analyzers.py / prompts.py
│   │   └── config.py / example_usage.py
│   │
│   ├── p0_night_service/              # 夜间服务标注（旧版脚本）
│   ├── p1_osm_data/                  # OSM 空间数据（旧版脚本）
│   ├── village_data/                  # 小区数据（旧版脚本）
│   └── _backup_scattered/             # 历史调试脚本（122个，废弃）
│
├── osm_data/                          # ★ OSM 空间数据 ★
│   ├── nanshan_poi_integrated_v3.csv  # 整合 POI (69,413条) [当前使用]
│   ├── nanshan_communities_real_population.csv  # 小区人口估算
│   ├── nanshan_villages_with_building.csv       # 小区与建筑匹配
│   ├── nanshan_road_network.*         # 深圳路网南山截取 [当前使用]
│   ├── nanshan_network_nodes.csv      # 路网节点
│   ├── cache/osm_responses/           # OSM API 原始响应缓存 (~229MB)
│   ├── poi_versions/                  # POI 历史版本（旧）
│   │   ├── nanshan_poi.csv ~ v5.csv  # 各版本 POI
│   │   └── poi.shp/.dbf              # 原始 shp
│   ├── village_versions/              # 小区数据旧版本
│   │   └── nanshan_villages_with_building.csv
│   └── road_versions/                # 路网旧版本（OSMnx graphml等）
│       ├── road_network.gpkg / road_network.graphml
│       └── download_summary.txt
│
├── data/gaode_poi/                   # ★ 高德 POI 数据 ★
│   ├── nanshan_night_service_poi.csv  # 夜间服务标注后
│   └── nanshan_night_service_poi_with_night_service.csv
│
├── building_data/                     # 建筑轮廓数据
│   └── nanshan_buildings_v2.geojson  # [当前使用]
│
├── llm_integration/                  # LLM 集成模块（已移至 scripts/）
│
├── archive/                          # ★ 历史归档（不删除）★
│   ├── guangdong_poi/               # 广东省 POI 原始数据
│   │   ├── guangdong.zip            # 广东省 OSM 数据包
│   │   └── 深圳市POI数据.csv        # 深圳市 POI 原始
│   ├── guangdong_district/           # 广东省区划原始数据
│   │   ├── 广东省POI_2022.*         # 广东 POI 2022 shp
│   │   ├── 2023区划_2023区划.*      # 广东 2023 区划 shp
│   │   └── ...
│   └── shenzhen_road_raw/           # 深圳原始路网数据
│       ├── 深圳市_区划边界_深圳市.*    # 深圳市行政区划边界
│       └── 深圳市_路网_深圳市.*       # 深圳真实路网
│
├── backup_data/                     # ★ 备份数据（不删除）★
│   ├── village_data/               # 小区数据备份
│   │   ├── sz_village.geojson      # 原始小区边界
│   │   ├── sz_village_geocoded.csv  # 含坐标小区（宝安+龙岗）
│   │   ├── nanshan_communities_synthetic.csv
│   │   ├── villages.db / import_villages.sql
│   │   └── *.txt                   # 集成说明
│   └── building_data/               # 建筑数据备份
│       ├── nanshan_buildings_v2.gpkg
│       └── nanshan_residential_buildings.geojson
│
├── docs/                             # ★ 文档 ★
│   ├── README_main.md              # 本文件
│   ├── DATA_ACQUISITION_GUIDE.md  # 数据获取指南
│   ├── diagnostic_report.txt         # 诊断报告
│   ├── encoding_fix_report.txt       # 编码修复报告
│   ├── pyrightconfig.json
│   ├── nb_backup_*.ipynb           # Notebook 历史备份（4个）
│   ├── 研究笔记*.md                 # 研究笔记（3个）
│   ├── arcgis投影工具_*/            # ArcGIS 工具（POI筛选等）
│   └── POI筛选工具_*/               # POI 筛选工具
│
└── cache/                           # 缓存（可清理）
    └── osm_responses/               # 高德/Overpass API 响应缓存
```

---

## 运行顺序（v2 真实数据版本）

### Step 1：数据采集（如需重新获取数据）

```bash
# 高德 POI 采集（需 API Key）
python scripts/data_collection/p5_gaode_api.py

# 夜间服务推断
python scripts/data_collection/p5b_analyze_night_service.py
```

### Step 2：数据质量检查

```bash
python v2_real_data/scripts/p2_accessibility/check_all_data_quality.py
```

### Step 3：网络可达性分析（推荐）

```bash
python v2_real_data/scripts/p2_accessibility/p8_real_population.py
```

### Step 4：生成研究级图表

```bash
python v2_real_data/scripts/p2_accessibility/p8b_research_visualization_fixed.py
```

---

## v2 真实数据分析结果

**数据来源**：
- 人口：南山区2025年初常住人口 **184.44万**（深圳市南山区人民政府 szns.gov.cn）
- 面积：187.53 km²
- 人口密度：9840 人/km²

**网络数据**：
- 道路：27,843 条，总长 5,253 km，密度 28.0 km/km²
- 步行网络：166,021 节点 / 368,331 边

**分析规模**：
- 小区：402 个，总人口 184.42万
- POI：69,413 个（日间），4,778 个（夜间）

**可达性结果**：

| 时段 | 均值（标准化） | 中位数 |
|------|-------------|--------|
| 日间 | 0.0973 | 0.0658 |
| 夜间 | 0.0866 | 0.0581 |

**TPI（时间贫困指数）分布**：

| TPI等级 | 小区数 | 人口 | 占比 |
|---------|--------|------|------|
| 严重剥夺 (TPI≥50%) | 26 | 11.58万 | 6.3% |
| 中度剥夺 (20-50%) | 13 | 6.02万 | 3.3% |
| 轻度剥夺 (5-20%) | 23 | 7.61万 | 4.1% |
| 无显著差距 (-5~5%) | 70 | 25.87万 | 14.0% |
| 夜间优势 (<-5%) | 270 | 133.33万 | **72.3%** |

**受夜间剥夺影响人口**：
- 62 个小区（15.4%），共 **25.22万人**（13.7%）处于时间贫困

---

## 技术栈

- **数据分析**：pandas, numpy, scipy
- **空间分析**：geopandas, shapely, networkx
- **统计分析**：scipy.stats, esda (Moran's I), libpysal
- **可视化**：matplotlib, geopandas
- **数据库**：sqlite3
- **LLM 集成**：支持 GPT-4 / Claude 等

---

## 数据来源

| 数据类型 | 来源 | 规模 |
|----------|------|------|
| 人口（v2） | 南山区人民政府 szns.gov.cn（2025年初） | 184.44万 |
| 人口（v1） | 估算（非官方） | ~160万 |
| POI 设施 | 高德地图 API | 69,413 条 |
| 路网 | 深圳路网数据（shp） | 南山区 27,843 条 |
| 小区 | nanshan_villages_with_building.csv | 402 个 |
| 建筑轮廓 | OSM Overpass API | 南山区内 |

---

## 核心结论

1. **"可达性幻觉"确实存在**：72.3%的人口居住在夜间服务反而更好的区域，但仍有**25.22万居民（13.7%）**经历明显夜间服务剥夺

2. **极化效应**：南部商业区（科技园等）夜间设施充足，TPI<-20%；北部城中村等老旧小区TPI高达200-340%

3. **夜间服务最大缺口**：医疗（尤其是牙科，中医）、运动健身，文化设施夜间覆盖率极低（<10%）

4. **研究价值**：深圳南山区作为中国最密集城区之一（9840人/km²），其时空可达性格局对"15分钟城市"规划具有典型示范意义

---

## 致谢

本项目数据采集与分析由 AI 辅助完成。

**研究团队**：深圳市 XX 研究团队
**联系邮箱**：xxx@xxx.edu.cn
