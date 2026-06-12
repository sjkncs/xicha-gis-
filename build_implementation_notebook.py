# -*- coding: utf-8 -*-
"""Build the PPT-synchronized implementation notebook.

This notebook intentionally follows the exact scripts and output files used for
the current HIT PPT, instead of drawing independent demonstration charts. It is
meant to answer: "How was the PPT scheme implemented in code, data, metrics and
figures?"
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "projects" / "15min-urban-accessibility"
OUT_DIR = PROJECT / "notebooks"
OUT_DIR.mkdir(parents=True, exist_ok=True)
NB_PATH = OUT_DIR / "implementation_metrics_data_figures_方案实现.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip() + "\n")


def code(text: str, tags: list[str] | None = None):
    cell = nbf.v4.new_code_cell(text.strip() + "\n")
    if tags:
        cell.metadata["tags"] = tags
    return cell


nb = nbf.v4.new_notebook()
nb.metadata.update(
    {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    }
)

cells = []

cells.append(
    md(
        """
<div style="background:linear-gradient(120deg,#003f5c,#005375 55%,#0f766e);padding:24px 28px;border-radius:10px;color:white">
  <h1 style="margin:0;font-size:30px">PPT 同步版：南山区 15 分钟城市可达性幻觉研究实现说明</h1>
  <p style="margin:10px 0 0;font-size:16px;line-height:1.55">
  本 Notebook 与当前 PPT 图件生成脚本保持同一数据口径、同一绘图逻辑、同一输出文件。
  </p>
  <p style="margin:12px 0 0;font-size:13px;opacity:.92">
  重点说明：数据如何获得、指标如何计算、图纸如何绘制、PPT 中每张图如何由脚本生成。
  </p>
</div>

## 重要修订说明

上一版 Notebook 为了讲清楚方法流程，额外生成了几张示例统计图；这些图虽然可解释指标，但**不是 PPT 图件的原始生成逻辑**。  
本版已经改为以 PPT 的真实生成脚本为主线：

- 分层 GIS 总图：`redraw_total_gis_map_layers.py` + `redraw_total_gis_map.py`
- PPT 第 15-20 页样式与文字：`revise_layered_map_ppt_style.py`
- 街景语义结构图：`redraw_ppt_semantic_chart.py`
- 街景障碍评分图：`redraw_ppt_obstacle_chart.py`
- 报告/论文补充图：`redraw_report_figures.py`

因此，本 Notebook 中的“图表生成”优先展示和调用这些同源脚本；辅助诊断只作为说明，不再替代 PPT 图件。
        """
    )
)

cells.append(
    md(
        """
## 0. 环境、路径与字体

Notebook 的运行目录可能是 `notebooks/`，因此先自动定位项目根目录和工作区根目录。所有脚本路径、输入数据和输出图件都用实际文件定位。
        """
    )
)

cells.append(
    code(
        """
from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from IPython.display import display, Markdown, Image

def find_project_root() -> Path:
    candidates = [Path.cwd(), *Path.cwd().parents]
    for p in candidates:
        if (p / "accessibility_results.csv").exists() and (p / "osm_data").exists():
            return p
        nested = p / "projects" / "15min-urban-accessibility"
        if (nested / "accessibility_results.csv").exists() and (nested / "osm_data").exists():
            return nested
    raise FileNotFoundError("未找到 projects/15min-urban-accessibility")

PROJECT = find_project_root()
WORKSPACE = PROJECT.parents[1]
OUT = PROJECT / "notebook_outputs"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(WORKSPACE))

def setup_cn_font():
    for fp in [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]:
        if Path(fp).exists():
            font_manager.fontManager.addfont(fp)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120

setup_cn_font()

print("工作区根目录:", WORKSPACE)
print("项目根目录:", PROJECT)
print("Notebook输出目录:", OUT)
        """
    )
)

cells.append(
    md(
        """
## 1. PPT 图件生成脚本总览

下面这张表是当前 PPT/报告图件的“同步清单”。后续所有解释都围绕这些脚本展开，而不是另起一套绘图逻辑。
        """
    )
)

cells.append(
    code(
        """
