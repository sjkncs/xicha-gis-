#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地下载 SegFormer B3 模型 (Windows) + 上传到GPU服务器"""
import os, sys, warnings
warnings.filterwarnings("ignore")

# 设置镜像站点
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

from huggingface_hub import snapshot_download
from pathlib import Path

LOCAL_MODEL_DIR = Path(r"E:\xicha gis 智能定位\自选年份\gpu_scripts\segformer_b3_ade")
MODEL_NAME = "nvidia/segformer-b3-finetuned-ade-512-512"

print(f"下载模型: {MODEL_NAME}")
print(f"本地目录: {LOCAL_MODEL_DIR}")
print(f"镜像: {os.environ['HF_ENDPOINT']}")

try:
    path = snapshot_download(
        repo_id=MODEL_NAME,
        local_dir=LOCAL_MODEL_DIR,
        local_dir_use_symlinks=False,
        allow_patterns=["*.json", "*.bin", "*.safetensors", "*.txt", "*.md", "*.py"],
    )
    print(f"下载完成: {path}")

    # 列出文件
    files = list(LOCAL_MODEL_DIR.rglob("*"))
    total_size = sum(f.stat().st_size for f in files if f.is_file())
    print(f"文件数: {len(files)}")
    print(f"总大小: {total_size/1024**2:.1f} MB")
    for f in sorted(LOCAL_MODEL_DIR.glob("*")):
        if f.is_file():
            print(f"  {f.name}: {f.stat().st_size/1024**2:.1f} MB")

except Exception as e:
    print(f"下载失败: {e}")
    import traceback; traceback.print_exc()
