# VLM Simulation Figures

VLM模拟结果对比图——对比原始街景与VLM感知的差异。

## 目录说明

包含原始图像与VLM感知结果的一一对比图，用于论文中展示VLM对街道空间的感知偏差。

### 命名规则

- `fig_sim_{N/S/E/W}.jpg` — 各方向（北/南/东/西）原始街景模拟图
- `fig_sim_{N/S/E/W}_vlm.jpg` — VLM感知版本
- `fig_sim_sample1.jpg` / `fig_sim_sample1_vlm.jpg` — 样本对比图

### 障碍物分级

- `fig_sim_low_obstacle.jpg` / `_vlm.jpg` — 低障碍物区域
- `fig_sim_moderate_obstacle.jpg` / `_vlm.jpg` — 中等障碍物区域
- `fig_sim_high_obstacle.jpg` / `_vlm.jpg` — 高障碍物区域

### 用途

用于论文中说明VLM在不同城市密度和绿化程度下的感知偏差，对应"15分钟城市时间贫困研究"中的幻觉分析部分。
