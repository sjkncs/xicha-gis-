#!/usr/bin/env python3
"""完整安装 Grounding DINO 到远程服务器"""
import paramiko, os

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()

def run(c, cmd, timeout=600):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

# 1. 复制正确的config文件
print("=== 1. 复制 config ===")
out, err, ec = run(c, "cp /root/autodl-tmp/streetview_analysis/groundingdino_repo/groundingdino/config/GroundingDINO_SwinT_OGC.py /root/autodl-tmp/streetview_analysis/groundingdino/GroundingDINO_SwinT_OGC.py && echo OK")
print(f"[{ec}] {out} | {err[:100]}")

# 2. 创建 __init__.py 修复导入
print("\n=== 2. 创建 config __init__.py ===")
out, err, ec = run(c, "mkdir -p /root/autodl-tmp/streetview_analysis/groundingdino/config /root/autodl-tmp/streetview_analysis/groundingdino/util && echo dirs created")
print(f"[{ec}] {out}")
init_py = b'''
from .GroundingDINO_SwinT_OGC import *
from .GroundingDINO_SwinB_cfg import *
'''
sftp.file("/root/autodl-tmp/streetview_analysis/groundingdino/config/__init__.py", "wb").write(init_py)
print("OK")

# 3. 创建 SLConfig 兼容文件
print("\n=== 3. 创建 slconfig ===")
slconfig_content = b'''
import os
from typing import Any, Dict, List

class SLConfig:
    def __init__(self, config_dict: Dict[str, Any] = None, **kwargs):
        if config_dict:
            for k, v in config_dict.items():
                setattr(self, k, v)
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def fromfile(cls, path):
        import importlib.util
        module_name = os.path.basename(path).replace(".py", "")
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return cls(**module.CFG)
'''
sftp.file("/root/autodl-tmp/streetview_analysis/groundingdino/util/slconfig.py", "wb").write(slconfig_content)
print("OK")

# 4. 创建 util __init__.py
print("\n=== 4. 创建 util __init__.py ===")
util_init = b'''
from .slconfig import SLConfig
from .inference import predict
from .box_ops import box_cxcywh_to_xyxy, box_xyxy_to_cxcywh
'''
sftp.file("/root/autodl-tmp/streetview_analysis/groundingdino/util/__init__.py", "wb").write(util_init)
print("OK")

# 5. 安装 groundingdino（--no-deps 避免重新装torch）
print("\n=== 5. 安装 groundingdino (no-deps) ===")
out, err, ec = run(c,
    "cd /root/autodl-tmp/streetview_analysis/groundingdino_repo && "
    "pip install -q --no-deps . 2>&1 | tail -5")
print(f"[{ec}] {out}")
if err: print(f"err: {err[:200]}")

# 6. 下载模型权重
print("\n=== 6. 下载模型权重 (~2.7GB) ===")
out, err, ec = run(c,
    "cd /root/autodl-tmp/streetview_analysis/groundingdino && "
    "wget -q --show-progress -O groundingdino_swint_ogc.pth "
    "https://huggingface.co/ShilongLiu/GroundingDINO/resolve/main/groundingdino_swint_ogc.pth 2>&1 | tail -3",
    timeout=900)
print(f"[{ec}] {out[-200:]}")

# 检查文件大小
out2, _, _ = run(c, "ls -lh /root/autodl-tmp/streetview_analysis/groundingdino/groundingdino_swint_ogc.pth")
print(f"文件: {out2}")

# 7. 安装 transformers (如果没有)
print("\n=== 7. 确保 transformers 足够新 ===")
out, err, ec = run(c, "pip install -q 'transformers>=4.40.0' 2>&1 | tail -3")
print(f"[{ec}] {out}")

# 8. 上传检测脚本
print("\n=== 8. 上传检测脚本 ===")
local_script = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\grounding_dino_detect.py"
sftp.put(local_script, f"{REMOTE_DIR}/grounding_dino_detect.py")
print("OK")

# 9. 上传运行脚本
run_script = f"""#!/bin/bash
cd {REMOTE_DIR}
nohup python3 grounding_dino_detect.py > grounding_run.log 2>&1 &
echo "PID=$!" > grounding_pid.txt
echo "Started, waiting 5s..."
sleep 5
tail -3 grounding_run.log
"""
sftp.file(f"{REMOTE_DIR}/run_gdino.sh", "w").write(run_script.encode())
out, err, ec = run(c, f"chmod +x {REMOTE_DIR}/run_gdino.sh && bash {REMOTE_DIR}/run_gdino.sh")
print(f"[{ec}] {out[-300:]}")

sftp.close()
c.close()
print("\n=== 安装完成 ===")
