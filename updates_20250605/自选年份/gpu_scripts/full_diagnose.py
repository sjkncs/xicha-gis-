# -*- coding: utf-8 -*-
"""GPU 服务器完整诊断 - 检查所有依赖"""
import paramiko

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=20):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

def check_pkg(c, pkg, test_code):
    out, _ = run(c, f"/root/miniconda3/bin/python -c \"{test_code}\" 2>&1")
    status = "OK" if out.strip() and "error" not in out.lower() and "no module" not in out.lower() else "MISSING"
    print(f"  [{status}] {pkg}: {out.strip()[:100]}")
    return status == "OK"

def main():
    c = ssh()
    print("=" * 55)
    print("GPU 服务器完整环境诊断")
    print("=" * 55)

    # GPU
    print("\n[GPU]")
    out, _ = run(c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,driver_version --format=csv,noheader 2>&1")
    print(f"  {out.strip()}")
    out, _ = run(c, "nvcc --version 2>&1 | grep release || echo 'nvcc not found'")
    print(f"  nvcc: {out.strip()}")

    # PyTorch
    print("\n[PyTorch & CUDA]")
    check_pkg(c, "torch", "import torch; print(f'torch {torch.__version__} CUDA:{torch.cuda.is_available()}')")
    check_pkg(c, "torch GPU", "import torch; t=torch.randn(100,100).cuda(); print('GPU OK:', t.sum().item())")

    # 核心库
    print("\n[核心库]")
    check_pkg(c, "numpy", "import numpy; print(numpy.__version__)")
    check_pkg(c, "opencv", "import cv2; print('cv2', cv2.__version__)")
    check_pkg(c, "pillow", "from PIL import Image; print('PIL OK')")
    check_pkg(c, "scipy", "import scipy; print('scipy', scipy.__version__)")
    check_pkg(c, "matplotlib", "import matplotlib; print('matplotlib', matplotlib.__version__)")
    check_pkg(c, "pandas", "import pandas; print('pandas', pandas.__version__)")
    check_pkg(c, "sklearn", "import sklearn; print('sklearn', sklearn.__version__)")

    # 深度学习
    print("\n[深度学习]")
    check_pkg(c, "transformers", "import transformers; print('transformers', transformers.__version__)")
    check_pkg(c, "timm", "import timm; print('timm', timm.__version__)")
    check_pkg(c, "accelerate", "import accelerate; print('accelerate', accelerate.__version__)")
    check_pkg(c, "huggingface", "import huggingface_hub; print('huggingface_hub', huggingface_hub.__version__)")

    # 3D / GIS
    print("\n[3D & GIS]")
    check_pkg(c, "plyfile", "import plyfile; print('plyfile', plyfile.__version__)")
    check_pkg(c, "trimesh", "import trimesh; print('trimesh', trimesh.__version__)")
    check_pkg(c, "open3d", "import open3d; print('open3d', open3d.__version__)")
    check_pkg(c, "geopandas", "import geopandas; print('geopandas', geopandas.__version__)")
    check_pkg(c, "rasterio", "import rasterio; print('rasterio', rasterio.__version__)")
    check_pkg(c, "shapely", "import shapely; print('shapely', shapely.__version__)")
    check_pkg(c, "albumentations", "import albumentations; print('albumentations', albumentations.__version__)")
    check_pkg(c, "scikit-image", "import skimage; print('skimage', skimage.__version__)")

    # COLMAP
    print("\n[3DGS Tools]")
    out, _ = run(c, "which colmap 2>&1; colmap version 2>&1 | head -3", timeout=10)
    print(f"  COLMAP: {out.strip() or '未安装'}")
    out, _ = run(c, "which gaussian-splatting 2>&1; which gs 2>&1 || echo '3DGS CLI not found'")
    print(f"  3DGS CLI: {out.strip()}")

    # 磁盘
    print("\n[磁盘]")
    out, _ = run(c, "df -h / /autodl-pub/data /tmp 2>&1")
    print(out)

    # 安装进度
    print("\n[安装进度]")
    for step in ["step2_pytorch.done", "step3_core.done", "step4_dl.done", "step5_3d.done", "INSTALL_DONE"]:
        out, _ = run(c, f"test -f /root/gis_project/gpu_scripts/{step} && echo 'done' || echo 'pending'", timeout=5)
        print(f"  {step}: {out.strip()}")

    # pip list
    print("\n[pip list (前50)]")
    out, _ = run(c, "/root/miniconda3/bin/pip list 2>&1 | head -50")
    print(out)

    c.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
