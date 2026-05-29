# -*- coding: utf-8 -*-
"""全面诊断 venv 环境 + GPU 测试"""
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

def main():
    c = ssh()

    print("=" * 55)
    print("venv 环境全面诊断")
    print("=" * 55)

    # 1. venv 所有包
    print("\n[1] /root/venv 所有包...")
    out, _ = run(c, f"{VENV}/bin/pip list 2>&1 | sort")
    print(out)

    # 2. GPU 完整测试 (用 venv python)
    print("\n[2] venv Python GPU 测试...")
    out, _ = run(c,
        f"{VENV}/bin/python -c \""
        "import torch; "
        "print('torch:', torch.__version__); "
        "print('CUDA:', torch.cuda.is_available()); "
        "if torch.cuda.is_available(): "
        "    print('GPU:', torch.cuda.get_device_name(0)); "
        "    print('VRAM:', torch.cuda.get_device_properties(0).total_memory / 1024**3, 'GB'); "
        "    x = torch.randn(5000, 5000, device='cuda'); "
        "    y = x @ x.T; "
        "    print('GEMM test OK:', y.sum().item()); \" 2>&1",
        timeout=60)
    print(f"  {out.strip()}")

    # 3. 测试 torch 在 GPU 上的兼容性
    print("\n[3] 测试 CUDA 12.1 兼容性...")
    out, _ = run(c, "nvidia-smi | grep -E 'CUDA|Driver' | head -5")
    print(f"  Driver CUDA: {out.strip()}")
    print("  (CUDA 12.1 运行时应向后兼容 CUDA 13.1 驱动)")

    # 4. 检查其他关键包
    print("\n[4] 检查关键包...")
    for pkg, code in [
        ("numpy", "import numpy; print(numpy.__version__)"),
        ("opencv", "import cv2; print(cv2.__version__)"),
        ("pillow", "from PIL import Image; print('PIL OK')"),
        ("scipy", "import scipy; print(scipy.__version__)"),
        ("transformers", "import transformers; print(transformers.__version__)"),
        ("timm", "import timm; print(timm.__version__)"),
        ("matplotlib", "import matplotlib; print(matplotlib.__version__)"),
        ("pandas", "import pandas; print(pandas.__version__)"),
        ("sklearn", "import sklearn; print(sklearn.__version__)"),
        ("albumentations", "import albumentations; print(albumentations.__version__)")
    ]:
        out, _ = run(c, f"{VENV}/bin/python -c \"{code}\" 2>&1")
        ok = "OK" if out.strip() and "error" not in out.lower() and "no module" not in out.lower() else "MISSING"
        print(f"  [{ok}] {pkg}: {out.strip()[:80]}")

    # 5. 安装缺失的包
    print("\n[5] 安装缺失包 (在 venv 中)...")
    cmd = (
        f"{VENV}/bin/pip install "
        "opencv-python-headless scipy transformers timm accelerate huggingface_hub "
        "pillow pandas scikit-learn albumentations plyfile trimesh "
        "geopandas rasterio shapely pyproj scikit-image 2>&1 | tail -5"
    )
    print("  安装中 (预计 3-10 分钟)...")
    out, _ = run(c, cmd, timeout=900)
    print(f"  {out.strip()[-500:]}")

    # 6. 再次验证
    print("\n[6] 最终验证...")
    out, _ = run(c,
        f"{VENV}/bin/python -c \""
        "import torch, cv2, numpy, PIL, scipy, transformers, timm; "
        "print('torch:', torch.__version__, 'CUDA:', torch.cuda.is_available()); "
        "print('opencv:', cv2.__version__); "
        "print('numpy:', numpy.__version__); "
        "print('scipy:', scipy.__version__); "
        "print('transformers:', transformers.__version__); "
        "print('timm:', timm.__version__); "
        "if torch.cuda.is_available(): "
        "    print('GPU:', torch.cuda.get_device_name(0))\" 2>&1",
        timeout=60)
    print(f"  {out.strip()}")

    c.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
