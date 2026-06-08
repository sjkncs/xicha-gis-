#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SegFormer B3 模型下载脚本 - 直接用 Python 运行"""
import warnings
warnings.filterwarnings("ignore")
import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
import time

MODEL_DIR = "/root/gis_project/models"
LOG_FILE = "/root/gis_project/logs/model_download.log"

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

log("开始下载 SegFormer B3...")
t0 = time.time()

try:
    log("下载 ImageProcessor...")
    processor = AutoImageProcessor.from_pretrained(
        "nvidia/mit-b3",
        cache_dir=MODEL_DIR,
        local_files_only=False
    )
    log("ImageProcessor 下载完成")

    log("下载 Model...")
    model = AutoModelForSemanticSegmentation.from_pretrained(
        "nvidia/mit-b3",
        cache_dir=MODEL_DIR,
        local_files_only=False
    )
    log("Model 下载完成!")

    elapsed = time.time() - t0
    log(f"全部完成! 耗时: {elapsed:.1f}秒")

    # 验证
    import torch
    log(f"torch: {torch.__version__}")
    log(f"CUDA: {torch.cuda.is_available()}")

    # 标记完成
    with open("/root/gis_project/gpu_scripts/MODELS_READY", "w") as f:
        f.write(f"Downloaded at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

except Exception as e:
    log(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    with open(LOG_FILE, "a") as f:
        traceback.print_exc(file=f)
