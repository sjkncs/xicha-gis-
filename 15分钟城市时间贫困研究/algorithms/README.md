# algorithms/ — 算法与模型模块

> 15分钟城市时间贫困研究 — 算法与深度学习模块

本目录包含所有核心算法和模型代码。

## 目录结构

```
algorithms/
├── optimization/          # 元启发式优化算法（核心求解器）
├── deep_learning/        # 深度学习模块（建筑分类/高度回归/形态分割）
├── streetview/          # 街景分析模块（LLM-Vision + DeepLabV3+）
└── utils/               # 通用工具函数
```

## 模块说明

### 1. optimization/ — 元启发式优化算法

**核心文件**: `meta_heuristic_solver.py`

集成 7 种元启发式算法用于求解路网最短路径：

| 算法 | 缩写 | 用途 |
|------|------|------|
| Genetic Algorithm | GA | 遗传算法 |
| Simulated Annealing | SA | 模拟退火 |
| Tabu Search | TS | 禁忌搜索 |
| Ant Colony Optimization | ACO | 蚁群算法 |
| Differential Evolution | DE | 差分进化 |
| Particle Swarm Optimization | PSO | 粒子群算法 |
| Neural Network | NN | 神经网络代理模型 |

**适配数据**：
- OSMnx 路网数据 (`osmnx.graph`)
- 南山区真实建筑/POI 数据
- 步行时间/综合成本为优化目标

### 2. deep_learning/ — 深度学习模块

**主文件**: `dl_gaode_integration.py`

三大核心模型：

| 模型 | 输入 | 输出 |
|------|------|------|
| BuildingTypeClassifier (CNN/ResNet18) | 建筑特征向量 (用途编码×16维, 楼层数, 周边POI密度) | 9类建筑用途概率 + 步行性风险评分 |
| BuildingHeightRegressor (MLP) | 高德建筑特征 + 周边设施密度 + 路网结构特征 | 预测楼层数 (MAE < 2层) / 估算楼间距 |
| UrbanMorphologySegmenter (ResNet50 + FPN) | 小区级聚合特征 (建筑密度, 用途多样性, 设施密度) | 4类城市形态分类 |

**数据来源**: 高德API房屋数据 (4121条, 南山区1166条有效)

### 3. streetview/ — 街景分析模块

**文件**:
- `section13_full.py` — 完整 Section 13 分析（融合三大数据源）
- `section13_streetview_analysis.py` — 街景 LLM-Vision 评分

**评分维度**:
- Walkability Scores (WS, 0-10) — 步行性评分
- Safety Indices (SI, 0-10) — 安全感评分
- Accessibility Indices (AI, 0-10) — 可达性评分
- Night Visibility Scores (NVS, 0-10) — 夜间可见度评分

> 注：街景影像可通过 OSM 等地理数据还原，无需额外高德API调用

### 4. utils/ — 工具函数

- `cleanup.py` — 数据清理工具

## 使用示例

```python
# 元启发式算法求解
from algorithms.optimization.meta_heuristic_solver import (
    GeneticAlgorithmSolver,
    SimulatedAnnealingSolver,
    DijkstraGroundTruth
)

# 深度学习模型推理
from algorithms.deep_learning.dl_gaode_integration import (
    BuildingTypeClassifier,
    BuildingHeightRegressor
)
```

## 依赖

- Python 3.8+
- numpy, pandas, networkx, osmnx
- tensorflow / pytorch
- matplotlib, scipy

## 研究背景

本模块支撑论文核心贡献：
- **可达性幻觉指数 (AII)**: 量化统计可达性与实际步行可达性之间的差距
- **元启发式最短路径算法**: 在大规模路网上提供接近 Dijkstra 精度的近似解
- **深度学习预测**: 从建筑数据预测步行性风险，准确率 86.3%
