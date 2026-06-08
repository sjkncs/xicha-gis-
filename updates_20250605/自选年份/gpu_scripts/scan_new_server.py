#!/usr/bin/env python3
import paramiko, time

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

cmds = [
    ("streetview_seg dir", "ls -la /root/streetview_seg/ 2>&1"),
    ("find jpg files", "find /root/ -name '*.jpg' -type f 2>/dev/null | head -20"),
    ("find panorama dirs", "find /root/ -maxdepth 5 -type d 2>/dev/null | grep -i -E 'panorama|streetview|baidu|全景|图像' | head -20"),
    ("find gpu_scripts on autodl-pub", "find /root/autodl-pub/ -maxdepth 4 -type d 2>/dev/null | grep -v 'COCO\|ADE\|VOC\|ImageNet\|KITTI\|MOT\|LaSOT\|Tracking\|S3DIS\|DRIVE\|DIV2K\|ModelNet\|NUSWIDE\|DOTA\|Objects\|CUB\|ILSVRC\|CelebA\|CASIA\|CMLR\|BERT\|RoBERTa\|Aishell\|argoverse\|nuScenes\|SemanticKITTI\|TT100K\|CULane\|MPI' | head -30"),
    ("miniconda envs", "source /root/miniconda3/etc/profile.d/conda.sh && conda env list 2>&1"),
    ("venv transformers", "source /root/venv/bin/activate && pip show transformers 2>&1"),
    ("sys disk usage", "df -h / 2>&1"),
    ("home size", "du -sh /root/ 2>&1"),
]
for name, cmd in cmds:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f"=== {name} ===")
    print(out[:800] if out else err[:300])
    print()

client.close()