script_manifest = pd.DataFrame([
    {
        "模块": "总图与真实图层读取",
        "脚本": "redraw_total_gis_map.py",
        "是否改PPT": "否",
        "主要输入": "边界SHP、nanshan_road_network.shp、building_data、facility_locations.json、accessibility_results.csv、route/network/trajectory JSON",
        "主要输出": "paper/figures/fig_total_time_poverty_map_optimized.png/pdf/json",
    },
    {
        "模块": "PPT第15-20页分层GIS图",
        "脚本": "redraw_total_gis_map_layers.py",
        "是否改PPT": "否",
        "主要输入": "调用 redraw_total_gis_map.py 读取同一批图层",
        "主要输出": "paper/figures/layered_total_map/fig_total_layer_01~06.png/pdf",
    },
    {
        "模块": "PPT第15-20页版式与图文插入",
        "脚本": "revise_layered_map_ppt_style.py",
        "是否改PPT": "是",
        "主要输入": "fig_total_layer_01~06.png + ppt_spatial_diagnostics.json + PPT模板第14页样式",
        "主要输出": "哈工大PPT...pptx 第15-20页",
    },
    {
        "模块": "PPT街景语义结构图",
        "脚本": "redraw_ppt_semantic_chart.py",
        "是否改PPT": "是",
        "主要输入": "streetview-analysis/gpu_scripts/results/seg_results.csv + 自选年份/yolo_results_merged.json",
        "主要输出": "_ppt_chart_work/semantic_structure_redrawn.png，并替换PPT第33页图",
    },
    {
        "模块": "PPT街景障碍评分图",
        "脚本": "redraw_ppt_obstacle_chart.py",
        "是否改PPT": "是",
        "主要输入": "脚本内 DISTRICTS/SCORES/COUNTS/BOTTOM_BLOCK 数组",
        "主要输出": "_ppt_chart_work/obstacle_score_redrawn.png，并替换PPT第33页图",
    },
    {
        "模块": "报告/论文补充图与断面图替换",
        "脚本": "redraw_report_figures.py",
        "是否改PPT": "否，改DOCX",
        "主要输入": "accessibility_results.csv、street_profiles、profile_summary.csv等",
        "主要输出": "paper/figures/fig1_framework.png、fig_four_index_spatial_comparison.png、fig11_four_index_comparison_sci.png 等",
    },
])

for col in ["脚本"]:
    script_manifest[col + "_存在"] = script_manifest[col].apply(lambda x: (WORKSPACE / x).exists())
display(script_manifest)
        """
    )
)

cells.append(
    md(
        """
## 2. PPT 分层 GIS 图的数据口径

这里特别强调一个容易混淆的点：  
`osm_data/nanshan_poi_integrated_v3_wgs84.csv` 是 POI 总表，而 PPT 分层总图脚本实际读取的是 `facility_locations.json`，再经过南山区边界过滤后进入地图。因此：

- 原始设施记录：约 69,422 条；
- PPT 分层图边界内 POI：66,424 个；
- 这个数字来自 `layered_total_map_summary.json`，与 PPT 第 15-20 页解释一致。
        """
    )
)

cells.append(
    code(
        """
def first_file(pattern: str) -> Path | None:
    matches = sorted(WORKSPACE.rglob(pattern), key=lambda p: (len(str(p)), str(p)))
    return matches[0] if matches else None

layer_summary_path = PROJECT / "paper" / "figures" / "layered_total_map" / "layered_total_map_summary.json"
diag_path = PROJECT / "paper" / "figures" / "layered_total_map" / "ppt_spatial_diagnostics.json"
layer_summary = json.loads(layer_summary_path.read_text(encoding="utf-8"))
diagnostics = json.loads(diag_path.read_text(encoding="utf-8"))

