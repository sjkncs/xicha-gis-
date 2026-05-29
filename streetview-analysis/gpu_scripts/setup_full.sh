#!/bin/bash
# ====================================================================
# GPU 服务器完整环境配置脚本
# 修正版: 使用 /root/miniconda3 路径
# 数据存储: /autodl-pub/data
# 执行: bash setup_full.sh 2>&1 | tee setup_full.log
# ====================================================================
set -e

export MINICONDA="/root/miniconda3"
export PATH="$MINICONDA/bin:$PATH"

echo "==== GPU 服务器环境安装 (修正版) ===="
echo "时间: $(date)"

# 0. 检查 CUDA 驱动版本
echo ""
echo "=== GPU 驱动版本 ==="
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader

# 1. 配置 pip 镜像
echo ""
echo "=== [1/10] 配置 pip 镜像 ==="
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip config set global.trusted-host https://pypi.tuna.tsinghua.edu.cn
pip config set global.timeout 120
echo "镜像配置完成"

# 2. 升级 pip
echo ""
echo "=== [2/10] 升级 pip ==="
pip install --upgrade pip 2>&1 | tail -2

# 3. 安装 PyTorch 2.5 (CUDA 12.4) - 覆盖旧版
echo ""
echo "=== [3/10] 安装 PyTorch 2.5 + CUDA 12.4 ==="
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -5

# 4. 验证 PyTorch
echo ""
echo "=== [4/10] 验证 PyTorch + GPU ==="
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA Available: {torch.cuda.is_available()}')
print(f'CUDA Version: {torch.version.cuda}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB')
    x = torch.randn(1000, 1000).cuda()
    print(f'GPU 测试: {x.sum().item():.2f} OK!')
"

# 5. 安装核心依赖
echo ""
echo "=== [5/10] 安装核心 Python 库 ==="
pip install \
    numpy==1.26.4 \
    opencv-python==4.10.0.84 \
    opencv-python-headless==4.10.0.84 \
    pillow==10.4.0 \
    scipy==1.13.1 \
    matplotlib==3.9.0 \
    seaborn==0.13.2 \
    pandas==2.2.2 \
    scikit-learn==1.5.1 \
    scikit-image==0.24.0 \
    albumentations==1.4.15 \
    2>&1 | tail -5

# 6. 安装深度学习库
echo ""
echo "=== [6/10] 安装 transformers + timm + 生态 ==="
pip install \
    transformers==4.46.0 \
    timm==0.9.16 \
    accelerate==1.2.1 \
    huggingface_hub==0.27.0 \
    sentencepiece==0.2.0 \
    protobuf==5.27.5 \
    2>&1 | tail -5

# 7. 安装 3DGS 工具
echo ""
echo "=== [7/10] 安装图像/3D 处理库 ==="
pip install \
    plyfile==1.0.3 \
    trimesh==4.2.0 \
    open3d==0.19.0 \
    rasterio==1.3.11 \
    fiona==1.10.0 \
    shapely==2.0.5 \
    pyproj==3.7.0 \
    geopandas==0.14.4 \
    2>&1 | tail -5

# 8. 安装 CUDA 扩展兼容库
echo ""
echo "=== [8/10] 安装 CUDA 工具 ==="
pip install \
    nvidia-cublas-cu12==12.1.3.1 \
    nvidia-cudnn-cu12==9.1.0.70 \
    nvidia-cuda-nvrtc-cu12==12.1.105 \
    nvidia-cuda-runtime-cu12==12.1.105 \
    nvidia-cuda-cupti-cu12==12.1.105 \
    2>&1 | tail -5

# 9. 全部验证
echo ""
echo "=== [9/10] 完整验证 ==="
python -c "
import torch, cv2, numpy, PIL, scipy, transformers, timm
print(f'  torch:     {torch.__version__}  CUDA:{torch.cuda.is_available()}')
print(f'  opencv:    {cv2.__version__}')
print(f'  numpy:     {numpy.__version__}')
print(f'  PIL:       {PIL.__version__}')
print(f'  scipy:     {scipy.__version__}')
print(f'  transformers: {transformers.__version__}')
print(f'  timm:      {timm.__version__}')
if torch.cuda.is_available():
    print(f'  GPU:       {torch.cuda.get_device_name(0)}')
"

# 10. 磁盘使用
echo ""
echo "=== [10/10] 磁盘状态 ==="
df -h / /autodl-pub/data 2>&1 | head -5

echo ""
echo "==== 全部完成! $(date) ===="
echo "激活环境: source /root/miniconda3/bin/activate base"
