#!/usr/bin/env python3
import paramiko
HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace')

c = ssh()

searches = [
    ("All pth/pt files", "find /root /autodl-pub /usr -maxdepth 6 -name '*.pth' -o -name '*.pt' -o -name '*.safetensors' 2>/dev/null | head -30"),
    ("Torch hub cache", "ls -la ~/.cache/torch/hub/ 2>/dev/null; ls -la ~/.cache/torch/checkpoints/ 2>/dev/null"),
    ("HuggingFace cache", "ls -la ~/.cache/huggingface/ 2>/dev/null"),
    ("pip cache", "ls ~/.cache/pip/ 2>/dev/null | head -20"),
    ("Model weights dir", "ls -la /root/.cache/ 2>/dev/null; find /root/.cache -type f 2>/dev/null | head -30"),
    ("autodl cache", "ls -la /root/.cache/ 2>/dev/null; find /autodl-tmp -type f 2>/dev/null | head -10"),
    ("Checkpoints anywhere", "find /root -maxdepth 5 -type d -name 'checkpoints' -o -name 'models' -o -name 'weights' 2>/dev/null | head -10"),
    ("FCN ResNet50", "ls /root/.cache/torch/hub/checkpoints/ 2>/dev/null; ls /root/.cache/huggingface/hub/ 2>/dev/null | head -20"),
    ("Try no-weights load", "/root/miniconda3/bin/python -c 'from torchvision.models.segmentation.fcn import fcn_resnet50; m = fcn_resnet50(); print(len(m.classifier[4].bias))' 2>&1"),
]

for name, cmd in searches:
    try:
        out = run(c, cmd)
        if out.strip():
            print(f"\n# {name}:")
            print(out.strip()[:500])
    except Exception as e:
        print(f"# {name}: ERROR {e}")

c.close()