actual_inputs = []
for label, pattern in [
    ("PPT地图POI设施点", "facility_locations.json"),
    ("路由网络节点", "network_nodes.json"),
    ("路由网络边", "network_edges.json"),
    ("20m街景采样轨迹", "trajectory_preview_20m.csv.geojson"),
]:
    p = first_file(pattern)
    actual_inputs.append({
        "输入": label,
        "匹配模式": pattern,
        "实际路径": str(p.relative_to(WORKSPACE)) if p else "未找到",
        "文件大小MB": round(p.stat().st_size / 1024 / 1024, 2) if p else None,
    })

display(pd.DataFrame(actual_inputs))

layer_counts = pd.DataFrame([{"图层": k, "PPT脚本边界内数量": v} for k, v in layer_summary["layers"].items()])
display(layer_counts)

road_counts = pd.DataFrame([{"道路层级": k, "数量": v} for k, v in layer_summary["road_counts"].items()])
poi_counts = pd.DataFrame([{"POI类型": k, "数量": v} for k, v in layer_summary["poi_counts"].items()])
display(road_counts)
display(poi_counts)
        """
    )
)

cells.append(
    md(
        """
## 3. 实际脚本中的核心读取逻辑

下面直接从 `redraw_total_gis_map.py` 抽取函数源码。PPT 总图和分层图都通过这些函数读取数据，Notebook 不再另写一套 POI/路网读取逻辑。
        """
    )
)

cells.append(
    code(
        """
def source_of_functions(script_name: str, function_names: list[str]) -> str:
    path = WORKSPACE / script_name
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    tree = ast.parse(text)
    chunks = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in function_names:
            start = node.lineno - 1
            end = getattr(node, "end_lineno", node.lineno)
            chunks.append("\\n".join(lines[start:end]))
    return "\\n\\n".join(chunks)

core_read_source = source_of_functions(
    "redraw_total_gis_map.py",
    ["read_boundary", "read_roads", "read_buildings", "read_pois", "read_communities", "read_route_edges", "read_trajectory"],
)
display(Markdown("```python\\n" + core_read_source[:8000] + "\\n```"))
        """
    )
)

cells.append(
    md(
        """
## 4. 实际脚本中的分层绘图逻辑

PPT 第 15-20 页的六张图来自 `redraw_total_gis_map_layers.py`。该脚本不是重新生成另一套数据，而是 `import redraw_total_gis_map as total` 后调用同一批读取函数，再分层绘制。
        """
    )
)

cells.append(
    code(
        """
layer_source = source_of_functions(
    "redraw_total_gis_map_layers.py",
    [
        "load_layers",
        "figure_01_base",
        "figure_02_poi",
        "figure_03_routes",
        "figure_04_saii",
        "figure_05_synthesis",
        "figure_06_panel",
        "main",
    ],
)
display(Markdown("```python\\n" + layer_source[:10000] + "\\n```"))
        """
    )
)

cells.append(
    md(
        """
## 5. PPT 第 15-20 页实际输出图

下面展示的就是 PPT 当前使用的分层图源文件。重新生成命令是：

```bash
python redraw_total_gis_map_layers.py
python revise_layered_map_ppt_style.py
```

第一条命令只重绘图片；第二条命令会把图片和解释文字写入 PPT 第 15-20 页。
        """
    )
)

cells.append(
    code(
        """
layer_fig_dir = PROJECT / "paper" / "figures" / "layered_total_map"
layer_figs = [
    ("15 / 3.2A 多源空间证据链", "fig_total_layer_06_four_panel_evidence_chain.png"),
    ("16 / 3.2B 路网等级与建筑/AOI", "fig_total_layer_01_base_road_hierarchy.png"),
    ("17 / 3.2C POI服务供给", "fig_total_layer_02_poi_service_supply.png"),
    ("18 / 3.2D 步行路由与街景采样", "fig_total_layer_03_walk_route_streetview_sampling.png"),
    ("19 / 3.2E 社区/AOI与SAII风险", "fig_total_layer_04_community_aoi_saii_risk.png"),
    ("20 / 3.2F 低密度综合图", "fig_total_layer_05_low_density_synthesis.png"),
]

