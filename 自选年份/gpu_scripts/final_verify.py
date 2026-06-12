# -*- coding: utf-8 -*-
"""GPU 服务器环境最终验证"""
import paramiko

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

VENV = "/root/venv"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=20):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

def test(c, desc, code):
    out, _ = run(c, f"{VENV}/bin/python -c '{code}' 2>&1")
    ok = "OK" if out.strip() and "error" not in out.lower() and "no module" not in out.lower() else "FAIL"
    print(f"  [{ok}] {desc}: {out.strip()[:80]}")
    return ok == "OK"

def main():
    c = ssh()
    print("=" * 55)
    print("GPU 服务器环境最终验证")
    print("=" * 55)

    # GPU 测试
    print("\n[GPU]")
    out, _ = run(c, f"{VENV}/bin/python << 'EOF'\n"
        "import torch\n"
        "print('torch:', torch.__version__)\n"
        "print('CUDA:', torch.cuda.is_available())\n"
        "if torch.cuda.is_available():\n"
        "    print('GPU:', torch.cuda.get_device_name(0))\n"
        "    props = torch.cuda.get_device_properties(0)\n"
        "    print('VRAM:', props.total_memory / 1024**3, 'GB')\n"
        "    x = torch.randn(5000, 5000, device='cuda')\n"
        "    y = x @ x.T\n"
        "    print('GEMM OK:', y.sum().item())\n"
        "EOF", timeout=60)
    print(f"  {out.strip()}")

    # 核心库
    print("\n[核心库]")
    tests = [
        ("opencv", "import cv2; print('cv2', cv2.__version__)"),
        ("numpy", "import numpy; print('numpy', numpy.__version__)"),
        ("pillow", "from PIL import Image; print('PIL OK')"),
        ("scipy", "import scipy; print('scipy', scipy.__version__)"),
        ("matplotlib", "import matplotlib; print('matplotlib', matplotlib.__version__)"),
        ("pandas", "import pandas; print('pandas', pandas.__version__)"),
        ("sklearn", "import sklearn; print('sklearn', sklearn.__version__)"),
        ("albumentations", "import albumentations; print('albumentations', albumentations.__version__)")
    ]
    for desc, code in tests:
        test(c, desc, code)

    # 深度学习
    print("\n[深度学习]")
    tests = [
        ("transformers", "import transformers; print('transformers', transformers.__version__)"),
        ("timm", "import timm; print('timm', timm.__version__)"),
        ("accelerate", "import accelerate; print('accelerate', accelerate.__version__)"),
        ("torchvision", "import torchvision; print('torchvision', torchvision.__version__)")
    ]
    for desc, code in tests:
        test(c, desc, code)

    # 3D / GIS
    print("\n[3D & GIS]")
    tests = [
        ("plyfile", "import plyfile; print('plyfile', plyfile.__version__)"),
        ("trimesh", "import trimesh; print('trimesh', trimesh.__version__)"),
        ("geopandas", "import geopandas; print('geopandas', geopandas.__version__)"),
        ("rasterio", "import rasterio; print('rasterio', rasterio.__version__)"),
        ("shapely", "import shapely; print('shapely', shapely.__version__)")
    ]
    for desc, code in tests:
        test(c, desc, code)

    # GPU 状态
    print("\n[GPU 状态]")
    out, _ = run(c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>&1")
    print(f"  {out.strip()}")

    # 磁盘
    print("\n[磁盘]")
    out, _ = run(c, "df -h / /autodl-pub/data 2>&1 | tail -3")
    print(f"  {out.strip()}")

    c.close()
    print("\n验证完成!")

if __name__ == "__main__":
    main()
