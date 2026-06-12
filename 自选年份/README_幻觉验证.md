# 可达性幻觉验证模块

本目录包含数字-物理对照验证系统，用于量化分析 15 分钟生活圈中 **"可达性幻觉"**（Reachability Illusion）——即数字规划模型中的可达性与真实街道环境之间的偏差。

---

## 核心文件

| 文件 | 功能 |
|------|------|
| `illusion_scorer.py` | 计算五维幻觉评分 |
| `street_view_verifier.py` | 街景路径验证与证据链生成 |
| `world_model_validator.py` | Tesla BEV + 3D Occupancy Network 世界模型对照验证 |
| `run_illusion_pipeline.py` | 统一流水线编排 |
| `illusion_output/illusion_summary.json` | 幻觉评分结果 |
| `verifier_output/evidence_chains.json` | 路径验证证据链 |
| `world_model_output/world_model_summary.json` | 世界模型验证摘要 |
| `world_model_output/bev_voxel_3d.json` | 3D Voxel 栅格数据（4层高度占用 + 流动场） |
| `world_model_output/road_geometry.json` | 数字路网几何数据 |
| `city_twin_output/illusion_verification_panel.html` | 可视化对照面板 |
| `world_model_output/world_model_panel.html` | 世界模型对照面板 |
| `world_model_output/tesla_world_3d.html` | Tesla-Style 3D Voxel 世界模型可视化（Three.js） |

---

## 五维幻觉评分体系

```
综合幻觉分 = 0.20×I + 0.25×II + 0.20×III + 0.20×IV + 0.15×V
```

| 维度 | 名称 | 数据来源 | 说明 |
|------|------|----------|------|
| I | 几何幻觉 | 路网统计 (walkable_stats.json) | 数字最短路径 vs 真实街道网络连通性 |
| II | 语义幻觉 | 街景分割 (seg_final_clean.csv) | POI 语义类型与实际土地利用的匹配偏差 |
| III | 接入幻觉 | 街景分割 | 数字路网存在但真实环境不可通行的比例 |
| IV | 体验幻觉 | 街景分割 (openness/canyon/density/walkability) | 实际行走体验与理论最优的偏差 |
| V | 公平幻觉 | 街景分割 × 人群权重 |弱势群体（老人/儿童/低收入）的体验损失 |

**评分区间含义：**
- `0.00–0.15` 低幻觉：规划与现实高度吻合
- `0.15–0.35` 中幻觉：存在系统性偏差，需重点关注
- `0.35–0.60` 高幻觉：大量真实街道与规划不符
- `0.60–1.00` 极高幻觉：规划模型与现实严重脱节

---

## 快速开始

### 一键运行（完整流水线）

```powershell
cd 自选年份
python run_illusion_pipeline.py
```

可选参数：
```powershell
# 仅评分，跳过路径验证
python run_illusion_pipeline.py --skip-verification

# 仅路径验证，跳过评分
python run_illusion_pipeline.py --skip-scoring

# 跳过世界模型验证（更快）
python run_illusion_pipeline.py --skip-world-model

# 自定义路径
python run_illusion_pipeline.py --sv-csv "baidu_streetview/segmentation_results_v3/seg_final_clean.csv" --sv-manifest "baidu_streetview/ns_manifest.csv" --network-stats "network_output/walkable_stats.json"
```

### 分步运行

```powershell
# Step 1: 幻觉评分
python illusion_scorer.py --sv-csv baidu_streetview/segmentation_results_v3/seg_final_clean.csv --network-stats network_output/walkable_stats.json --output illusion_output

# Step 2: 路径验证
python street_view_verifier.py --sv-manifest baidu_streetview/ns_manifest.csv --sv-csv baidu_streetview/segmentation_results_v3/seg_final_clean.csv --facility network_output/facility_locations.json --output verifier_output --interval 50 --max-dist 100

# Step 3: 世界模型验证 (Tesla BEV + 3D Occupancy Network)
python world_model_validator.py --sv-csv baidu_streetview/segmentation_results_v3/seg_final_clean.csv --network-stats network_output/walkable_stats.json --output world_model_output
```

