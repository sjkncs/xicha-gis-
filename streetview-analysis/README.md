# Streetview Analysis (街景图像分析)

VLM辅助的街景图像障碍物识别与城市空间分析管道。

## 目录结构

```
streetview-analysis/
├── scripts/            # 分析脚本（批处理、推理、可视化）
├── gpu_scripts/       # GPU推理相关脚本
├── results/           # JSON格式结果文件
│   ├── all_sim_results.json           # 模拟结果汇总
│   ├── all_sim_results_categorized.json  # 分类后的模拟结果
│   ├── yolo_results_merged.json       # YOLO检测结果（合并版）
│   ├── yolo_results_per_image.jsonl   # 每张图片的YOLO结果
│   ├── results.json                   # 综合推理结果
│   └── street_summary.json            # 街道汇总
├── annotated_streetview/   # VLM标注后的街景图像
├── raw_streetview/        # 原始街景图像
├── baidu_streetview/     # 百度街景图像
├── city_twin_output/     # 城市双胞胎可视化输出
├── picture_extracted/     # 从街景中提取的图片
├── trajectory_output/     # 轨迹分析输出
├── heatmaps/             # 热力图
└── outputs/             # 综合输出结果
```

## 核心脚本说明

| 脚本 | 功能 |
|------|------|
| `batch_segmentation*.py` | 批量图像分割 |
| `city_twin_builder.py` | 城市双胞胎构建 |
| `full_pipeline.py` | 完整处理管道 |
| `obstacle_analysis*.py` | 障碍物分析 |
| `StreeView_year.py` | 按年份收集街景数据 |
| `trajectory_sampler.py` | 轨迹采样分析 |
| `segment_by_nvidia_api.py` | NVIDIA API图像分割 |
| `continuous_collector.py` | 持续数据采集 |
| `fix_all_results.py` | 结果修复与合并 |

## 数据说明

- **annotated_streetview**: VLM（视觉语言模型）标注后的街景图，标注了障碍物类型和高度
- **raw_streetview**: 原始街景图像
- **baidu_streetview**: 百度街景源图像
- **picture_extracted**: 从分析结果中提取的特征图片

## 依赖

主要依赖：Python 3.8+, PyTorch, OpenCV, PIL, requests

详见各脚本顶部 `requirements` 或 `import` 声明。
