# -*- coding: utf-8 -*-
"""Build an evidence-backed image provenance notebook.

The user's current requirement is broader than the PPT-only implementation
notebook: every project image/chart should be traceable to the code and data
that produced it. This script scans images and Python scripts, combines exact
text hits with known project directory rules, and writes a CSV/Markdown/Notebook
provenance bundle.

It intentionally does not run mutating PPT/DOCX scripts or remote GPU jobs.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import nbformat as nbf

try:
    from PIL import Image, ImageOps, ImageDraw, ImageFont
except Exception:  # pragma: no cover - notebook still useful without previews
    Image = None
    ImageOps = None
    ImageDraw = None
    ImageFont = None


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "projects" / "15min-urban-accessibility"
OUT_DIR = PROJECT / "notebook_outputs"
NB_DIR = PROJECT / "notebooks"
OUT_DIR.mkdir(parents=True, exist_ok=True)
NB_DIR.mkdir(parents=True, exist_ok=True)

MANIFEST_CSV = OUT_DIR / "image_provenance_manifest.csv"
MANIFEST_JSON = OUT_DIR / "image_provenance_manifest.json"
SUMMARY_CSV = OUT_DIR / "image_provenance_group_summary.csv"
SCRIPT_HITS_CSV = OUT_DIR / "image_provenance_script_hits.csv"
MANIFEST_MD = OUT_DIR / "image_provenance_manifest.md"
CONTACT_SHEET = OUT_DIR / "image_provenance_contact_sheet.png"
NB_PATH = NB_DIR / "all_project_image_provenance_全项目图像生成溯源.ipynb"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}

RELEVANT_ROOTS = [
    PROJECT,
    ROOT / "streetview-analysis",
    ROOT / "自选年份",
    ROOT / "appendix-vlm",
    ROOT / "figures-vlm",
    ROOT / "_ppt_chart_work",
    ROOT / "15分钟城市时间贫困研究",
    ROOT / "papers" / "conference-slides" / "会议论文" / "15min可达性幻觉" / "overleaf_paper",
]

SCRIPT_ROOTS = [
    ROOT,
    PROJECT,
    ROOT / "streetview-analysis",
    ROOT / "自选年份",
    ROOT / "papers" / "conference-slides" / "会议论文" / "15min可达性幻觉" / "overleaf_paper",
]

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".ipynb_checkpoints",
    "cache",
    "figure_redraw_backups",
    "auto-claude-code-research",
    "node_modules",
}

GENERATION_KEYWORDS = (
    "savefig",
    "imwrite",
    ".save(",
    "copy2",
    "copyfile",
    "sftp.get",
    "add_picture",  # used only to separate insertion; exact generator handled below
)
INSERTION_SCRIPT_HINTS = (
    "build_report",
    "embed_figures",
    "fix_appendix_images",
    "insert_layered_maps_into_ppt",
    "revise_layered_map_ppt_style",
)
GENERATOR_SCRIPT_HINTS = (
    "generate",
    "redraw",
    "figures_generator",
    "network_analysis_viz",
    "p8",
    "p9",
    "p10",
    "final_charts",
    "final_obstacle_detect",
    "render_only",
    "rerender",
    "annotate_images",
    "copy_figures",
    "copy_to_appendix",
    "vlm_",
    "seg_inference",
    "sim_run",
    "streetview_acquisition",
    "integrated_streetview_collector",
    "baidu_panorama_collector",
)

SECRET_PATTERNS = [
    (re.compile(r"(API_KEY\s*=\s*)[\"'][^\"']+[\"']", re.I), r"\1'<REDACTED>'"),
    (re.compile(r"(SSH_PASS\s*=\s*)[\"'][^\"']+[\"']", re.I), r"\1'<REDACTED>'"),
    (re.compile(r"(password\s*=\s*)[\"'][^\"']+[\"']", re.I), r"\1'<REDACTED>'"),
    (re.compile(r"(Authorization[\"']?\s*:\s*f?[\"']Bearer\s*)[^\"'}]+", re.I), r"\1<REDACTED>"),
]


@dataclass
class ScriptHit:
    script: str
    line_no: int
    kind: str
    snippet: str


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def clean_snippet(text: str) -> str:
    text = text.strip()
    for pattern, repl in SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    text = re.sub(r"\s+", " ", text)
    return text[:260]


def walk_files(roots: Iterable[Path], suffixes: set[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for current, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            cur = Path(current)
            if any(part in EXCLUDE_DIRS for part in cur.parts):
                continue
            for name in names:
                p = cur / name
                if p.suffix.lower() in suffixes and p not in seen:
                    seen.add(p)
                    files.append(p)
    return sorted(files, key=lambda p: rel(p).lower())


def image_size(path: Path) -> tuple[int | None, int | None]:
    if Image is None:
        return None, None
    try:
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None, None


def category_for(r: str) -> tuple[str, str]:
    s = r.replace("\\", "/")
    if "/notebook_outputs/" in s:
        return "Notebook输出图", "Notebook解释/预览图"
    if "/backup_v1_estimated/" in s:
        return "历史备份图件", "早期V1可达性/夜间服务/空间分布备份图"
    if "/data/dl_pipeline/images/" in s:
        return "深度学习管线图像", "高德静态图/语义分割/VLM管线输入输出图"
    if "/data/streetview/integrated_collection/images/amap_staticmap/" in s:
        return "高德静态地图采集测试图", "高德静态地图API采集/测试输出"
    if "/data/population/" in s and s.lower().endswith((".tif", ".tiff")):
        return "人口夜光栅格图像", "人口估计或夜间灯光栅格输入"
    if "/v2_real_data/p8_fig11" in s:
        return "建筑AOI补充图件", "建筑用途/楼层/密度与TPI叠加图"
    if "/v2_real_data/p8_fig" in s or s.startswith("projects/15min-urban-accessibility/p8_fig"):
        return "P8真实人口可视化图件", "研究区、日夜可达性、空间指标与夜间服务图"
    if "/v2_real_data/section13_walkability" in s:
        return "Section13街景综合图件", "街景步行环境与可达性幻觉综合结果"
    if "/paper/dl_integration_results" in s or "/paper/section13_results" in s:
        return "深度学习/街景论文图件", "深度学习步行环境或街景Section13结果图"
    if s.startswith("_ppt_chart_work/"):
        return "PPT重绘工作区图件", "PPT图表替换/原始图备份"
    if "/paper/figures/layered_total_map/" in s:
        return "PPT分层GIS图", "路线图/POI/AOI/路网/SAII分层表达"
    if "/paper/figures/" in s:
        return "论文与报告图件", "研究报告/论文正文或附录图"
    if "/conference_paper/figures/" in s:
        return "会议论文图件", "会议论文/报告可复用图"
    if "/overleaf_paper/figures/" in s:
        return "Overleaf论文图件", "LaTeX论文图件"
    if "/overleaf_paper/appendix_annotated/" in s:
        return "Overleaf附录街景标注图", "论文附录标注样本"
    if "/overleaf_paper/appendix_raw/" in s:
        return "Overleaf附录街景原图", "论文附录原始街景"
    if "/street_profiles_hq/" in s:
        return "SCI街道断面图", "楼栋高度/用途/道路断面批量图"
    if "/street_profiles/" in s:
        return "普通街道断面图", "楼栋高度/用途/道路断面批量图"
    if "/annotated_streetview/" in s:
        return "街景YOLO中文标注图", "原始街景经YOLO检测后叠加中文标注"
    if "/raw_streetview/" in s:
        return "街景原始影像", "采集/下载得到的街景原图"
    if s.startswith("自选年份/picture/"):
        return "街景采集测试图", "按坐标和朝向下载的早期街景测试图"
    if "/baidu_streetview/" in s and s.lower().endswith((".jpg", ".jpeg", ".png")):
        return "百度街景采集图", "街景采集/分割输入或输出"
    if "/gpu_scripts/results/annotated_cn/" in s:
        return "精选中文街景标注图", "GPU检测样本二次中文渲染"
    if "/gpu_scripts/results/vlm_full/" in s:
        return "VLM增强街景标注图", "中文标注图叠加VLM识别面板"
    if "/gpu_scripts/results/annotated_images/" in s:
        return "街景检测结果标注图", "YOLO检测结果可视化"
    if "/gpu_scripts/results/sim_v2_samples/" in s:
        return "街景仿真检测样本", "YOLO+语义分割仿真样本"
    if "/gpu_scripts/results/samples_gpu/" in s or "/gpu_scripts/samples_gpu/" in s:
        return "GPU下载标注样本", "远程GPU结果下载样本"
    if "/gpu_scripts/results/charts/" in s or "/gpu_scripts/results/category_bar_" in s or "/gpu_scripts/results/score_dist_" in s:
        return "街景障碍统计图", "障碍类别/评分/区级对比统计图"
    if "/gpu_scripts/results/heatmaps" in s or "/heatmaps/" in s:
        return "街景热力图/分割热图", "FCN/YOLO/语义分割热力图"
    if "/figures-vlm/" in s or s.startswith("figures-vlm/"):
        return "VLM论文图件", "VLM实验报告图"
    if "/appendix_annotated/" in s:
        return "报告附录街景标注图", "DOCX附录街景标注样本"
    if "/appendix_raw/" in s:
        return "报告附录街景原图", "DOCX附录原始街景"
    return "其他项目图片", "项目资产/中间图像"


def manual_mapping(r: str, filename: str) -> dict[str, str]:
    s = r.replace("\\", "/")
    out = {
        "generating_code": "",
        "source_data": "",
        "production_method": "",
        "rerun_command": "",
        "confidence": "",
        "evidence": "",
    }

    def set_map(code: str, data: str, method: str, command: str, confidence: str, evidence: str) -> dict[str, str]:
        out.update(
            generating_code=code,
            source_data=data,
            production_method=method,
            rerun_command=command,
            confidence=confidence,
            evidence=evidence,
        )
        return out

    if s.startswith("_ppt_chart_work/semantic_structure_redrawn.png"):
        return set_map(
            "redraw_ppt_semantic_chart.py",
            "streetview-analysis/gpu_scripts/results/seg_results.csv; 自选年份/yolo_results_merged.json",
            "按四类街景语义指标聚合矩阵绘制柱状/结构图，并替换PPT第33页对应图表。",
            "python redraw_ppt_semantic_chart.py",
            "exact_known",
            "固定输出文件名 semantic_structure_redrawn.png。",
        )
    if s.startswith("_ppt_chart_work/obstacle_score_redrawn.png"):
        return set_map(
            "redraw_ppt_obstacle_chart.py",
            "脚本内 DISTRICTS/SCORES/COUNTS/BOTTOM_BLOCK 数组",
            "按街景障碍评分、样本量与底部遮挡比例重绘PPT统计图，并替换PPT第33页。",
            "python redraw_ppt_obstacle_chart.py",
            "exact_known",
            "固定输出文件名 obstacle_score_redrawn.png。",
        )
    if s.startswith("_ppt_chart_work/slide33_shape14.png"):
        return set_map(
            "redraw_ppt_obstacle_chart.py",
            "哈工大PPT第33页原始shape导出图",
            "PPT第33页障碍评分原始图表截图/导出文件，用作重绘前后对照。",
            "由PPT图表重绘流程导出；通常无需单独重跑。",
            "workspace_artifact",
            "slide33_shape14.png 是第33页原始shape对照图。",
        )
    if s.startswith("_ppt_chart_work/slide33_shape19.png"):
        return set_map(
            "redraw_ppt_semantic_chart.py",
            "哈工大PPT第33页原始shape导出图",
            "PPT第33页语义结构原始图表截图/导出文件，用作重绘前后对照。",
            "由PPT图表重绘流程导出；通常无需单独重跑。",
            "workspace_artifact",
            "slide33_shape19.png 是第33页原始shape对照图。",
        )
    if "/paper/figures/layered_total_map/" in s and filename.startswith("fig_total_layer_"):
        return set_map(
            "redraw_total_gis_map_layers.py; redraw_total_gis_map.py",
            "自选年份/network_output/facility_locations.json; network_nodes.json; network_edges.json; trajectory_preview_20m.csv.geojson; 南山区边界/道路/建筑/社区数据",
            "读取同一批GIS底图、POI、路由和社区指标，分别绘制路网、POI、路径、SAII风险和综合低密度总图。",
            "python redraw_total_gis_map_layers.py",
            "directory_exact",
            "layered_total_map 目录和 fig_total_layer_* 命名由分层总图脚本控制。",
        )
    if filename.startswith("fig_total_time_poverty_map_optimized"):
        return set_map(
            "redraw_total_gis_map.py",
            "南山区边界SHP、nanshan_road_network.shp、building_data、facility_locations.json、accessibility_results.csv、route/network/trajectory JSON",
            "重绘带路网、建筑、社区、POI、路径、街景采样点和SAII风险的综合GIS总图。",
            "python redraw_total_gis_map.py",
            "exact_known",
            "固定输出 fig_total_time_poverty_map_optimized.*。",
        )
    if filename in {"fig_sv_obstacle_mosaic.png", "fig_sv_before_after_mosaic.png"}:
        return set_map(
            "generate_streetview_figures_v2.py",
            "appendix-vlm/appendix_annotated/appendix_annotated; appendix-vlm/appendix_raw/appendix_raw",
            "从294张街景标注图中按坐标/方向选择12个样本，绘制3x4标注拼图或原图-标注对照图。",
            "python generate_streetview_figures_v2.py",
            "exact_known",
            "脚本固定输出两个 fig_sv_* mosaic 文件。",
        )
    if s.startswith("appendix-vlm/appendix_annotated/"):
        return set_map(
            "regenerate_all_annot_final.py; regenerate_all_annot.py; regen_annot_v1.py",
            "appendix-vlm/appendix_raw/appendix_raw",
            "从附录街景原图读取坐标、方向和障碍类型目录，用中文字体重绘顶部分类条、方向标签和底部坐标说明。",
            "python regenerate_all_annot_final.py",
            "directory_match",
            "appendix-vlm/appendix_annotated 由全量中文重标注脚本维护。",
        )
    if s.startswith("appendix-vlm/appendix_raw/"):
        return set_map(
            "streetview-analysis/scripts/archive_streetview.py; analyze_all_sources.py",
            "自选年份/raw_streetview 或街景采集目录；坐标/方向/年份文件名",
            "原始街景样本按区域、类型、坐标目录归档，用于后续附录中文标注和mosaic拼图。",
            "按街景采集/归档脚本运行；Notebook不自动联网下载。",
            "raw_acquired",
            "appendix-vlm/appendix_raw 是报告附录原图目录。",
        )
    if "/street_profiles_hq/" in s:
        return set_map(
            "projects/15min-urban-accessibility/v2_real_data/generate_street_profiles_sci.py",
            "building_data/南山区-房屋楼栋基础数据_2920004003598.csv; profile_summary.csv",
            "按道路名和建筑坐标滑动窗口分组，依据楼层数估算高度，按建筑用途着色，生成SCI版街道断面图。",
            "python projects/15min-urban-accessibility/v2_real_data/generate_street_profiles_sci.py",
            "directory_match",
            "street_profiles_hq 批量目录由SCI断面图脚本生成。",
        )
    if "/street_profiles/" in s:
        return set_map(
            "projects/15min-urban-accessibility/v2_real_data/generate_street_profiles.py",
            "building_data/南山区-房屋楼栋基础数据_2920004003598.csv; osm_data/nanshan_poi_integrated_v3_wgs84.csv; profile_summary.csv",
            "按道路/空间聚类生成普通版街道断面图，包含建筑高度、用途颜色、SCR/EWW估计等说明。",
            "python projects/15min-urban-accessibility/v2_real_data/generate_street_profiles.py",
            "directory_match",
            "street_profiles 批量目录由普通断面图脚本生成。",
        )
    if "/gpu_scripts/results/annotated_cn/" in s:
        return set_map(
            "streetview-analysis/gpu_scripts/rerender_cn.py",
            "gpu_scripts/samples_gpu; gpu_scripts/results/sim_results_v2.json",
            "读取GPU下载标注图和仿真JSON，用PIL中文字体重绘右侧中文指标面板。",
            "python streetview-analysis/gpu_scripts/rerender_cn.py  # 含外部API/远程依赖，Notebook不自动执行",
            "directory_match",
            "annotated_cn 输出目录由 rerender_cn.py 配置。",
        )
    if "/gpu_scripts/samples_gpu/" in s or "/gpu_scripts/results/samples_gpu/" in s:
        return set_map(
            "streetview-analysis/gpu_scripts/download_samples.py; streetview-analysis/gpu_scripts/check_annotated.py",
            "远程GPU街景检测可视化结果；gpu_scripts/results/all_results_fixed.json",
            "从远程GPU结果中按南山区高/中/低障碍评分抽样下载标注样本，供中文重渲染和报告附录使用。",
            "python streetview-analysis/gpu_scripts/download_samples.py  # 需远程环境",
            "directory_match",
            "samples_gpu 为GPU下载标注样本目录。",
        )
    if "/gpu_scripts/results/vlm_full/" in s:
        return set_map(
            "streetview-analysis/gpu_scripts/rerender_cn.py",
            "gpu_scripts/results/annotated_cn; VLM API响应",
            "在中文标注图上增加VLM识别面板，形成双面板街景障碍解释图。",
            "python streetview-analysis/gpu_scripts/rerender_cn.py  # 含外部API/远程依赖，Notebook不自动执行",
            "directory_match",
            "vlm_full 输出目录由 rerender_cn.py 配置。",
        )
    if "/gpu_scripts/results/annotated_images/" in s:
        return set_map(
            "streetview-analysis/gpu_scripts/annotate_images.py",
            "gpu_scripts/results/all_results_fixed.json",
            "从YOLO检测JSON读取bbox/类别/评分，使用PIL中文字体叠加检测框和中文说明。",
            "python streetview-analysis/gpu_scripts/annotate_images.py",
            "directory_match",
            "annotated_images 输出目录由 annotate_images.py 配置。",
        )
    if "/gpu_scripts/results/sim_v2_samples/" in s or "/gpu_scripts/results/sim_samples/" in s:
        return set_map(
            "streetview-analysis/gpu_scripts/sim_run_v2.py; streetview-analysis/gpu_scripts/download_v3.py",
            "远程 /root/autodl-tmp/streetview_images/南山区; YOLO11x; DeepLabV3/FCN语义分割",
            "远程GPU/CPU脚本对南山区60张街景做YOLO检测和语义分割，绘制带指标面板的仿真样本，本地脚本下载结果。",
            "python streetview-analysis/gpu_scripts/sim_run_v2.py && python streetview-analysis/gpu_scripts/download_v3.py  # 需远程环境",
            "directory_match",
            "sim_v2_samples 由仿真脚本生成并由下载脚本落地。",
        )
    if (
        ("/gpu_scripts/results/charts/" in s and filename in {"category_distribution.png", "score_distribution.png", "district_comparison.png", "yolo_district_comparison.png"})
        or filename.startswith("category_bar_")
        or filename.startswith("score_dist_")
    ):
        return set_map(
            "streetview-analysis/gpu_scripts/final_charts.py; streetview-analysis/gpu_scripts/final_obstacle_detect.py; streetview-analysis/gpu_scripts/download_charts.py",
            "gpu_scripts/results/all_results_fixed.json; 远程FCN/YOLO热图",
            "按障碍类别、评分分布、视角类别和区级均值/标准差绘制最终统计图。",
            "python streetview-analysis/gpu_scripts/final_charts.py  # 含远程下载依赖",
            "exact_known",
            "最终图表/检测脚本固定输出障碍类别和评分分布统计图。",
        )
    if "/gpu_scripts/results/heatmaps_nanshan/" in s or "/gpu_scripts/results/heatmaps_yolo/" in s:
        return set_map(
            "streetview-analysis/gpu_scripts/final_charts.py; streetview-analysis/gpu_scripts/download_samples.py",
            "gpu_scripts/results/all_results_fixed.json; 远程 /root/autodl-tmp/streetview_analysis/output/heatmaps",
            "按南山区高/中/低障碍评分抽样下载FCN或YOLO热力图，用作报告示例。",
            "python streetview-analysis/gpu_scripts/final_charts.py  # 含远程下载依赖",
            "directory_match",
            "heatmaps_nanshan/heatmaps_yolo 目录由最终图表脚本下载维护。",
        )
    if "/gpu_scripts/results/heatmaps/" in s or "/heatmaps/" in s:
        return set_map(
            "streetview-analysis/scripts/obstacle_analysis.py; streetview-analysis/gpu_scripts/seg_inference_*.py; 自选年份/gpu_scripts/step3_run.py",
            "街景原图; 语义分割模型输出; obstacle/segmentation JSON",
            "将语义分割或障碍概率叠加到街景原图，形成空间热力/遮挡热图。",
            "按对应批处理脚本运行，具体见 manifest 的 exact_hit 脚本列。",
            "directory_inferred",
            "热图目录存在多个历史批处理脚本，按目录归属和精确命中共同判断。",
        )
    if "/annotated_streetview/" in s:
        return set_map(
            "streetview-analysis/gpu_scripts/render_only_v2.py; streetview-analysis/gpu_scripts/full_pipeline_local.py",
            "自选年份/raw_streetview; yolo11x_local.pt; all_sim_results.json",
            "本地YOLO检测后用PIL中文字体叠加bbox、障碍分数、道路比例和通行率面板。",
            "python streetview-analysis/gpu_scripts/render_only_v2.py",
            "directory_match",
            "annotated_streetview 输出目录由 render_only_v2.py/full_pipeline_local.py 配置。",
        )
    if "/raw_streetview/" in s or "/baidu_streetview/" in s:
        return set_map(
            "projects/15min-urban-accessibility/data/streetview/streetview_acquisition.py; integrated_streetview_collector.py; baidu_panorama_collector.py; streetview-analysis/scripts/archive_streetview.py",
            "trajectory_output/trajectory_preview_20m.csv.geojson; sample_points_n*.csv; 百度/腾讯/高德街景接口或下载目录",
            "按照轨迹采样点和方向采集或归档的原始街景，不是绘图脚本生成的统计图。",
            "按采集脚本配置运行；Notebook不自动联网下载。",
            "raw_acquired",
            "原始街景目录与采集/归档脚本路径匹配。",
        )
    if "/overleaf_paper/figures/" in s and filename.startswith("fig_sim_"):
        if filename.endswith("_vlm.jpg"):
            return set_map(
                "自选年份/gpu_scripts/vlm_batch.py; 自选年份/gpu_scripts/vlm_w.py",
                "overleaf_paper/figures/fig_sim_*.jpg/png; VLM API响应",
                "对论文仿真样本图进行VLM辅助标注，输出 *_vlm.jpg。",
                "python 自选年份/gpu_scripts/vlm_batch.py",
                "directory_match",
                "VLM脚本固定处理 fig_sim_* 并生成 *_vlm.jpg。",
            )
        return set_map(
            "streetview-analysis/gpu_scripts/copy_figures.py; 自选年份/gpu_scripts/update_latex_stats.py",
            "gpu_scripts/results/sim_v2_samples",
            "从仿真样本中按高/中/低障碍和方向选择代表图，复制为论文fig_sim_*文件。",
            "python streetview-analysis/gpu_scripts/copy_figures.py",
            "directory_match",
            "copy_figures.py 明确列出 fig_sim_* 代表样本复制规则。",
        )
    if "/overleaf_paper/figures/" in s:
        return set_map(
            "projects/15min-urban-accessibility/conference_paper/figures_generator.py; streetview-analysis/gpu_scripts/copy_figures.py; 自选年份/gpu_scripts/update_latex_stats.py",
            "conference_paper/figures; gpu_scripts/results/sim_v2_samples; Overleaf LaTeX图目录",
            "Overleaf论文图件由会议论文图表脚本直接输出，或从仿真样本/报告图件复制到LaTeX figures目录。",
            "python projects/15min-urban-accessibility/conference_paper/figures_generator.py",
            "directory_inferred",
            "overleaf_paper/figures 是LaTeX论文图件汇总目录。",
        )
    if "/overleaf_paper/appendix_annotated/" in s or "/overleaf_paper/appendix_raw/" in s:
        return set_map(
            "streetview-analysis/gpu_scripts/copy_to_appendix.py",
            "自选年份/raw_streetview; 自选年份/annotated_streetview",
            "将全量原始街景和YOLO中文标注图复制到Overleaf论文附录目录。",
            "python streetview-analysis/gpu_scripts/copy_to_appendix.py",
            "directory_match",
            "appendix_raw/appendix_annotated 目录由 copy_to_appendix.py 维护。",
        )
    if "/conference_paper/figures/" in s:
        return set_map(
            "projects/15min-urban-accessibility/conference_paper/figures_generator.py",
            "社区/POI/路网/指标表，部分图为脚本内模拟或论文示意数据",
            "会议论文统一图表脚本生成研究框架、研究区、幻觉散点、类型分析、日夜对比等图件。",
            "python projects/15min-urban-accessibility/conference_paper/figures_generator.py",
            "directory_match",
            "conference_paper/figures 由 figures_generator.py 统一输出。",
        )
    if "/v2_real_data/p8_fig11" in s:
        return set_map(
            "projects/15min-urban-accessibility/v2_real_data/p10_fig11_building_aoi.py; projects/15min-urban-accessibility/v2_real_data/scripts/p2_accessibility/p8c_fig11_only.py",
            "building_data/nanshan_buildings_v2.geojson; v2_real_data/p8_network_results.csv; osm_data/nanshan_road_network.shp",
            "基于OSM建筑AOI、楼层、用途和社区可达性结果，生成建筑用途、楼层热力、高层-TPI叠加和建筑密度图。",
            "python projects/15min-urban-accessibility/v2_real_data/p10_fig11_building_aoi.py",
            "directory_match",
            "p8_fig11* 文件由P10建筑AOI脚本固定输出。",
        )
    if "/v2_real_data/p8_fig" in s or s.startswith("projects/15min-urban-accessibility/p8_fig"):
        return set_map(
            "projects/15min-urban-accessibility/v2_real_data/scripts/p2_accessibility/p8b_research_visualization_fixed.py; projects/15min-urban-accessibility/generate_real_figures.py",
            "v2_real_data/p8_network_results.csv; osm_data/nanshan_road_network.shp; osm_data/nanshan_poi_integrated_v3.csv",
            "基于真实人口、日夜可达性、TPI/SAII、夜间POI覆盖与社区类型绘制P8研究级图件。",
            "python projects/15min-urban-accessibility/v2_real_data/scripts/p2_accessibility/p8b_research_visualization_fixed.py",
            "directory_match",
            "p8_fig* 由P8真实人口研究级可视化脚本固定输出。",
        )
    if "/v2_real_data/section13_walkability" in s or "/paper/section13_results" in s:
        return set_map(
            "projects/15min-urban-accessibility/section13_full_v2.py; projects/15min-urban-accessibility/algorithms/streetview/section13_full.py",
            "streetview segmentation/detection results; section13 community walkability metrics",
            "汇总街景步行环境感知、障碍检测和社区可达性幻觉指标，绘制Section13综合结果图。",
            "python projects/15min-urban-accessibility/section13_full_v2.py",
            "directory_match",
            "section13结果图由Section13脚本固定输出。",
        )
    if "/paper/dl_integration_results" in s:
        return set_map(
            "projects/15min-urban-accessibility/algorithms/deep_learning/dl_gaode_integration.py",
            "高德建筑/街景/步行环境深度学习集成指标",
            "汇总深度学习步行环境评估结果，生成集成分析图。",
            "python projects/15min-urban-accessibility/algorithms/deep_learning/dl_gaode_integration.py",
            "directory_match",
            "dl_integration_results.png 由深度学习集成脚本保存。",
        )
    if "/data/dl_pipeline/images/" in s:
        return set_map(
            "projects/15min-urban-accessibility/algorithms/deep_learning/dl_pipeline/segment_inference.py; projects/15min-urban-accessibility/algorithms/deep_learning/dl_pipeline/vlm_map_analysis.py",
            "data/dl_pipeline/images/raw; VLM/DeepLabV3/SegFormer模型输出",
            "原始高德静态图进入深度学习管线，结果图由语义分割推理或VLM地图分析脚本生成。",
            "python projects/15min-urban-accessibility/algorithms/deep_learning/dl_pipeline/run_pipeline.py --mode inference",
            "directory_match",
            "data/dl_pipeline/images 是DL管线输入/输出目录。",
        )
    if "/data/streetview/integrated_collection/images/amap_staticmap/" in s:
        return set_map(
            "projects/15min-urban-accessibility/data/streetview/test_staticmap_api.py; integrated_streetview_collector.py",
            "高德静态地图API; 测试坐标 113.9412,22.5308 或轨迹采样点",
            "调用高德staticmap接口下载PNG静态地图，用于街景/地图采集管线连通性测试。",
            "python projects/15min-urban-accessibility/data/streetview/test_staticmap_api.py",
            "exact_known",
            "test_staticmap_api.py 固定保存 test_single.png。",
        )
    if "/data/population/" in s and s.lower().endswith((".tif", ".tiff")):
        return set_map(
            "projects/15min-urban-accessibility/scripts/data_collection/p4_population_from_lights.py",
            "VIIRS夜间灯光或人口估计数据",
            "人口/夜光栅格输入文件，用于人口估计或空间指标校准，不是matplotlib生成图。",
            "python projects/15min-urban-accessibility/scripts/data_collection/p4_population_from_lights.py",
            "raw_acquired",
            "data/population 下的TIF为栅格数据资产。",
        )
    if s.startswith("自选年份/picture/"):
        return set_map(
            "streetview-analysis/scripts/StreeView_year.py; 自选年份/upload_images.py",
            "坐标点 113.9263685,22.5129279; 0/90/180/270度街景方向",
            "早期街景采集测试图，按同一坐标四个朝向下载保存，用于验证年份/方向参数。",
            "python streetview-analysis/scripts/StreeView_year.py",
            "raw_acquired",
            "自选年份/picture/1 下为四方向街景采集测试图。",
        )
    if "/backup_v1_estimated/" in s:
        return set_map(
            "projects/15min-urban-accessibility/backup_v1_estimated/scripts/*.py",
            "backup_v1_estimated/*.csv; 早期可达性估算数据",
            "早期V1估算流程的备份图件，保留用于对照，不作为当前PPT/报告主图。",
            "按 backup_v1_estimated/scripts 下对应脚本运行。",
            "archive_directory",
            "backup_v1_estimated 为早期备份目录。",
        )
    if "/figures-vlm/" in s or s.startswith("figures-vlm/"):
        return set_map(
            "streetview-analysis/gpu_scripts/generate_latex*.py; streetview-analysis/gpu_scripts/generate_report.py",
            "gpu_scripts/results/all_results_fixed.json; VLM/YOLO街景分析结果",
            "VLM/YOLO街景分析报告中的论文图件或复制图件，供LaTeX/附录使用。",
            "python streetview-analysis/gpu_scripts/generate_report.py",
            "directory_inferred",
            "figures-vlm 为VLM报告图件目录。",
        )
    if "/gpu_scripts/" in s and s.lower().endswith((".png", ".jpg", ".jpeg")):
        return set_map(
            "streetview-analysis/gpu_scripts/check_*.py; seg_inference_*.py; sim_run*.py",
            "GPU脚本临时输入/输出、调试样本或远程下载样本",
            "GPU推理调试和模型验证过程中生成的临时可视化样本。",
            "按对应gpu_scripts脚本运行；多数为调试中间图。",
            "directory_inferred",
            "gpu_scripts 根目录图片多为调试样本。",
        )
    if "/paper/figures/" in s:
        return set_map(
            "projects/15min-urban-accessibility/paper/generate_figures.py; redraw_report_figures.py; v2_real_data/scripts/p2_accessibility/*.py",
            "accessibility_results.csv; section13_community_accessibility_illusion.csv; OSM/建筑/POI/社区数据",
            "论文与报告图件由多组脚本生成，具体以 exact_hit 中的脚本命中为准；若无精确命中，按paper/figures目录归类。",
            "按 manifest exact_hit 脚本运行；报告替换脚本默认不自动执行。",
            "directory_inferred",
            "paper/figures 为报告/论文图件集中目录，存在多脚本生成历史。",
        )
    if "/notebook_outputs/" in s:
        return set_map(
            "build_implementation_notebook.py; build_image_provenance_notebook.py",
            "Notebook读取的指标表、manifest与代表图样本",
            "Notebook执行过程中生成的说明性图件、contact sheet或旧版演示图。",
            "python build_image_provenance_notebook.py",
            "notebook_output",
            "notebook_outputs 目录为Notebook产物。",
        )
    return out


def scan_scripts() -> tuple[dict[str, str], dict[str, list[tuple[int, str]]]]:
    scripts = walk_files(SCRIPT_ROOTS, {".py"})
    texts: dict[str, str] = {}
    interesting_lines: dict[str, list[tuple[int, str]]] = {}
    quoted_img = re.compile(r"""["']([^"']+\.(?:png|jpg|jpeg|tif|tiff))["']""", re.I)
    for script in scripts:
        # Avoid unrelated tool projects while still scanning project scripts.
        if "auto-claude-code-research" in script.parts:
            continue
        try:
            text = script.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        r = rel(script)
        texts[r] = text
        lines: list[tuple[int, str]] = []
        for i, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            if quoted_img.search(line) or any(k in low for k in GENERATION_KEYWORDS) or "add_picture" in low:
                lines.append((i, line))
        interesting_lines[r] = lines
    return texts, interesting_lines


def classify_script_hit(script: str, line: str) -> str:
    stem = Path(script).stem.lower()
    low = line.lower()
    if "add_picture" in low or any(h in stem for h in INSERTION_SCRIPT_HINTS):
        if any(h in stem for h in ("redraw_ppt",)):
            return "generation_and_insertion"
        return "insertion"
    if any(k in low for k in ("savefig", "imwrite", ".save(", "copy2", "copyfile", "sftp.get")):
        return "generation_or_copy"
    if any(h in stem for h in GENERATOR_SCRIPT_HINTS):
        return "generation_or_copy"
    return "reference"


def find_hits(filename: str, script_lines: dict[str, list[tuple[int, str]]]) -> list[ScriptHit]:
    hits: list[ScriptHit] = []
    fl = filename.lower()
    for script, lines in script_lines.items():
        for line_no, line in lines:
            if fl in line.lower():
                hits.append(ScriptHit(script, line_no, classify_script_hit(script, line), clean_snippet(line)))
    return hits


def merge_code(manual: str, hits: list[ScriptHit], kinds: tuple[str, ...]) -> str:
    items: list[str] = []
    if manual:
        items.extend([x.strip() for x in manual.split(";") if x.strip()])
    for h in hits:
        if h.kind in kinds:
            items.append(h.script)
    out: list[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return "; ".join(out)


def best_confidence(manual_conf: str, hits: list[ScriptHit]) -> str:
    if any(h.kind in {"generation_or_copy", "generation_and_insertion"} for h in hits):
        return "exact_script_hit" if not manual_conf else f"{manual_conf}+exact_hit"
    return manual_conf or "unmatched"


def build_manifest() -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    images = walk_files(RELEVANT_ROOTS, IMAGE_EXTS)
    _, script_lines = scan_scripts()
    rows: list[dict[str, object]] = []
    hit_rows: list[dict[str, object]] = []

    for path in images:
        r = rel(path)
        filename = path.name
        category, role = category_for(r)
        width, height = image_size(path)
        stat = path.stat()
        manual = manual_mapping(r, filename)
        hits = find_hits(filename, script_lines)

        for h in hits:
            hit_rows.append(
                {
                    "image": r,
                    "script": h.script,
                    "line_no": h.line_no,
                    "hit_kind": h.kind,
                    "snippet": h.snippet,
                }
            )

        generation_code = merge_code(
            manual.get("generating_code", ""),
            hits,
            ("generation_or_copy", "generation_and_insertion"),
        )
        insertion_code = merge_code("", hits, ("insertion", "generation_and_insertion"))
        evidence_bits = []
        if manual.get("evidence"):
            evidence_bits.append(str(manual["evidence"]))
        for h in hits[:4]:
            evidence_bits.append(f"{h.script}:{h.line_no} {h.snippet}")

        rows.append(
            {
                "relative_path": r,
                "file_name": filename,
                "category": category,
                "image_role": role,
                "extension": path.suffix.lower(),
                "width_px": width,
                "height_px": height,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified_time": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "generating_code": generation_code,
                "insertion_or_usage_code": insertion_code,
                "source_data": manual.get("source_data", ""),
                "production_method": manual.get("production_method", ""),
                "rerun_command": manual.get("rerun_command", ""),
                "confidence": best_confidence(str(manual.get("confidence", "")), hits),
                "evidence": " | ".join(evidence_bits),
            }
        )

    counts = Counter(row["category"] for row in rows)
    confidence_counts = Counter(row["confidence"] for row in rows)
    summary_rows: list[dict[str, object]] = []
    by_cat: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_cat[str(row["category"])].append(row)
    for category, items in sorted(by_cat.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        conf = Counter(str(x["confidence"]) for x in items)
        scripts = Counter()
        for item in items:
            for code in str(item["generating_code"]).split(";"):
                code = code.strip()
                if code:
                    scripts[code] += 1
        summary_rows.append(
            {
                "category": category,
                "image_count": len(items),
                "top_confidence": "; ".join(f"{k}:{v}" for k, v in conf.most_common(4)),
                "primary_generating_code": "; ".join(f"{k} ({v})" for k, v in scripts.most_common(4)),
                "example_image": str(items[0]["relative_path"]),
            }
        )

    return rows, summary_rows, hit_rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, object]], summary_rows: list[dict[str, object]]) -> None:
    lines: list[str] = []
    lines.append("# 全项目图像与图表生成溯源清单")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 图片总数：{len(rows)}")
    lines.append(f"- CSV逐图清单：`{rel(MANIFEST_CSV)}`")
    lines.append("")
    lines.append("## 类别汇总")
    lines.append("")
    lines.append("| 类别 | 图片数 | 主要脚本 | 示例 |")
    lines.append("|---|---:|---|---|")
    for row in summary_rows:
        lines.append(
            f"| {row['category']} | {row['image_count']} | {row['primary_generating_code']} | `{row['example_image']}` |"
        )
    lines.append("")
    lines.append("## 逐图清单")
    lines.append("")
    lines.append("| 图片 | 类别 | 生成代码 | 输入数据/来源 | 置信度 |")
    lines.append("|---|---|---|---|---|")
    for row in rows:
        src = str(row["source_data"]).replace("|", "/")
        lines.append(
            f"| `{row['relative_path']}` | {row['category']} | {row['generating_code']} | {src} | {row['confidence']} |"
        )
    MANIFEST_MD.write_text("\n".join(lines), encoding="utf-8")


def make_contact_sheet(rows: list[dict[str, object]]) -> None:
    if Image is None or ImageOps is None or ImageDraw is None:
        return
    by_cat: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_cat[str(row["category"])].append(row)

    selected: list[dict[str, object]] = []
    priority = [
        "PPT分层GIS图",
        "PPT重绘工作区图件",
        "论文与报告图件",
        "会议论文图件",
        "SCI街道断面图",
        "普通街道断面图",
        "街景YOLO中文标注图",
        "精选中文街景标注图",
        "VLM增强街景标注图",
        "街景仿真检测样本",
        "街景热力图/分割热图",
        "Overleaf论文图件",
    ]
    for cat in priority:
        selected.extend(by_cat.get(cat, [])[:2])
    selected = selected[:24]
    if not selected:
        return

    thumb_w, thumb_h = 260, 180
    cols = 4
    rows_n = (len(selected) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows_n * (thumb_h + 42)), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 13)
        small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 10)
    except Exception:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
    for idx, row in enumerate(selected):
        p = ROOT / str(row["relative_path"])
        x = (idx % cols) * thumb_w
        y = (idx // cols) * (thumb_h + 42)
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                im.thumbnail((thumb_w - 14, thumb_h - 14), Image.LANCZOS)
                canvas = Image.new("RGB", (thumb_w, thumb_h), "#f4f6f8")
                ox = (thumb_w - im.width) // 2
                oy = (thumb_h - im.height) // 2
                canvas.paste(im, (ox, oy))
        except Exception:
            canvas = Image.new("RGB", (thumb_w, thumb_h), "#eeeeee")
        sheet.paste(canvas, (x, y))
        draw.rectangle([x, y, x + thumb_w - 1, y + thumb_h - 1], outline="#cccccc")
        label = str(row["category"])[:20]
        path_short = str(row["file_name"])[:32]
        draw.text((x + 6, y + thumb_h + 4), label, fill="#111111", font=font)
        draw.text((x + 6, y + thumb_h + 23), path_short, fill="#555555", font=small)
    sheet.save(CONTACT_SHEET, quality=92)


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip() + "\n")


def code(text: str, tags: list[str] | None = None):
    cell = nbf.v4.new_code_cell(text.strip() + "\n")
    if tags:
        cell.metadata["tags"] = tags
    return cell


def build_notebook() -> None:
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
<div style="background:linear-gradient(120deg,#143642,#0f766e 58%,#2f6f73);padding:24px 28px;border-radius:10px;color:white">
  <h1 style="margin:0;font-size:30px">全项目图像与图表生成溯源 Notebook</h1>
  <p style="margin:10px 0 0;font-size:15px;line-height:1.55">
  面向报告、PPT、论文、街景、断面图和深度学习结果，逐张追踪 image → 生成代码 → 输入数据 → 重跑命令。
  </p>
</div>

## 说明

本 Notebook 不再只解释 PPT 中少数图表，而是以 `image_provenance_manifest.csv` 为主线，对项目内所有主要图片资产做溯源。  
其中：

- `exact_known / exact_script_hit`：脚本中有固定输出名或静态扫描命中；
- `directory_match`：批量目录由固定生成脚本维护，例如街道断面图、街景标注图；
- `raw_acquired`：不是绘图脚本生成，而是街景采集/下载得到的原始影像；
- `directory_inferred`：历史脚本较多，按目录、命名和脚本命中综合判断。

远程GPU、SSH、API相关脚本只作为来源路径记录；Notebook 默认不执行这些命令，也不会修改 PPT/DOCX。
            """
        )
    )
    cells.append(
        code(
            """
from pathlib import Path
import pandas as pd
from IPython.display import display, Markdown, Image

ROOT = Path.cwd()
while not (ROOT / "projects" / "15min-urban-accessibility").exists() and ROOT.parent != ROOT:
    ROOT = ROOT.parent
PROJECT = ROOT / "projects" / "15min-urban-accessibility"
OUT = PROJECT / "notebook_outputs"
MANIFEST = OUT / "image_provenance_manifest.csv"
SUMMARY = OUT / "image_provenance_group_summary.csv"
HITS = OUT / "image_provenance_script_hits.csv"
CONTACT = OUT / "image_provenance_contact_sheet.png"

manifest = pd.read_csv(MANIFEST, encoding="utf-8-sig")
summary = pd.read_csv(SUMMARY, encoding="utf-8-sig")
hits = pd.read_csv(HITS, encoding="utf-8-sig") if HITS.exists() else pd.DataFrame()

print("工作区:", ROOT)
print("图片总数:", len(manifest))
print("类别数:", manifest["category"].nunique())
display(summary)
            """
        )
    )
    cells.append(md("## 1. 全项目图片资产分布"))
    cells.append(
        code(
            """
display(
    manifest.groupby(["category", "confidence"])
    .size()
    .rename("image_count")
    .reset_index()
    .sort_values(["category", "image_count"], ascending=[True, False])
)

display(
    manifest.assign(dir=manifest["relative_path"].str.rsplit("/", n=1).str[0])
    .groupby("dir")
    .size()
    .rename("image_count")
    .reset_index()
    .sort_values("image_count", ascending=False)
    .head(30)
)
            """
        )
    )
    cells.append(md("## 2. 代表性图像总览"))
    cells.append(
        code(
            """
if CONTACT.exists():
    display(Image(filename=str(CONTACT), width=980))
else:
    display(Markdown("未生成 contact sheet。"))
            """
        )
    )
    cells.append(
        md(
            """
## 3. 各类图像如何产生

下面不是重新造图，而是读取已经生成的溯源 manifest。每一类都对应真实脚本、真实输入数据和重跑命令。
            """
        )
    )
    cells.append(
        code(
            """
cols = ["category", "image_count", "primary_generating_code", "top_confidence", "example_image"]
display(summary[cols])

for _, row in summary.iterrows():
    cat = row["category"]
    sub = manifest[manifest["category"] == cat].head(6)
    display(Markdown(f"### {cat}"))
    display(sub[[
        "relative_path", "image_role", "generating_code",
        "source_data", "production_method", "rerun_command", "confidence"
    ]])
            """
        )
    )
    cells.append(md("## 4. 逐图查询：输入任意图片路径或类别"))
    cells.append(
        code(
            """
def query_image(keyword: str, limit: int = 20):
    mask = manifest.apply(lambda col: col.astype(str).str.contains(keyword, case=False, regex=False)).any(axis=1)
    cols = [
        "relative_path", "category", "image_role", "generating_code",
        "source_data", "production_method", "rerun_command", "confidence", "evidence"
    ]
    return manifest.loc[mask, cols].head(limit)

# 示例1：查询PPT两张重绘图
display(query_image("_ppt_chart_work"))

# 示例2：查询街景中文标注图
display(query_image("annotated_cn", 10))

# 示例3：查询街道断面图
display(query_image("street_profiles_hq", 10))
            """
        )
    )
    cells.append(md("## 5. 脚本精确命中证据"))
    cells.append(
        code(
            """
if len(hits):
    display(hits.head(80))
    display(
        hits.groupby(["script", "hit_kind"])
        .size()
        .rename("hit_count")
        .reset_index()
        .sort_values("hit_count", ascending=False)
        .head(40)
    )
else:
    display(Markdown("没有脚本命中记录。"))
            """
        )
    )
    cells.append(
        md(
            """
## 6. 关键生成链路

### 6.1 GIS路线图 / 分层总图

`redraw_total_gis_map.py` 负责综合总图；`redraw_total_gis_map_layers.py` 读取同一批边界、路网、建筑、POI、社区、route和trajectory数据，输出第15-20页使用的分层图。  
`revise_layered_map_ppt_style.py` 只负责把这些图和诊断文字插入PPT。

### 6.2 指标空间对比与报告图

报告中的指标分布、SAII、昼夜可达性、POI分布等图主要来自 `paper/generate_figures.py`、`redraw_report_figures.py`、`v2_real_data/scripts/p2_accessibility/*.py`。  
具体哪张图命中了哪个脚本，以 manifest 的 `generating_code` 和 `evidence` 为准。

### 6.3 街道断面图

`generate_street_profiles.py` 和 `generate_street_profiles_sci.py` 从楼栋基础数据读取中心坐标、层数、使用用途，按道路名/空间窗口分组，绘制建筑高度和用途颜色。  
`profile_summary.csv` 是这些断面图的统计索引。

### 6.4 街景原图、标注图、热力图

原始街景属于采集/下载影像，不是统计图生成；标注图来自 YOLO/语义分割/VLM 后处理；热力图来自FCN/YOLO遮挡或语义分割结果。  
Notebook 不执行远程推理，只记录对应脚本和数据。
            """
        )
    )
    cells.append(md("## 7. 安全重跑命令清单"))
    cells.append(
        code(
            """
rerun_table = (
    manifest[["category", "generating_code", "source_data", "rerun_command", "confidence"]]
    .drop_duplicates()
    .sort_values(["category", "generating_code"])
)
display(rerun_table)

display(Markdown(
    "**注意：** `redraw_ppt_*`、`revise_layered_map_ppt_style.py`、`redraw_report_figures.py` 会修改PPT或DOCX；"
    "远程GPU/API脚本可能含服务器或API依赖。需要重跑时应先备份并确认环境。"
))
            """
        )
    )
    cells.append(md("## 8. 导出文件"))
    cells.append(
        code(
            """
exports = pd.DataFrame([
    {"文件": str(MANIFEST.relative_to(ROOT)), "用途": "逐图完整溯源CSV，Excel可打开"},
    {"文件": str((OUT / "image_provenance_manifest.json").relative_to(ROOT)), "用途": "逐图结构化JSON"},
    {"文件": str((OUT / "image_provenance_manifest.md").relative_to(ROOT)), "用途": "Markdown版逐图清单"},
    {"文件": str(SUMMARY.relative_to(ROOT)), "用途": "按类别汇总"},
    {"文件": str(HITS.relative_to(ROOT)), "用途": "脚本命中证据"},
    {"文件": str(CONTACT.relative_to(ROOT)), "用途": "代表性图像预览拼图"},
])
display(exports)
            """
        )
    )
    nb["cells"] = cells
    nbf.write(nb, NB_PATH)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rows, summary_rows, hit_rows = build_manifest()
    write_csv(MANIFEST_CSV, rows)
    write_csv(SUMMARY_CSV, summary_rows)
    write_csv(SCRIPT_HITS_CSV, hit_rows)
    MANIFEST_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(rows, summary_rows)
    make_contact_sheet(rows)
    build_notebook()
    print(f"images={len(rows)}")
    print(f"manifest={MANIFEST_CSV}")
    print(f"summary={SUMMARY_CSV}")
    print(f"hits={SCRIPT_HITS_CSV}")
    print(f"markdown={MANIFEST_MD}")
    print(f"notebook={NB_PATH}")
    if CONTACT_SHEET.exists():
        print(f"contact_sheet={CONTACT_SHEET}")


if __name__ == "__main__":
    main()
