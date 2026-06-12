# -*- coding: utf-8 -*-
"""分步上传 + 执行 GPU 服务器环境安装"""
import paramiko, os
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE_WORK = "/root/gis_project"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

def put(c, local, remote):
    s = c.open_sftp()
    s.put(local, remote)
    s.close()
    print(f"  PUT: {Path(local).name} -> {remote}")

# ========== STEP 1: 上传 + 执行基础安装 ==========
def step1_setup(c):
    print("\n=== STEP 1: 基础环境安装 ===")

    # 创建目录
    run(c, f"mkdir -p {REMOTE_WORK}/gpu_scripts {REMOTE_WORK}/data {REMOTE_WORK}/outputs {REMOTE_WORK}/models")

    # 上传脚本
    script_path = Path(__file__).parent / "setup_step1_env.sh"
    if script_path.exists():
        put(c, str(script_path), f"{REMOTE_WORK}/gpu_scripts/setup_step1_env.sh")
        print("  已上传 setup_step1_env.sh")
    else:
        print(f"  找不到脚本: {script_path}")

    # 改权限
    run(c, f"chmod +x {REMOTE_WORK}/gpu_scripts/setup_step1_env.sh")

    # 配置 pip 镜像
    print("  配置 pip 镜像...")
    out, err = run(c, 'pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>&1', timeout=30)
    print(f"  {out.strip()}")

    # 安装系统依赖
    print("  安装系统依赖 (apt-get)...")
    out, err = run(c,
        "apt-get update -qq && "
        "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "
        "git curl wget unzip libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev "
        "libgomp1 build-essential cmake pkg-config 2>&1 | tail -5",
        timeout=120)
    print(f"  {out.strip()}")

    # 检查 conda
    out, err = run(c, "which conda 2>&1", timeout=10)
    has_conda = bool(out.strip())

    if not has_conda:
        print("  安装 Miniconda...")
        out, err = run(c,
            "wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh && "
            "bash /tmp/miniconda.sh -b -p /opt/conda && rm /tmp/miniconda.sh && "
            "ls /opt/conda/bin/conda | head -2",
            timeout=180)
        print(f"  {out.strip()}")
    else:
        print(f"  Conda 已存在: {out.strip()}")

    # 创建环境
    print("  创建 conda 环境 gis_ai...")
    out, err = run(c,
        "/opt/conda/bin/conda create -y -n gis_ai python=3.10 2>&1 | tail -5",
        timeout=300)
    print(f"  {out.strip()}")

    # 安装 PyTorch
    print("  安装 PyTorch 2.5 + CUDA 12.4 (预计 3-8 分钟)...")
    cmd = (
        "/opt/conda/bin/pip install --upgrade pip setuptools wheel 2>&1 | tail -2 && "
        "/opt/conda/bin/pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -3"
    )
    out, err = run(c, cmd, timeout=600)
    print(f"  {out.strip()[-300:]}")

    # 验证 PyTorch
    print("  验证 PyTorch CUDA...")
    out, err = run(c,
        "/opt/conda/bin/python -c \"import torch; print(f'PyTorch:{torch.__version__} CUDA:{torch.cuda.is_available()} v{torch.version.cuda} GPU:{torch.cuda.get_device_name(0) if torch.cuda.is_available() else \\\"None\\\"}')\"",
        timeout=30)
    print(f"  {out.strip()}")

    # 安装核心依赖
    print("  安装核心 Python 库...")
    cmd = (
        "/opt/conda/bin/pip install numpy==1.26.4 pandas pillow scipy matplotlib seaborn "
        "opencv-python opencv-python-headless scikit-learn scikit-image albumentations 2>&1 | tail -3"
    )
    out, err = run(c, cmd, timeout=300)
    print(f"  {out.strip()[-200:]}")

    # 安装 transformers + timm
    print("  安装 transformers + timm...")
    cmd = (
        "/opt/conda/bin/pip install transformers==4.46.0 timm==0.9.16 accelerate huggingface_hub sentencepiece 2>&1 | tail -3"
    )
    out, err = run(c, cmd, timeout=300)
    print(f"  {out.strip()[-200:]}")

    # 全部验证
    print("  完整验证...")
    verify = (
        "/opt/conda/bin/python -c \""
        "import torch; import cv2; import timm; import transformers; import numpy; import PIL; "
        "print(f'torch:{torch.__version__} CUDA:{torch.cuda.is_available()} GPU:{torch.cuda.get_device_name(0) if torch.cuda.is_available() else \\\"N/A\\\"}'); "
        "print(f'opencv:{cv2.__version__} timm:{timm.__version__} transformers:{transformers.__version__} numpy:{numpy.__version__}')\""
    )
    out, err = run(c, verify, timeout=60)
    print(f"  {out.strip()}")
    return True

