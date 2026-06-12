#!/usr/bin/env python3
"""检查服务器上所有可用的检测/分割相关模型和库"""
import paramiko, json, textwrap

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

commands = {
    "已安装的相关包": "pip list 2>/dev/null | grep -iE 'yolo|ultralytics|segmentation|pytorch|torchvision|transformers|mmdet|mmseg|detectron|opencv|cv2|scikit|albumentations|timm|clip| grounding' | head -40",
    "GPU型号 + CUDA": "nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader",
    "Python版本": "python3 --version",
    "torchvision版本": "python3 -c 'import torchvision; print(torchvision.__version__)' 2>/dev/null",
    "timm版本": "python3 -c 'import timm; print(timm.__version__)' 2>/dev/null",
    "可用YOLO模型检查": "python3 -c \"from ultralytics import YOLO; print('ultralytics OK')\" 2>/dev/null || echo 'ultralytics NOT installed'",
    "transformers版本": "python3 -c 'import transformers; print(transformers.__version__)' 2>/dev/null",
    "GroundingDINO检查": "python3 -c 'import grounding_dino; print(\"grounding_dino OK\")' 2>/dev/null || echo 'grounding_dino NOT installed'",
    "CLIP版本": "python3 -c 'import clip; print(\"clip OK\")' 2>/dev/null || echo 'clip NOT installed'",
    "detectron2检查": "python3 -c 'import detectron2; print(\"detectron2 OK\")' 2>/dev/null || echo 'detectron2 NOT installed'",
    "segmentation_models检查": "python3 -c 'import segmentation_models_pytorch; print(\"segmentation_models_pytorch OK\")' 2>/dev/null || echo 'segmentation_models_pytorch NOT installed'",
    "torch版本": "python3 -c 'import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\")'",
    "已缓存的YOLO模型": f"ls ~/.cache/ultralytics/ 2>/dev/null | head -20 || echo 'no ultralytics cache'",
    "服务器磁盘空间": "df -h /root | tail -1",
    "GPU内存": "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader",
}

for title, cmd in commands.items():
    print(f"\n{'='*60}\n=== {title} ===")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out)
    if err and "warning" not in err.lower():
        print(f"[stderr] {err[:200]}")

c.close()
