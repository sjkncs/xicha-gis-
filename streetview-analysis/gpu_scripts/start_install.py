# -*- coding: utf-8 -*-
"""GPU 服务器安装：使用 heredoc 直接写入脚本并后台运行"""
import paramiko, time
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE = "/root/gis_project"

SCRIPT_CONTENT = r"""#!/bin/bash
set -e
LOG="/root/gis_project/gpu_scripts/install.log"
exec > $LOG 2>&1
echo "===== 开始安装 $(date) ====="

# 1. pip 镜像
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip config set global.trusted-host https://pypi.tuna.tsinghua.edu.cn
pip install --upgrade pip setuptools wheel

# 2. 卸载旧版 PyTorch
pip uninstall -y torch torchvision torchaudio 2>/dev/null || true

# 3. 安装 PyTorch 2.5 + CUDA 12.4
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
echo "PyTorch 完成"

# 4. 核心库
pip install numpy==1.26.4 opencv-python==4.10.0.84 opencv-python-headless==4.10.0.84 \
  pillow==10.4.0 scipy==1.13.1 matplotlib==3.9.0 seaborn==0.13.2 \
  pandas==2.2.2 scikit-learn==1.5.1 scikit-image==0.24.0 albumentations==1.4.15
echo "核心库完成"

# 5. 深度学习库
pip install transformers==4.46.0 timm==0.9.16 accelerate huggingface_hub sentencepiece
echo "DL库完成"

# 6. 3D/GIS库
pip install plyfile open3d rasterio shapely geopandas pyproj
echo "3D/GIS库完成"

# 7. 验证
python -c "
import torch, cv2, numpy, PIL, scipy, transformers, timm
print('torch:', torch.__version__, 'CUDA:', torch.cuda.is_available())
print('opencv:', cv2.__version__)
print('transformers:', transformers.__version__)
print('timm:', timm.__version__)
if torch.cuda.is_available():
    print('GPU:', torch.cuda.get_device_name(0))
    t = torch.randn(100,100).cuda()
    print('GPU测试:', t.sum().item(), 'OK')
"

echo "===== 安装完成 $(date) ====="
touch /root/gis_project/gpu_scripts/INSTALL_DONE
"""

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=15):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

def put_content(c, content, remote_path):
    """通过 cat heredoc 写入文件内容"""
    # 转义单引号
    escaped = content.replace("'", "'\"'\"'")
    cmd = f"cat > '{remote_path}' << 'ENDOFFILE'\n{content}\nENDOFFILE"
    out, err = run(c, cmd, timeout=20)
    return out, err

def main():
    c = ssh()
    print("Connected!")

    # 检查是否已安装
    out, _ = run(c, f"test -f {REMOTE}/gpu_scripts/INSTALL_DONE && echo done || echo not_done", timeout=10)
    if "done" in out:
        print("安装已完成！验证环境...")
        out, _ = run(c, "/root/miniconda3/bin/python -c \"import torch; print(torch.__version__, torch.cuda.is_available())\"", timeout=30)
        print(f"  {out.strip()}")
        c.close()
        return

    # 写入安装脚本
    print("\n[1] 写入安装脚本...")
    script_path = f"{REMOTE}/gpu_scripts/install.sh"
    out, err = put_content(c, SCRIPT_CONTENT, script_path)
    if err.strip():
        print(f"  写入结果: {err.strip()[:200]}")
    run(c, f"chmod +x {script_path}", timeout=10)
    print(f"  脚本已写入: {script_path}")

    # 检查是否已经在运行
    out, _ = run(c, "ps aux | grep 'install.sh' | grep -v grep | head -2", timeout=10)
    if out.strip():
        print(f"\n  安装已在运行: {out.strip()}")
        print("  等待完成中...")
        # 等待最多 30 分钟
        for i in range(30):
            time.sleep(60)
            out, _ = run(c, f"test -f {REMOTE}/gpu_scripts/INSTALL_DONE && echo done || echo not_done", timeout=10)
            if "done" in out:
                print(f"\n  安装完成! (等待了 {i+1} 分钟)")
                break
            print(f"  [{i+1}/30] 仍在运行中...", end="\r")
    else:
        # 后台启动
        print("\n[2] 后台启动安装...")
        out, err = run(c, f"cd {REMOTE}/gpu_scripts && nohup bash install.sh > install.out 2>&1 &", timeout=10)
        print(f"  nohup: {out.strip() or '启动成功'}")

        # 等待 2 分钟后检查
        print("\n[3] 等待 2 分钟后检查...")
        time.sleep(120)

    # 检查日志
    print("\n[4] 检查安装日志...")
    out, _ = run(c, f"tail -20 {REMOTE}/gpu_scripts/install.log 2>&1", timeout=10)
    print(f"  {out.strip()}")

    # 检查是否完成
    out, _ = run(c, f"test -f {REMOTE}/gpu_scripts/INSTALL_DONE && echo done || echo not_done", timeout=10)
    if "done" in out:
        print("\n  安装已完成！验证中...")
        out, _ = run(c, "/root/miniconda3/bin/python -c \"import torch; print('torch:', torch.__version__)\"", timeout=30)
        print(f"  {out.strip()}")
    else:
        print("\n  安装尚未完成")
        print(f"  查看进度: tail -f {REMOTE}/gpu_scripts/install.log")
        print("  查看实时输出: tail {REMOTE}/gpu_scripts/install.out")

    c.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
