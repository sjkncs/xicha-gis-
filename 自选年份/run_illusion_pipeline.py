# -*- coding: utf-8 -*-
"""
run_illusion_pipeline.py — 物理-数字验证 Pipeline 统一入口
Physical-Digital Verification Pipeline

整合四个核心模块:
  1. illusion_scorer      — 可达性幻觉评分（全局视角）
  2. street_view_verifier — 路径级街景验证（路径视角）
  3. world_model_validator — Tesla灵感的世界模型对照（栅格/嵌入/规划视角）
  4. 输出验证报告 + 热力图数据（供 Cesium 可视化）

用法:
  python run_illusion_pipeline.py
  python run_illusion_pipeline.py --skip-scoring --skip-verification
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# 项目根目录（相对于本脚本）
BASE_DIR = Path(__file__).parent


def run_cmd(cmd, desc):
    print(f"\n{'='*60}")
    print(f"  {desc}")
    print(f"  CMD: {' '.join(cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=False)
    if result.returncode != 0:
        print(f"[ERROR] {desc} 失败 (exit {result.returncode})")
        return False
    print(f"[OK] {desc} 完成")
    return True


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="幻觉验证 Pipeline")
    parser.add_argument("--skip-scoring", action="store_true",
                        help="跳过幻觉评分")
    parser.add_argument("--skip-verification", action="store_true",
                        help="跳过路径验证")
    parser.add_argument("--skip-world-model", action="store_true",
                        help="跳过世界模型验证")
    parser.add_argument("--sv-csv", default="baidu_streetview/segmentation_results_v3/seg_final_clean.csv")
    parser.add_argument("--sv-manifest", default="baidu_streetview/ns_manifest.csv")
    parser.add_argument("--network-stats", default="network_output/walkable_stats.json")
    parser.add_argument("--facility", default="network_output/facility_locations.json")
    args = parser.parse_args()

    print(f"\n{'#'*60}")
    print(f"  数字-物理验证 Pipeline")
    print(f"  街景CSV: {args.sv_csv}")
    print(f"  街景清单: {args.sv_manifest}")
    print(f"  网络统计: {args.network_stats}")
    print(f"{'#'*60}")

    success = True

    # Step 1: 幻觉评分
    if not args.skip_scoring:
        success &= run_cmd(
            [sys.executable, "illusion_scorer.py",
             "--sv-csv", args.sv_csv,
             "--network-stats", args.network_stats,
             "--output", "illusion_output"],
            "Step 1/3: 可达性幻觉评分"
        )
    else:
        print("[SKIP] Step 1 幻觉评分已跳过")

    # Step 2: 路径街景验证
    if not args.skip_verification:
        success &= run_cmd(
            [sys.executable, "street_view_verifier.py",
             "--sv-manifest", args.sv_manifest,
             "--sv-csv", args.sv_csv,
             "--facility", args.facility,
             "--output", "verifier_output",
             "--interval", "50",
             "--max-dist", "100"],
            "Step 2/3: 街景路径验证"
        )
    else:
        print("[SKIP] Step 2 路径验证已跳过")

    # Step 3: 世界模型验证（Tesla BEV + 3D Occupancy Network）
    if not args.skip_world_model:
        success &= run_cmd(
            [sys.executable, "world_model_validator.py",
             "--sv-csv", args.sv_csv,
             "--network-stats", args.network_stats,
             "--output", "world_model_output"],
            "Step 3/4: Tesla BEV + 3D Occupancy 世界模型验证"
        )
    else:
        print("[SKIP] Step 3 世界模型验证已跳过")

    # Step 4: 汇总报告
    if success:
        print(f"\n{'='*60}")
        print("  汇总报告")
        print(f"{'='*60}")
        try:
            ill = load_json(BASE_DIR / "illusion_output" / "illusion_summary.json")
            ver = load_json(BASE_DIR / "verifier_output" / "verification_summary.json")
            try:
                wm = load_json(BASE_DIR / "world_model_output" / "world_model_summary.json")
            except Exception:
                wm = None
            print(f"\n幻觉评分结果:")
            print(f"  综合幻觉分: {ill.get('composite_illusion_score', 'N/A')}")
            dims = ill.get("dimensions", {})
            for key, label in [
                ("I_geometric", "I几何"),
                ("II_semantic", "II语义"),
                ("III_access", "III接入"),
                ("IV_experience", "IV体验"),
                ("V_equity", "V公平"),
            ]:
                d = dims.get(key, {})
                print(f"  {label}: {d.get('score', 'N/A')}")
            print(f"\n路径验证结果:")
            stats = ver.get("statistics", {})
            print(f"  验证路径: {stats.get('total_paths', 'N/A')}")
            print(f"  平均Gap: {stats.get('avg_gap_score', 'N/A')}")
            print(f"  低幻觉: {stats.get('paths_by_level', {}).get('low_illusion', 0)} 条")
            print(f"  中幻觉: {stats.get('paths_by_level', {}).get('medium_illusion', 0)} 条")
            print(f"  高幻觉: {stats.get('paths_by_level', {}).get('high_illusion', 0)} 条")
            print(f"  极高幻觉: {stats.get('paths_by_level', {}).get('extreme_illusion', 0)} 条")
            if wm:
                print(f"\nTesla 世界模型验证结果 (BEV + 3D Occupancy Network):")
                print(f"  幻觉假设评分: {wm.get('illusion_hypothesis_score', 'N/A')}")
                print(f"  嵌入余弦相似度: {wm.get('embedding_comparison', {}).get('global_cosine_sim', 'N/A')}")
                print(f"  嵌入欧氏偏差: {wm.get('embedding_comparison', {}).get('global_euclidean_dev', 'N/A')}")
                print(f"  物理占用均值: {wm.get('physical_occupancy', {}).get('mean_p_occ', 'N/A')}")
                print(f"  数字占用均值: {wm.get('digital_occupancy', {}).get('mean_p_occ', 'N/A')}")
                print(f"  规划偏距均值: {wm.get('planning_gap', {}).get('mean_gap_score', 'N/A')}")
                print(f"  占用差异: {wm.get('occupancy_gap', {}).get('physical_vs_digital', 'N/A')}")
                bev = wm.get('bev_3d', {})
                if bev:
                    print(f"  3D Voxel 网格: {bev.get('n_cells', 'N/A')} 格")
                    print(f"  BEV 层数: 4 (ground/pedestrian/vehicle/canopy)")
                roads = wm.get('road_geometry', {})
                if roads:
                    print(f"  数字路网: {roads.get('n_segments', 'N/A')} 路段")
            print(f"\n输出文件:")
            print(f"  illusion_output/illusion_summary.json")
            print(f"  illusion_output/per_neighborhood_illusions.json")
            print(f"  illusion_output/sv_with_illusions.csv")
            print(f"  verifier_output/verification_summary.json")
            print(f"  verifier_output/evidence_chains.json")
            print(f"  verifier_output/verified_paths.geojson")
            if wm:
                print(f"  world_model_output/world_model_summary.json")
                print(f"  world_model_output/physical_occupancy.json")
                print(f"  world_model_output/digital_occupancy.json")
                print(f"  world_model_output/embedding_comparison.json")
                print(f"  world_model_output/planning_gap.json")
                print(f"  world_model_output/bev_voxel_3d.json")
                print(f"  world_model_output/road_geometry.json")
            print(f"\n对照面板:")
            print(f"  city_twin_output/illusion_verification_panel.html")
            print(f"  world_model_output/world_model_panel.html")
            print(f"  world_model_output/tesla_world_3d.html  ← Tesla 3D Voxel Viewer!")
            print(f"\n  启动对照面板: python -m http.server 8899")
            print(f"  启动 3D 世界模型: python -m http.server 8898")
            print(f"  (在对应 output 目录内运行)")
        except Exception as e:
            print(f"[WARN] 汇总报告生成失败: {e}")

    print(f"\n{'#'*60}")
    if success:
        print("  Pipeline 全部完成!")
    else:
        print("  Pipeline 部分失败，请检查日志")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()
