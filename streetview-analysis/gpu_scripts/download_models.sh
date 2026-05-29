#!/bin/bash
# ====================================================================
# 模型下载脚本 - 在 GPU 服务器上运行
# 用法: bash download_models.sh
# ====================================================================
set -e
VENV="/root/venv"
PY="$VENV/bin/python"
DATA_DIR="/autodl-pub/data"
MODEL_DIR="$DATA_DIR/models"
mkdir -p "$MODEL_DIR"

echo "===== 模型下载 ====="
echo "VRAM: $(nvidia-smi --query-gpu=memory.total --format=csv,noheader)"

# HuggingFace 镜像配置
export HF_ENDPOINT="https://hf-mirror.com"
export HF_HUB_ENABLE_HF_TRANSFER=1

# 1. SegFormer B3 (分割模型)
echo ""
echo "[1/4] 下载 SegFormer B3..."
$PY -c "
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
processor = AutoImageProcessor.from_pretrained('nvidia/mit-b3', cache_dir='$MODEL_DIR')
model = AutoModelForSemanticSegmentation.from_pretrained('nvidia/mit-b3', cache_dir='$MODEL_DIR')
print('SegFormer B3 OK')
"

# 2. SegFormer B2 (轻量版)
echo ""
echo "[2/4] 下载 SegFormer B2..."
$PY -c "
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
processor = AutoImageProcessor.from_pretrained('nvidia/mit-b2', cache_dir='$MODEL_DIR')
model = AutoModelForSemanticSegmentation.from_pretrained('nvidia/mit-b2', cache_dir='$MODEL_DIR')
print('SegFormer B2 OK')
"

# 3. DepthPro (深度估计)
echo ""
echo "[3/4] 下载 DepthPro..."
$PY -c "
from transformers import AutoImageProcessor, AutoModelForDepthEstimation
# DepthPro 有不同版本，先尝试最新版
try:
    processor = AutoImageProcessor.from_pretrained('apple/DepthPro-V1', cache_dir='$MODEL_DIR')
    model = AutoModelForDepthEstimation.from_pretrained('apple/DepthPro-V1', cache_dir='$MODEL_DIR')
    print('DepthPro-V1 OK')
except Exception as e:
    print(f'DepthPro-V1 failed: {e}')
    try:
        processor = AutoImageProcessor.from_pretrained('apple/DepthPro', cache_dir='$MODEL_DIR')
        model = AutoModelForDepthEstimation.from_pretrained('apple/DepthPro', cache_dir='$MODEL_DIR')
        print('DepthPro OK')
    except Exception as e2:
        print(f'DepthPro failed: {e2}')
"

# 4. DPT (另一个深度估计模型)
echo ""
echo "[4/4] 下载 DPT-Large..."
$PY -c "
from transformers import AutoImageProcessor, AutoModelForDepthEstimation
try:
    processor = AutoImageProcessor.from_pretrained('Intel/dpt-large', cache_dir='$MODEL_DIR')
    model = AutoModelForDepthEstimation.from_pretrained('Intel/dpt-large', cache_dir='$MODEL_DIR')
    print('DPT-Large OK')
except Exception as e:
    print(f'DPT-Large failed: {e}')
"

# 检查下载结果
echo ""
echo "===== 模型检查 ====="
du -sh "$MODEL_DIR" 2>/dev/null
find "$MODEL_DIR" -name "config.json" -path "*/nvidia*" 2>/dev/null | head -5
find "$MODEL_DIR" -name "config.json" -path "*/apple*" 2>/dev/null | head -5
find "$MODEL_DIR" -name "config.json" -path "*/Intel*" 2>/dev/null | head -5
find "$MODEL_DIR" -name "pytorch_model.bin" -o -name "model.safetensors" 2>/dev/null | head -10

echo ""
echo "===== 下载完成 ====="