# ========== STEP 2: 上传全景图数据 ==========
def step2_upload_data(c):
    print("\n=== STEP 2: 上传全景图数据 ===")

    # 统计文件
    panorama_dir = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
    all_jpg = list(panorama_dir.rglob("*.jpg"))
    print(f"  全景图总数: {len(all_jpg)}")

    # 用 scp 递归上传整个目录 (比 Python SFTP 更快)
    # 由于文件多，先上传 manifest + 少量样本
    manifest_local = panorama_dir / "manifest.csv"
    if manifest_local.exists():
        put(c, str(manifest_local), f"{REMOTE_WORK}/data/manifest.csv")
        print(f"  manifest.csv 已上传")

    # 上传 segmentation_results
    seg_dir = panorama_dir / "segmentation_results_v3"
    seg_results_csv = seg_dir / "seg_results.csv"
    if seg_results_csv.exists():
        put(c, str(seg_results_csv), f"{REMOTE_WORK}/data/seg_results.csv")
        print(f"  seg_results.csv 已上传")

    # 上传楼栋/POI 数据
    data_files = [
        (r"e:\xicha gis 智能定位\projects\15min-urban-accessibility\building_data\nanshan_buildings_official.geojson",
         f"{REMOTE_WORK}/data/nanshan_buildings_official.geojson"),
        (r"e:\xicha gis 智能定位\projects\15min-urban-accessibility\osm_data\nanshan_network_nodes.csv",
         f"{REMOTE_WORK}/data/nanshan_network_nodes.csv"),
        (r"e:\xicha gis 智能定位\projects\15min-urban-accessibility\osm_data\nanshan_poi_v5.json",
         f"{REMOTE_WORK}/data/nanshan_poi_v5.json"),
    ]
    for local, remote in data_files:
        if Path(local).exists():
            put(c, local, remote)
            print(f"  {Path(local).name} 已上传")

    # 用 scp 批量上传全景点 (通过 sshpass 或 subprocess)
    import subprocess
    print("\n  用 scp 批量上传全景图目录...")
    cmd = [
        "sshpass", "-proBbKv+ed3Vm",
        "scp", "-o", "StrictHostKeyChecking=no",
        "-P", "37625", "-r",
        str(panorama_dir) + "/Village",
        f"root@connect.bjb1.seetacloud.com:{REMOTE_WORK}/data/baidu_streetview/"
    ]
    print(f"  执行: sshpass scp -r Village/ ... (预计 5-15 分钟)")
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode == 0:
            print("  全景点上传完成")
        else:
            print(f"  scp 失败 (exit {result.returncode}), 尝试 rsync...")
            cmd2 = [
                "rsync", "-avz", "--progress",
                "-e", f"ssh -o StrictHostKeyChecking=no -p 37625",
                str(panorama_dir) + "/Village/",
                f"root@connect.bjb1.seetacloud.com:{REMOTE_WORK}/data/baidu_streetview/"
            ]
            result = subprocess.run(cmd2, capture_output=True, timeout=900)
            if result.returncode == 0:
                print("  rsync 上传完成")
            else:
                print(f"  rsync 也失败了，错误: {result.stderr.decode()[-200:]}")
    except FileNotFoundError:
        print("  sshpass/rsync 未安装，将通过 Python SFTP 上传...")
        sftp = c.open_sftp()
        upload_tree(sftp, str(panorama_dir / "Village"), f"{REMOTE_WORK}/data/baidu_streetview/Village")
        sftp.close()

def upload_tree(sftp, local_dir, remote_dir):
    """递归上传目录"""
    import os
    local = Path(local_dir)
    try:
        sftp.mkdir(remote_dir)
    except:
        pass
    for item in local.iterdir():
        remote_path = f"{remote_dir}/{item.name}"
        if item.is_dir():
            try:
                sftp.mkdir(remote_path)
            except:
                pass
            upload_tree(sftp, str(item), remote_path)
        else:
            sftp.put(str(item), remote_path)

def main():
    print("=" * 60)
    print("GPU 服务器环境部署")
    print("=" * 60)

    try:
        print("Connecting...")
        c = ssh()
        print("Connected!\n")

        ok = step1_setup(c)
        if ok:
            print("\n==== STEP 1 完成! ====")
            step2_upload_data(c)

            print("\n==== 全部完成! ====")
            print(f"服务器: {REMOTE_WORK}")
            print("激活环境: conda activate gis_ai")

        c.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    main()