### 启动对照面板

```powershell
# 幻觉验证面板
cd city_twin_output
python -m http.server 8899

# 世界模型面板
cd world_model_output
python -m http.server 8898

# Tesla 3D Voxel 世界模型（Three.js，不需要服务器，直接用浏览器打开）
# 双击打开: world_model_output/tesla_world_3d.html
# 或:
cd world_model_output
python -m http.server 8898
```

然后浏览器访问：
- `http://localhost:8899/illusion_verification_panel.html`
- `http://localhost:8898/world_model_panel.html`
- `http://localhost:8898/tesla_world_3d.html`

---

## 数据依赖

| 数据 | 路径 | 来源 |
|------|------|------|
| 街景分割结果 | `baidu_streetview/segmentation_results_v3/seg_final_clean.csv` | `batch_seg_final.py` (NVIDIA NIM VLM) |
| 街景嵥索引 | `baidu_streetview/ns_manifest.csv` | `StreeView_year.py` |
| 路网统计 | `network_output/walkable_stats.json` | `network.py` |
| 设施位置 | `network_output/facility_locations.json` | `network.py` |
| 街景图像 | `baidu_streetview/` (各子目录) | `StreeView_year.py` |

---

## 输出文件说明

### illusion_output/

| 文件 | 内容 |
|------|------|
| `illusion_summary.json` | 综合评分 + 五维评分 + 解读指南 |
| `per_neighborhood_illusions.json` | 按城市形态分类的详细评分 |
| `sv_with_illusions.csv` | 每条街景记录的幻觉标注 |

### verifier_output/

| 文件 | 内容 |
|------|------|
| `verification_summary.json` | 路径验证统计摘要 |
| `evidence_chains.json` | 每条路径的详细证据点（街景图 + VLM 分析） |
| `verified_paths.geojson` | 验证路径的 GeoJSON，含 gap score |

### world_model_output/

| 文件 | 内容 |
|------|------|
| `world_model_summary.json` | 世界模型验证综合评分与解读 |
| `physical_occupancy.json` | 物理占用栅格数据（含每个网格的 openness/canyon/density/building_pct/green_pct） |
| `digital_occupancy.json` | 数字占用栅格数据（基于 OSM 道路类型与中心度） |
| `embedding_comparison.json` | 物理与数字 4 维嵌入对比，含热点列表 |
| `planning_gap.json` | 欧氏路径与物理路径的 gap score 与详细偏差数据 |
| `bev_voxel_3d.json` | **Tesla 3D Voxel 栅格**：4 层高度占用 + 物理流动场 |
| `road_geometry.json` | **数字路网几何**：OSM 道路边线段 + 数字占用率 |
| `world_model_panel.html` | 世界模型对照可视化面板（独立 HTML，可直接双击打开） |
| `tesla_world_3d.html` | **Tesla-Style 3D Voxel Viewer**（Three.js，可直接双击打开） |

---

## 对照面板功能

### 幻觉验证面板 (illusion_verification_panel.html)

- **综合幻觉环**：SVG 圆环图显示当前综合幻觉分
- **五维雷达条**：各维度幻觉强度柱状图
- **路径 Gap 列表**：按 gap score 排序，点击飞至地图位置
- **证据链详情**：路径上每张街景图的 walkability / openness / canyon / density
- **CesiumJS 联动**：在 iframe 中同步飞向选中位置

### 世界模型面板 (world_model_panel.html)

