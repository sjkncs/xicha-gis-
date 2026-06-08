#!/usr/bin/env python3
import paramiko, time
HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

c = ssh()

# 先测试简单命令stdout capture
print("Test 1: simple echo")
stdin, stdout, stderr = c.exec_command("echo hello world", timeout=10)
out = stdout.read()
err = stderr.read()
print(f"stdout: {repr(out)}")
print(f"stderr: {repr(err[:200])}")

# 测试Python脚本
print("\nTest 2: Python script")
script = '/root/miniconda3/bin/python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"'
stdin, stdout, stderr = c.exec_command(script, timeout=30)
out = stdout.read()
err = stderr.read()
print(f"stdout: {repr(out[:200])}")
print(f"stderr: {repr(err[:200])}")

# 测试复杂脚本
print("\nTest 3: Complex GPU script via file")
sftp = c.open_sftp()
sftp.open("/root/autodl-tmp/test_script.py", "w").write(
    "import torch; print('GPU:', torch.cuda.get_device_name(0))\n"
    "import time; from torchvision.models.segmentation.fcn import fcn_resnet50; import torch.nn as nn\n"
    "m = fcn_resnet50(); m.classifier[4] = nn.Conv2d(512, 21, bias=True); m = m.cuda(); m.eval()\n"
    "x = torch.randn(1, 3, 512, 512).cuda()\n"
    "with torch.no_grad():\n"
    "    for _ in range(5): r = m(x)\n"
    "torch.cuda.synchronize()\n"
    "t0 = time.time()\n"
    "with torch.no_grad():\n"
    "    for _ in range(50): r = m(x)\n"
    "torch.cuda.synchronize()\n"
    "print('FCN FPS:', 50 / (time.time() - t0))\n"
    "print('DONE')\n"
)
sftp.close()

stdin, stdout, stderr = c.exec_command("/root/miniconda3/bin/python /root/autodl-tmp/test_script.py", timeout=300)
out = stdout.read()
err = stderr.read()
print(f"stdout ({len(out)} bytes): {out[:500]}")
print(f"stderr ({len(err)} bytes): {err[:200]}")

c.close()
