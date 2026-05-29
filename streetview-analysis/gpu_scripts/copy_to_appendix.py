#!/usr/bin/env python3
"""复制全量文件到论文附录文件夹"""
import os, shutil, glob

LOCAL_RAW = r"e:\xicha gis 智能定位\自选年份\raw_streetview"
LOCAL_ANN = r"e:\xicha gis 智能定位\自选年份\annotated_streetview"

APPENDIX_RAW = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\appendix_raw"
APPENDIX_ANN = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\appendix_annotated"
PAPER_FIG = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\figures"

for d in [APPENDIX_RAW, APPENDIX_ANN]:
    os.makedirs(d, exist_ok=True)

# 复制全量原图（保持目录结构）
print("复制全量原图...")
raw_files = glob.glob(os.path.join(LOCAL_RAW, "**", "*.jpg"), recursive=True)
print(f"  {len(raw_files)} 张原图")
for i, src in enumerate(sorted(raw_files)):
    rel = os.path.relpath(src, LOCAL_RAW)
    dst = os.path.join(APPENDIX_RAW, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
print(f"  完成!")

# 复制全量标注图
print("复制全量标注图...")
ann_files = glob.glob(os.path.join(LOCAL_ANN, "*.jpg"))
print(f"  {len(ann_files)} 张标注图")
for src in sorted(ann_files):
    shutil.copy2(src, os.path.join(APPENDIX_ANN, os.path.basename(src)))
print(f"  完成!")

# 验证
print(f"\n=== 验证 ===")
raw_count = len(glob.glob(os.path.join(APPENDIX_RAW, "**", "*.jpg"), recursive=True))
ann_count = len(glob.glob(os.path.join(APPENDIX_ANN, "*.jpg")))
fig_count = len(glob.glob(os.path.join(PAPER_FIG, "*.jpg")))
print(f"附录原图: {raw_count} 张")
print(f"附录标注: {ann_count} 张")
print(f"论文图: {fig_count} 张")