- **幻觉假设评分仪**：SVG 半圆仪表盘，颜色渐变（绿→黄→红）
- **占用对比条**：物理占用 vs 数字占用并排柱状图，标注差异方向
- **嵌入空间指标**：余弦相似度、欧氏偏差、规划偏距均值
- **栅格可视化（三个视图）**：
  - **占用对照**：圆点颜色=物理占用，紫边=数字模型同时覆盖
  - **嵌入对比**：颜色=嵌入偏差强度，虚线圆圈=热点栅格
  - **规划路径**：粗线=物理路径（真实），细线=数字路径（欧氏），颜色=偏差等级
- **Tesla 参照说明**：解释 Occupancy Network → 物理世界模型的映射关系

### Tesla 3D Voxel 世界模型 (tesla_world_3d.html)

> **无需 HTTP 服务器，直接双击 HTML 文件即可在浏览器中打开**

**Tesla Occupancy Network 风格的 3D 世界模型可视化**，完全对齐 Tesla 的技术路线：

- **Bird's Eye View (BEV) 占用栅格**：将地理区域离散化为网格单元
- **4 层高度占用（Tesla Occupancy Layers）**：
  - Layer 0 **Ground** (0-1m)：路面/人行道表面 — 来源于 `road_pct`
  - Layer 1 **Pedestrian** (1-2.5m)：行人活动区 — 来源于 `canyon × (1-walkability)`
  - Layer 2 **Vehicle** (2.5-5m)：机动车/建筑立面 — 来源于 `building_pct × density`
  - Layer 3 **Canopy** (5-15m)：树冠/高层建筑 — 来源于 `green_pct + building_pct`
- **流动场可视化**：箭头显示物理通行方向场（基于 walkability 梯度）
- **数字路网叠加**：OSM 道路几何叠加，颜色表示数字乐观偏差
- **颜色图例**：蓝色=自由通行 → 绿色→ 红色=高占用（障碍）
- **交互控制**：
  - 鼠标旋转/平移/缩放（OrbitControls）
  - 键盘快捷键：0-3 切换高度层，R 切换路网，F 切换流动场，1-3 切换视图模式
  - 视角预设：3D Voxels / BEV Top-Down / Side View

---

## 模块设计思路

### illusion_scorer.py

```python
# 核心接口
def compute_illusion_scores(
    sv_csv: str,       # VLM 分割结果 CSV
    network_stats: str, # 路网统计 JSON
    output_dir: str,   # 输出目录
) -> dict: ...
```

**幻觉计算逻辑：**
- **I (几何)**：比较全连通路网 vs 实际步行可达路网，计算拓扑差异
- **II (语义)**：按城市形态分组，计算 POI 密度与形态类型的偏差
- **III (接入)**：`can_pass = 1 - obstacle_factor`，统计不可通行比例
- **IV (体验)**：加权组合 openness / canyon / density / walkability 偏差
- **V (公平)**：对老年人/儿童/低收入区域额外加权惩罚

### street_view_verifier.py

```python
# 核心接口
def verify_paths(
    sv_manifest: str,   # 街景嵥
    sv_csv: str,        # VLM 分割结果
    facility_locs: str,  # 设施位置
    output_dir: str,
    sample_interval_m: float = 50,
    max_match_distance_m: float = 100,
) -> dict: ...
```

**验证逻辑：**
1. 预设若干条代表性路径（住宅→商业、住宅→地铁等）
2. 在路径上按指定间隔采样点
3. 将采样点与最近的街景数据匹配（距离阈值内）
4. 计算 Gap Score = |路径理论可达性 - 真实街景可达性|
5. 输出证据链（每段的街景图 + VLM 分析 + 评分）

### world_model_validator.py (Tesla BEV + 3D Occupancy Network)

基于 Tesla Occupancy Network 和 Bird's-Eye View 概念，将真实街道与数字模型表示为统一的世界模型进行对比。

```python
# 核心接口
def validate_world_model(
    sv_csv: str,       # VLM 分割结果 CSV
    network_stats: str, # OSM 路网统计 JSON
    output_dir: str,
    grid_size_deg: float = 0.003,
) -> dict: ...
```

**Tesla 对齐架构（对比）：**

