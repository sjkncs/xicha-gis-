#!/usr/bin/env python3
"""检查benchmark结果，然后测试带权重的推理"""
import paramiko, time, sys

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
PYTHON = "/root/miniconda3/bin/python"
REMOTE_DIR = "/root/autodl-tmp"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

c = ssh()
sftp = c.open_sftp()

# 检查bench结果
try:
    with sftp.open(f"{REMOTE_DIR}/bench_result.txt") as f:
        print("=== 已有结果 ===")
        print(f.read().decode())
except:
    print("无结果文件")

# 检查torch cache里有没有预训练权重
stdin, stdout, stderr = c.exec_command("find /root/.cache/torch -name '*.pth' 2>/dev/null | head -20")
print("\n=== 已有模型权重 ===")
print(stdout.read().decode())

# 检查datasets
stdin, stdout, stderr = c.exec_command("ls /autodl-pub/data/ 2>/dev/null | head -20")
print("=== 公开数据目录 ===")
print(stdout.read().decode())

# 测试：直接用CPU+预训练权重做分割推理 (跳过模型初始化)
test_script = r"""#!/root/miniconda3/bin/python
import torch, time, sys, os

LOG = "/root/autodl-tmp/seg_test.txt"
def log(msg):
    with open(LOG, "a") as f: f.write(msg + "\n")
    print(msg, flush=True)

log("START")

# 测试: 用已加载的resnet做backbone
try:
    import torchvision.models as models
    resnet = models.resnet50(pretrained=True)
    resnet.eval()
    x = torch.randn(1, 3, 224, 224)
    t0 = time.time()
    for _ in range(20):
        with torch.no_grad(): r = resnet(x)
    fps = 20 / (time.time() - t0)
    log("RESNET50_CPU_FPS=" + str(round(fps, 1)))
except Exception as e:
    log("RESNET50_FAIL=" + str(e)[:100])

# 测试: FCN (无预训练,直接推理随机输出)
try:
    from torchvision.models.segmentation.fcn import fcn_resnet50
    # 不加载权重,直接用随机初始化
    m = fcn_resnet50(pretrained=False)
    m.eval()
    x = torch.randn(1, 3, 256, 256)
    t0 = time.time()
    for _ in range(10):
        with torch.no_grad(): r = m(x)['out']
    fps = 10 / (time.time() - t0)
    log("FCN_NO_WEIGHT_CPU_FPS=" + str(round(fps, 1)))
except Exception as e:
    log("FCN_NO_WEIGHT_FAIL=" + str(e)[:100])

# 测试: LRASPP (轻量模型)
try:
    from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34
    m = lrasnet_lowresnet34(pretrained=False)
    m.eval()
    x = torch.randn(1, 3, 256, 256)
    t0 = time.time()
    for _ in range(10):
        with torch.no_grad(): r = m(x)['out']
    fps = 10 / (time.time() - t0)
    log("LRASPP_NO_WEIGHT_CPU_FPS=" + str(round(fps, 1)))
except Exception as e:
    log("LRASPP_NO_WEIGHT_FAIL=" + str(e)[:100])

log("DONE")
"""

with sftp.open(f"{REMOTE_DIR}/seg_test.py", "w") as f:
    f.write(test_script)

# 后台运行
channel = c.get_transport().open_session()
channel.exec_command(f"{PYTHON} {REMOTE_DIR}/seg_test.py 2>&1")

print("\nSeg test started, waiting 120s...")
time.sleep(120)

try:
    with sftp.open(f"{REMOTE_DIR}/seg_test.txt") as f:
        print("\n=== Segmentation Test Results ===")
        print(f.read().decode())
except FileNotFoundError:
    print("  (结果还没出来)")

sftp.close()
c.close()
