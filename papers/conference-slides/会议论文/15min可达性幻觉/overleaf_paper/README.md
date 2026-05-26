# Overleaf 论文上传指南

## 项目信息

- **论文标题**: Unveiling the Accessibility Illusion: Day-Night Accessibility Gap and Time Poverty in Shenzhen's 15-Minute City
- **中文标题**: 15分钟城市日-夜可达性差距与时间贫困分析
- **作者**: 宋阳霆 (2023315113), 张潇晗 (2023315112)
- **单位**: 哈尔滨工业大学（深圳）建筑学院 城乡规划系
- **年份**: 2026

## 文件夹结构

```
overleaf_paper/
├── main.tex              # 主论文文件
├── figures/             # 图片文件夹
│   ├── fig1_framework.png
│   ├── fig2_day_night.png
│   ├── fig3_spatial.png
│   ├── fig4_night_service.png
│   ├── fig5_radar.png
│   ├── fig6_time_poverty.png
│   ├── fig7_building_data.png
│   ├── fig7_tpi_heatmap.png
│   ├── fig8_aii_barchart.png
│   ├── fig9_radar_charts.png
│   ├── fig10_sai_vs_gta.png
│   ├── fig11_supply_demand.png
│   ├── fig12_saii_map.png
│   └── fig13_community_type.png
├── tables/              # 表格文件夹（预留）
├── references/          # 参考文献
│   └── references.bib
└── README.md            # 本文件
```

## Overleaf 上传步骤

### 步骤1: 创建新项目

1. 登录 Overleaf: https://www.overleaf.com
2. 点击 "New Project" → "Blank Project"
3. 项目名称设置为: `15MinuteCity_Accessibility_Analysis`

### 步骤2: 上传文件

1. 点击项目设置图标 (⚙️)
2. 选择 "Upload" 或 "上传"
3. **推荐方法**: 直接拖拽整个 `overleaf_paper` 文件夹到上传区域
4. 或者逐个上传:
   - 先上传 `main.tex`
   - 上传 `references/references.bib`
   - 上传所有图片到 `figures/` 文件夹

### 步骤3: 创建文件夹

在 Overleaf 中:
1. 点击 "Add files" → "New folder"
2. 创建以下文件夹:
   - `figures`
   - `tables`
   - `references`

### 步骤4: 设置主文档

1. 点击 `main.tex` 文件
2. 点击右上角 "Menu" (☰)
3. 设置 "Main document" 为 `main.tex`

## 编译设置

### 编译器选择

- 推荐使用: **XeLaTeX** 或 **PDFLaTeX**
- 设置方法: Menu → Compiler → XeLaTeX

### 依赖包

Overleaf 已预装以下包:
- IEEEtran
- graphicx
- xcolor
- amsmath, amssymb
- hyperref
- cite
- algorithm, algorithmicx
- siunitx
- threeparttable

## 图片引用

论文中的图片引用格式:

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.8\linewidth]{figures/fig6_time_poverty.png}
\caption{Time Poverty Index Distribution}
\label{fig:tpi}
\end{figure}
```

图片会自动从 `figures/` 文件夹加载。

## 参考文献

参考文献文件 `references/references.bib` 包含论文引用的所有文献。

引用格式:
```latex
\citep{moreno202115minute}  % 括号引用
\citet{allam2022operationalising}  % 文中引用
```

## 论文结构

| 章节 | 内容 |
|------|------|
| 1. Introduction | 研究背景与贡献 |
| 2. Literature Review | 文献综述 |
| 3. Methodology | 研究方法 |
| 4. Results | 研究结果 |
| 5. Discussion | 讨论 |
| 6. Conclusion | 结论 |

## 关键数据

| 指标 | 数值 |
|------|------|
| 研究社区数 | 402 |
| 总人口 | 184.4万 |
| 夜间可达性下降 | 77.9% |
| 平均可达性比率 | 0.909 |
| 严重时间贫困 | 6.5% |

## 常见问题

### Q: 图片不显示
A: 确保图片文件在 `figures/` 文件夹中，且文件名与 `.tex` 中引用一致。

### Q: 编译错误
A: 检查是否使用了正确的中文字体，Overleaf 默认支持中文。

### Q: 参考文献缺失
A: 点击 "Recompile" 按钮，或手动运行 BibTeX。

## 联系方式

- 宋阳霆: 2023315113@hit.edu.cn
- 张潇晗: 2023315112@hit.edu.cn
