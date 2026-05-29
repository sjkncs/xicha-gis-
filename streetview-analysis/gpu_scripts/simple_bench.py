#!/usr/bin/env python3
import paramiko, time
HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read(), stderr.read()

c = ssh()
PYTHON = "/root/miniconda3/bin/python"

# 测试1: GPU tensor
print("1. GPU test:")
out, err = run(c, f"{PYTHON} -c \"import torch; x=torch.randn(100,100).cuda(); print('GPU:', torch.cuda.get_device_name(0), 'OK')\"")
print(f"  out: {out.strip()[:100]}")
print(f"  err: {err.strip()[:200]}")

# 测试2: CPU 分割模型速度
print("\n2. CPU FCN speed (50 imgs):")
sftp = c.open_sftp()
sftp.open("/root/autodl-tmp/bench_cpu.py", "w").write(
    "import torch, time\n"
    "from torchvision.models.segmentation.fcn import fcn_resnet50\n"
    "m = fcn_resnet50()\n"
    "m.eval()\n"
    "x = torch.randn(1, 3, 512, 512)\n"
    "for _ in range(5): m(x)\n"
    "t0 = time.time()\n"
    "for _ in range(50): m(x)\n"
    "print('FCN_CPU_FPS:', 50 / (time.time() - t0))\n"
)
sftp.close()

stdin, stdout, stderr = c.exec_command(f"{PYTHON} /root/autodl-tmp/bench_cpu.py", timeout=120)
out, err = run(c, f"{PYTHON} /root/autodl-tmp/bench_cpu.py")
print(f"  out: {out.strip()[:100]}")
print(f"  err: {err.strip()[:200]}")

# 测试3: CPU LR-ASPP速度 (更快)
print("\n3. CPU LR-ASPP speed (50 imgs):")
sftp.open("/root/autodl-tmp/bench_lraspp.py", "w").write(
    "import torch, time\n"
    "from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34\n"
    "m = lrasnet_lowresnet34()\n"
    "m.eval()\n"
    "x = torch.randn(1, 3, 512, 512)\n"
    "for _ in range(5): m(x)\n"
    "t0 = time.time()\n"
    "for _ in range(50): m(x)\n"
    "print('LRASPP_CPU_FPS:', 50 / (time.time() - t0))\n"
)
sftp.close()

stdin, stdout, stderr = c.exec_command(f"{PYTHON} /root/autodl-tmp/bench_lraspp.py", timeout=120)
out, err = run(c, f"{PYTHON} /root/autodl-tmp/bench_lraspp.py")
print(f"  out: {out.strip()[:100]}")
print(f"  err: {err.strip()[:200]}")

# 测试4: CPU DeepLabV3
print("\n4. CPU DeepLabV3 speed (50 imgs):")
sftp.open("/root/autodl-tmp/bench_dlv3.py", "w").write(
    "import torch, time\n"
    "from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50\n"
    "m = deeplabv3_resnet50()\n"
    "m.eval()\n"
    "x = torch.randn(1, 3, 512, 512)\n"
    "for _ in range(5): m(x)\n"
    "t0 = time.time()\n"
    "for _ in range(50): m(x)\n"
    "print('DEEPLABV3_CPU_FPS:', 50 / (time.time() - t0))\n"
)
sftp.close()

stdin, stdout, stderr = c.exec_command(f"{PYTHON} /root/autodl-tmp/bench_dlv3.py", timeout=120)
out, err = run(c, f"{PYTHON} /root/autodl-tmp/bench_dlv3.py")
print(f"  out: {out.strip()[:100]}")
print(f"  err: {err.strip()[:200]}")

# 测试5: GPU FCN (可能不work)
print("\n5. GPU FCN speed:")
sftp.open("/root/autodl-tmp/bench_gpu_fcn.py", "w").write(
    "import torch, time\n"
    "from torchvision.models.segmentation.fcn import fcn_resnet50\n"
    "m = fcn_resnet50().cuda()\n"
    "m.eval()\n"
    "x = torch.randn(1, 3, 512, 512).cuda()\n"
    "for _ in range(5):\n"
    "    with torch.no_grad(): r = m(x)\n"
    "torch.cuda.synchronize()\n"
    "t0 = time.time()\n"
    "for _ in range(50):\n"
    "    with torch.no_grad(): r = m(x)\n"
    "torch.cuda.synchronize()\n"
    "print('FCN_GPU_FPS:', 50 / (time.time() - t0))\n"
)
sftp.close()

stdin, stdout, stderr = c.exec_command(f"{PYTHON} /root/autodl-tmp/bench_gpu_fcn.py 2>&1", timeout=120)
out, err = run(c, f"{PYTHON} /root/autodl-tmp/bench_gpu_fcn.py 2>&1")
print(f"  out: {out.strip()[:100]}")
print(f"  err: {err.strip()[:300]}")

# 测试6: 检查transformers可用
print("\n6. Transformers import:")
stdin, stdout, stderr = c.exec_command(f"{PYTHON} -c \"import transformers; print(transformers.__version__)\"")
out, err = run(c, f"{PYTHON} -c \"import transformers; print(transformers.__version__)\"")
print(f"  out: {out.strip()[:100]}")

# 测试7: skimage
print("\n7. skimage:")
stdin, stdout, stderr = c.exec_command(f"{PYTHON} -c \"import skimage; print(skimage.__version__)\"")
out, err = run(c, f"{PYTHON} -c \"import skimage; print(skimage.__version__)\"")
print(f"  out: {out.strip()[:100]}")

sftp.close()
c.close()
print("\nDone!")
