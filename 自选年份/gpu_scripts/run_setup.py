# -*- coding: utf-8 -*-
"""GPU 服务器完整部署：上传脚本 + 分步执行"""
import paramiko
from pathlib import Path
import time

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE_WORK = "/root/gis_project"

SCRIPTS_DIR = Path(__file__).parent

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=30, check_err=True):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if check_err and err and "error" in err.lower() and "warning" not in err.lower():
        print(f"  [WARN] stderr: {err.strip()[:200]}")
    return out

def put(c, local_path, remote_path):
    s = c.open_sftp()
    s.put(str(local_path), remote_path)
    s.close()
    print(f"  上传: {Path(local_path).name}")

def main():
    print("=" * 60)
    print("GPU 服务器完整部署")
    print("=" * 60)

    c = ssh()
    print("Connected!\n")

    # ====== 上传安装脚本 ======
    print("[1] 上传安装脚本...")
    scripts = {
        "setup_full.sh": f"{REMOTE_WORK}/gpu_scripts/setup_full.sh",
        "setup_step1_env.sh": f"{REMOTE_WORK}/gpu_scripts/setup_step1_env.sh",
    }
    for name, remote in scripts.items():
        lp = SCRIPTS_DIR / name
        if lp.exists():
            put(c, lp, remote)
            run(c, f"chmod +x {remote}")
            print(f"  {name} -> {remote}")
    print()

    # ====== STEP 1: pip 镜像 ======
    print("[2] 配置 pip 镜像...")
    out = run(c, 'pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>&1')
    print(f"  {out.strip()}")
    out = run(c, 'pip config set global.trusted-host https://pypi.tuna.tsinghua.edu.cn 2>&1')
    print(f"  {out.strip()}")
    out = run(c, 'pip config set global.timeout 120 2>&1')
    print(f"  {out.strip()}")

    # ====== STEP 2: 升级 pip ======
    print("\n[3] 升级 pip...")
    out = run(c, "pip install --upgrade pip 2>&1 | tail -2", timeout=60)
    print(f"  {out.strip()}")

    # ====== STEP 3: PyTorch 2.5 ======
    print("\n[4] 安装 PyTorch 2.5 + CUDA 12.4 (预计 3-8 分钟)...")
    out = run(c,
        "pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -5",
        timeout=600)
    print(f"  {out.strip()}")

    # ====== STEP 4: 验证 PyTorch ======
    print("\n[5] 验证 PyTorch + GPU...")
    out = run(c, (
        'python -c "import torch; '
        'print(f\\\'PyTorch:{torch.__version__} CUDA:{torch.cuda.is_available()}\\\'); '
        'if torch.cuda.is_available(): print(f\\\'GPU:{torch.cuda.get_device_name(0)}\\\')"'
    ), timeout=60)
    print(f"  {out.strip()}")

    # ====== STEP 5: 核心依赖 ======
    print("\n[6] 安装核心 Python 库...")
    cmd = (
        "pip install numpy==1.26.4 opencv-python==4.10.0.84 opencv-python-headless==4.10.0.84 "
        "pillow==10.4.0 scipy==1.13.1 matplotlib==3.9.0 seaborn==0.13.2 "
        "pandas==2.2.2 scikit-learn==1.5.1 scikit-image==0.24.0 albumentations==1.4.15 2>&1 | tail -5"
    )
    out = run(c, cmd, timeout=600)
    print(f"  {out.strip()[-300:]}")

    # ====== STEP 6: transformers + timm ======
    print("\n[7] 安装 transformers + timm...")
    cmd = (
        "pip install transformers==4.46.0 timm==0.9.16 accelerate==1.2.1 "
        "huggingface_hub==0.27.0 sentencepiece==0.2.0 2>&1 | tail -5"
    )
    out = run(c, cmd, timeout=600)
    print(f"  {out.strip()[-300:]}")

    # ====== STEP 7: 3D / GIS 库 ======
    print("\n[8] 安装 3D/GIS 处理库...")
    cmd = (
        "pip install plyfile==1.0.3 open3d==0.19.0 rasterio==1.3.11 "
        "shapely==2.0.5 geopandas==0.14.4 pyproj==3.7.0 2>&1 | tail -5"
    )
    out = run(c, cmd, timeout=600)
    print(f"  {out.strip()[-300:]}")

    # ====== STEP 8: 完整验证 ======
    print("\n[9] 完整验证...")
    out = run(c, (
        'python -c "import torch, cv2, numpy, PIL, scipy, transformers, timm; '
        'print(f\\\'torch:{torch.__version__} opencv:{cv2.__version__} numpy:{numpy.__version__}\\\'); '
        'print(f\\\'transformers:{transformers.__version__} timm:{timm.__version__}\\\'); '
        'if torch.cuda.is_available(): print(f\\\'GPU:{torch.cuda.get_device_name(0)} VRAM:{torch.cuda.get_device_properties(0).total_mem/1024**3:.0f}GB\\\')"'
    ), timeout=60)
    print(f"  {out.strip()}")

    # ====== STEP 9: 检查 gis_project 数据 ======
    print("\n[10] 检查 gis_project 数据目录...")
    out = run(c, f"ls -la {REMOTE_WORK}/data/ 2>&1")
    print(f"  {out.strip()}")

    # ====== STEP 10: GPU 状态确认 ======
    print("\n[11] GPU 最终状态...")
    out = run(c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>&1")
    print(f"  {out.strip()}")

    print("\n==== 安装完成! ====")
    c.close()

if __name__ == "__main__":
    main()
