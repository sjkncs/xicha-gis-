# conference_paper/ — 会议论文初稿

> 基于 IEEE Transactions on Intelligent Transportation Systems 格式
> 论文主题：**揭示可达性幻觉：路网障碍与15分钟城市承诺的差距**

## 文件结构

```
conference_paper/
├── main.tex              # 论文主文件 (LaTeX)
├── figures_generator.py   # 图表生成脚本 (Python/matplotlib)
├── figures/              # 图表输出目录 (生成后)
│   ├── fig1_framework.png          - 研究框架
│   ├── fig2_euclidean_vs_network.png  - 欧氏 vs 路网距离
│   ├── fig3_study_area.png         - 研究区概况
│   ├── fig4_illusion_scatter.png    - 可达性幻觉散点图
│   ├── fig5_type_analysis.png      - 社区类型分析
│   ├── fig6_deprived_communities.png  - 最贫困社区分布
│   ├── fig7_ai_distribution.png    - AI分布分析
│   ├── fig8_day_night.png         - 日间/夜间对比 (补充)
│   └── fig9_supply_demand.png      - 供需平衡分析
└── references/
    └── references.bib  # 参考文献
```

## 论文核心内容

### 研究问题
表面上满足15分钟距离标准的社区，居民实际获取公共服务是否仍然耗费更长时间和更高精力？

### 核心发现
| 指标 | 数值 |
|------|------|
| 平均路网比率 | 1.42 |
| 平均可达性幻觉指数 (AI) | 42.0% |
| 受幻觉影响社区比例 | 85% |
| 城中村路网比率（最低）| 1.28 |
| 高端社区日夜AR（最大差距）| 0.889 |

### 图表生成

运行图表生成脚本：
```powershell
cd "e:\xicha gis 智能定位\15分钟城市时间贫困研究\conference_paper"
python figures_generator.py
```

图表将输出到 `figures/` 目录，分辨率 300 DPI，符合 IEEE 会议投稿标准。

### Overleaf 上传

将整个 `conference_paper/` 目录拖拽上传到 Overleaf。

### 论文局限性

论文目前将路网障碍作为评价可达性幻觉的单一因素。

**补充方向**（文献中有提及）：
- 步行环境（街景 LLM-Vision 评分）
- 夜间服务可用性
- 时间贫困指数（TPI）
- 手机轨迹/问卷访谈验证