| Tesla 技术 | 本模块实现 | 数据来源 |
|-----------|----------|---------|
| Occupancy Grid (2D BEV) | `physical_occupancy.json` | 街景 VLM 分割 |
| Road Network (Vector Map) | `digital_occupancy.json` | OSM 路网 |
| Height Layers (多尺度占用) | `bev_voxel_3d.json` (4层) | 街景特征融合 |
| Flow/Vector Field | `physical_flow` in bev_voxel_3d | walkability 梯度 |
| Semantic Segmentation | `urban_form` / `embedding` | VLM 分割结果 |

**核心组件：**

| 组件 | 功能 |
|------|------|
| `GridOccupancy` | 将街景与 OSM 数据聚合到等大网格，计算物理/数字占用率 |
| `EmbeddingGrid` | 构建 4 维特征向量（道路类型/中心度/开阔度/格式一致性），对比物理与数字嵌入 |
| `PlanningGap` | 在网格上分别运行欧氏 A*（数字路径）和加权 A*（物理路径），量化路径偏距 |
| `compute_bev_occupancy_layers()` | **Tesla 4 层高度占用**（Ground/Pedestrian/Vehicle/Canopy） |
| `compute_road_geometry()` | **OSM 道路几何提取**（用于数字路网叠加） |

**幻觉假设评分公式：**
```
幻觉假设评分 = 0.30×(1-cos_sim) + 0.25×eucl_dev + 0.25×mean_gap + 0.20×|phys_occ - dig_occ|
```

**Tesla 参照：**
- Tesla Occupancy Network → 物理世界模型（基于真实街景感知）
- Tesla Bird's-Eye View → 数字世界模型（基于 OSM 道路拓扑）
- Tesla Height Layers → 4 层高度占用（Ground/Pedestrian/Vehicle/Canopy）
- Tesla Vector Field → 物理流动场（walkability 梯度方向）
- 两者的系统性偏差 → "可达性幻觉"

---

## 近期运行结果

### 幻觉评分

```
综合幻觉分: 0.2651
  I 几何幻觉:  0.5000  (网络拓扑与真实街道偏差较大)
  II 语义幻觉: 0.1273  (POI 分布与形态类型基本吻合)
  III接入幻觉: 0.2400  (约24%的数字路网节点实际不可通行)
  IV 体验幻觉: 0.4262  (真实行走体验与最优路径有明显差距)
  V 公平幻觉: 0.0000  (按居住类型分组，暂无差异化分析数据)
```

### 路径验证

```
  平均 Gap Score: 0.41
  低幻觉路径:    0 条
  中幻觉路径:    4 条
  高幻觉路径:    0 条
  极高幻觉路径:  1 条
```

### 世界模型验证 (2026-06-08) — Tesla BEV + 3D Occupancy

```
幻觉假设评分: 0.1707 (较低幻觉偏差，需关注特定路段)
  物理占用均值: 0.422  (真实环境约42%的空间有可达性constraint)
  数字占用均值: 0.218  (OSM模型假设约22%的空间有constraint)
  占用差异:     +0.205  (数字乐观偏差：数字模型低估了物理障碍)
  余弦相似度:   0.932  (嵌入空间高度吻合)
  欧氏偏差:     0.186
  规划偏距均值:  0.251
  网格单元:     34 个 (基于0.003°分辨率)

Tesla 3D Voxel:
  BEV 4层高度占用: Ground(0-1m) / Pedestrian(1-2.5m) / Vehicle(2.5-5m) / Canopy(5-15m)
  流动场: 基于 walkability 梯度的 2D 向量场
  数字路网: 道路几何叠加，颜色表示数字乐观偏差
```

---

## 集成到 city_twin_builder.py

幻觉验证模块已集成到主流程中。在完成街景采集、分割和路网构建后，运行：

```powershell
python city_twin_builder.py --step illusion
```

或在完整流程中自动执行：

```powershell
python city_twin_builder.py --step all
```