fig_table = []
for title, fn in layer_figs:
    p = layer_fig_dir / fn
    fig_table.append({
        "PPT页": title,
        "图件": fn,
        "存在": p.exists(),
        "大小MB": round(p.stat().st_size / 1024 / 1024, 2) if p.exists() else None,
        "更新时间": pd.Timestamp(p.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S") if p.exists() else "",
    })
display(pd.DataFrame(fig_table))

for title, fn in layer_figs:
    p = layer_fig_dir / fn
    if p.exists():
        display(Markdown(f"### {title}\\n`{p.relative_to(WORKSPACE)}`"))
        display(Image(filename=str(p), width=820))
        """
    )
)

cells.append(
    md(
        """
## 6. PPT 第 15-20 页版式与解释文字如何写入

图件进入 PPT 的脚本是 `revise_layered_map_ppt_style.py`。它的作用不是重新计算数据，而是：

1. 读取当前 PPT；
2. 复刻模板第 14 页的页眉、页脚、核心结论栏；
3. 把 `fig_total_layer_01~06.png` 放入第 15-20 页；
4. 把 `ppt_spatial_diagnostics.json` 中的社区、道路、路径、POI异常解释写入说明框。
        """
    )
)

cells.append(
    code(
        """
layout_source = source_of_functions(
    "revise_layered_map_ppt_style.py",
    ["add_template_header", "add_template_footer", "add_info_card", "rebuild_slide", "main"],
)
display(Markdown("```python\\n" + layout_source[:9000] + "\\n```"))
        """
    )
)

cells.append(
    md(
        """
## 7. 具体异常解释的数据来源

PPT 右侧说明框中的社区案例来自 `ppt_spatial_diagnostics.json`。  
该文件把高风险社区关联到邻近道路、路由边、慢行边、障碍边、断头节点、800m POI 和夜间 POI。
        """
    )
)

cells.append(
    code(
        """
diag_df = pd.DataFrame(diagnostics)
diag_view = diag_df[[
    "name", "area", "SAII", "TPI", "near_roads",
    "route_edges_500m", "ped_edges_500m", "barrier_edges_800m", "deadend_nodes_500m",
    "poi_800m", "night_poi_800m", "night_rate_800m", "poi_types_800m",
]].copy()
diag_view["邻近道路"] = diag_view["near_roads"].apply(lambda x: "、".join(x) if isinstance(x, list) else "")
diag_view["POI类型Top"] = diag_view["poi_types_800m"].apply(
    lambda d: "；".join([f"{k}:{v}" for k, v in list(d.items())[:5]]) if isinstance(d, dict) else ""
)
diag_view = diag_view.drop(columns=["near_roads", "poi_types_800m"])
display(diag_view.round(4))

def explain_case(r):
    roads = "、".join(r["near_roads"]) if isinstance(r["near_roads"], list) else "周边道路"
    return (
        f"{r['name']}（{r['area']}）邻近{roads}，SAII={r['SAII']:.4f}，TPI={r['TPI']:.1f}%。"
        f"500m路由边{int(r['route_edges_500m'])}条、慢行边{int(r['ped_edges_500m'])}条，"
        f"800m障碍边{int(r['barrier_edges_800m'])}条；"
        f"800m内POI {int(r['poi_800m'])}个，夜间可用{int(r['night_poi_800m'])}个"
        f"（夜间率{r['night_rate_800m']*100:.1f}%）。"
    )

for _, r in diag_df.head(6).iterrows():
    display(Markdown("- " + explain_case(r)))
        """
    )
)

cells.append(
    md(
        """
## 8. PPT 第 33 页两张街景图表的同源代码

PPT 第 33 页曾要求重绘两张图：

- 语义结构图：建筑界面、道路、绿视率、天空开敞度；
- 视觉障碍评分图：障碍评分、底部遮挡占比。

下面直接从对应脚本读取数据矩阵/参数，并展示当前已插入 PPT 的输出图。
        """
    )
)

cells.append(
    code(
        """
def import_script(script_name: str):
    path = WORKSPACE / script_name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

semantic = import_script("redraw_ppt_semantic_chart.py")
obstacle = import_script("redraw_ppt_obstacle_chart.py")

semantic_matrix = semantic.load_semantic_matrix()
display(Markdown("### 语义结构图实际聚合矩阵"))
display(semantic_matrix.round(3))

display(Markdown("### 视觉障碍评分图实际参数"))
obstacle_params = pd.DataFrame({
    "district": list(obstacle.DISTRICTS),
    "score": list(obstacle.SCORES),
    "n": list(obstacle.COUNTS),
    "bottom_block_pct": list(obstacle.BOTTOM_BLOCK),
})
display(obstacle_params)

chart_files = [
    ("PPT街景语义结构图", WORKSPACE / "_ppt_chart_work" / "semantic_structure_redrawn.png"),
    ("PPT街景障碍评分图", WORKSPACE / "_ppt_chart_work" / "obstacle_score_redrawn.png"),
]
for title, p in chart_files:
    display(Markdown(f"### {title}\\n`{p.relative_to(WORKSPACE)}`"))
    display(Image(filename=str(p), width=760))
        """
    )
)

cells.append(
    md(
        """
### 8.1 街景图表脚本源码片段
        """
    )
)

cells.append(
    code(
        """
semantic_source = source_of_functions("redraw_ppt_semantic_chart.py", ["load_semantic_matrix", "draw_chart", "replace_slide_picture"])
obstacle_source = source_of_functions("redraw_ppt_obstacle_chart.py", ["draw_chart", "replace_slide_picture"])
display(Markdown("#### redraw_ppt_semantic_chart.py\\n```python\\n" + semantic_source[:7000] + "\\n```"))
display(Markdown("#### redraw_ppt_obstacle_chart.py\\n```python\\n" + obstacle_source[:7000] + "\\n```"))
        """
    )
)

cells.append(
    md(
        """
## 9. 报告/论文补充图的同源输出

这些图主要服务报告和论文，也有部分内容可进入 PPT。它们来自 `redraw_report_figures.py` 或同一数据链路，下面展示当前已经生成的实际输出。
        """
    )
)

cells.append(
    code(
        """
report_figs = [
    ("研究框架图", PROJECT / "paper" / "figures" / "fig1_framework.png"),
    ("四指标空间对比", PROJECT / "paper" / "figures" / "fig_four_index_spatial_comparison.png"),
    ("SCI四指标对比", PROJECT / "paper" / "figures" / "fig11_four_index_comparison_sci.png"),
    ("总图：可达性幻觉综合地图", PROJECT / "paper" / "figures" / "fig_total_time_poverty_map_optimized.png"),
]
report_table = []
for title, p in report_figs:
    report_table.append({
        "图名": title,
        "路径": str(p.relative_to(WORKSPACE)),
        "存在": p.exists(),
        "大小MB": round(p.stat().st_size/1024/1024, 2) if p.exists() else None,
        "更新时间": pd.Timestamp(p.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S") if p.exists() else "",
    })
display(pd.DataFrame(report_table))

for title, p in report_figs:
    if p.exists():
        display(Markdown(f"### {title}\\n`{p.relative_to(WORKSPACE)}`"))
        display(Image(filename=str(p), width=820))
        """
    )
)

cells.append(
    md(
        """
## 10. 指标计算与 PPT 图件之间的承接关系

分层图脚本并不重新计算 `A_day_norm`、`A_night_norm`、`TPI`、`SAII`，而是读取 `accessibility_results.csv` 和 `section13_community_accessibility_illusion.csv` 的结果，再用于空间表达。

核心公式仍然是：

$$
TPI_i = \\frac{A^{night}_i - A^{day}_i}{A^{day}_i} \\times 100\\%
$$

$$
SAII_i = A^{day,norm}_i \\times \\frac{|TPI_i|}{100}
$$

街景校准则由 `WES`、`sidewalk_width_proxy`、`building_density_500m`、`AI_star_elderly`、`AI_star_wheelchair` 等字段进入综合解释。
        """
    )
)

cells.append(
    code(
        """
acc = pd.read_csv(PROJECT / "accessibility_results.csv")
env = pd.read_csv(PROJECT / "v2_real_data" / "section13_community_accessibility_illusion.csv")
names = pd.read_csv(PROJECT / "osm_data" / "nanshan_communities_real_population.csv")

metric_check = acc[["A_day_norm", "A_night_norm", "TPI", "SAII"]].describe().T
display(metric_check.round(4))

merged = acc.merge(
    env[["community_id", "WES", "sidewalk_width_proxy", "building_density_500m", "AI_star_elderly", "AI_star_wheelchair"]],
    on="community_id",
    how="left",
).merge(
    names[["id", "housetitle", "shangquan"]],
    left_on="community_id",
    right_on="id",
    how="left",
)

display(
    merged.nlargest(12, "SAII")[
        ["community_id", "housetitle", "shangquan", "A_day_norm", "A_night_norm", "TPI", "SAII", "WES", "sidewalk_width_proxy", "building_density_500m"]
    ].round(4)
)
        """
    )
)

cells.append(
    md(
        """
## 11. 可复现命令：哪些安全，哪些会改 PPT/DOCX

为了避免误改 PPT，下面把命令分为三类。Notebook 默认不执行这些命令；需要重跑时再把开关改成 `True`。
        """
    )
)

cells.append(
    code(
        """
commands = pd.DataFrame([
    {"类别": "安全重绘图片", "命令": "python redraw_total_gis_map.py", "影响": "只更新 paper/figures/fig_total_time_poverty_map_optimized.*"},
    {"类别": "安全重绘图片", "命令": "python redraw_total_gis_map_layers.py", "影响": "只更新 layered_total_map 下 01-06 分层图"},
    {"类别": "会改PPT", "命令": "python revise_layered_map_ppt_style.py", "影响": "重建 PPT 第15-20页，自动备份"},
    {"类别": "会改PPT", "命令": "python redraw_ppt_semantic_chart.py", "影响": "重绘并替换 PPT 第33页语义结构图，自动备份"},
    {"类别": "会改PPT", "命令": "python redraw_ppt_obstacle_chart.py", "影响": "重绘并替换 PPT 第33页障碍评分图，自动备份"},
    {"类别": "会改DOCX", "命令": "python redraw_report_figures.py", "影响": "重绘报告图并替换报告_final.docx相关图片，自动备份"},
])
display(commands)

RUN_SAFE_FIGURE_REGEN = False
RUN_PPT_MUTATING_REGEN = False

if RUN_SAFE_FIGURE_REGEN:
    for cmd in [["python", "redraw_total_gis_map.py"], ["python", "redraw_total_gis_map_layers.py"]]:
        subprocess.run(cmd, cwd=WORKSPACE, check=True)

if RUN_PPT_MUTATING_REGEN:
    # 注意：以下命令会修改 PPT，并生成备份。
    for cmd in [
        ["python", "revise_layered_map_ppt_style.py"],
        ["python", "redraw_ppt_semantic_chart.py"],
        ["python", "redraw_ppt_obstacle_chart.py"],
    ]:
        subprocess.run(cmd, cwd=WORKSPACE, check=True)

print("RUN_SAFE_FIGURE_REGEN =", RUN_SAFE_FIGURE_REGEN)
print("RUN_PPT_MUTATING_REGEN =", RUN_PPT_MUTATING_REGEN)
        """
    )
)

cells.append(
    md(
        """
## 12. 小结：本版与 PPT 的同步边界

本 Notebook 的同步原则是：

1. **图件不另画**：PPT 使用什么脚本，这里就解释什么脚本。
2. **数据不换源**：分层总图的 POI 使用 `facility_locations.json`，不是另一个 POI CSV 示例表。
3. **指标不重复造口径**：`TPI`、`SAII` 来自 `accessibility_results.csv`；街景校准来自 `section13_community_accessibility_illusion.csv`。
4. **PPT 修改脚本单独标记**：凡是会替换 PPT 或 DOCX 的脚本都默认不在 Notebook 中自动执行，只展示参数、源码和已生成输出。

这样，PPT 的图、报告的图和 Notebook 的说明三者使用的是同一套数据链路和同一批生成脚本。
        """
    )
)

nb["cells"] = cells
nbf.write(nb, NB_PATH)
print(NB_PATH)

