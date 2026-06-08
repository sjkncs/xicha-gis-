#!/bin/bash
# ====================================================================
# GPU 云服务器基础环境安装脚本
# 目标: RTX PRO 6000 Blackwell 98GB + Ubuntu 22.04
# 执行: bash setup_step1.sh 2>&1 | tee setup_step1.log
# ====================================================================
set -e
echo "==== Step 1: 系统基础依赖 ===="

# 换国内镜像 (腾讯云)
echo "[1/8] 配置清华 pip 镜像..."
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip config set global.trusted-host https://pypi.tuna.tsinghua.edu.cn

# 系统依赖
echo "[2/8] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq \
    git curl wget unzip zip libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgomp1 libgthread-2.0-0 libgthread2.0-0 libgcc-s1 \
    build-essential cmake pkg-config libboost-all-dev libcgal-dev \
    freeimage libfreeimage-dev libeigen3-dev libflann-dev \
    sqlite3 libsqlite3-dev libpng-dev libjpeg-dev \
    2>&1 | grep -v "^$" | tail -5

# 磁盘检查
echo "[3/8] 磁盘空间检查..."
df -h / | tail -1

# 安装 Miniconda (如果 conda 不存在)
if ! command -v conda &> /dev/null; then
    echo "[4/8] 安装 Miniconda..."
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p /opt/conda
    rm /tmp/miniconda.sh
    export PATH="/opt/conda/bin:$PATH"
    conda init bash
    source ~/.bashrc
else
    echo "[4/8] Conda 已存在: $(which conda)"
fi

export PATH="/opt/conda/bin:$PATH"

# 创建专用 conda 环境
ENV_NAME="gis_ai"
if conda env list | grep -q "^$ENV_NAME "; then
    echo "[5/8] 环境 $ENV_NAME 已存在，跳过创建"
else
    echo "[5/8] 创建 conda 环境: $ENV_NAME"
    conda create -y -n "$ENV_NAME" python=3.10
fi

conda activate "$ENV_NAME"

# 安装 PyTorch 2.5 + CUDA 12.4 (RTX 6000 Blackwell 需要 CUDA 12+)
echo "[6/8] 安装 PyTorch 2.5 + CUDA 12.4..."
pip install --upgrade pip setuptools wheel
pip install \
    torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu124 \
    2>&1 | tail -3

# 验证 PyTorch CUDA
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'CUDA版本: {torch.version.cuda}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')"

# 核心依赖
echo "[7/8] 安装核心 Python 依赖..."
pip install \
    numpy==1.26.4 pandas pillow scipy matplotlib seaborn \
    opencv-python opencv-python-headless \
    scikit-learn scikit-image \
    albumentations \
    2>&1 | tail -3

# transformers + timm (分割模型)
echo "[8/8] 安装 transformers + timm..."
pip install \
    transformers==4.46.0 \
    timm==0.9.16 \
    accelerate \
    huggingface_hub \
    sentencepiece \
    2>&1 | tail -3

echo ""
echo "==== Step 1 完成! 验证安装: ===="
python -c "
import torch; print(f'  torch: {torch.__version__} CUDA:{torch.cuda.is_available()}')
import cv2; print(f'  opencv: {cv2.__version__}')
import timm; print(f'  timm: {timm.__version__}')
import transformers; print(f'  transformers: {transformers.__version__}')
"
echo "==== 请运行: conda activate gis_ai ===="
