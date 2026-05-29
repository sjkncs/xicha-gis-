# -*- coding: utf-8 -*-
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    'connect.bjb1.seetacloud.com', port=10244,
    username='root', password='roBbKv+ed3Vm',
    timeout=15, allow_agent=False, look_for_keys=False
)

commands = [
    ('Python可用命令', 'which python || which python3.10 || which python3.11 || which conda'),
    ('conda版本', 'conda --version 2>/dev/null || echo no conda'),
    ('pip版本', 'pip --version 2>/dev/null || pip3 --version 2>/dev/null || echo no pip'),
    ('系统Python', 'ls /usr/bin/python* 2>/dev/null; ls /usr/local/bin/python* 2>/dev/null'),
    ('系统信息', 'cat /etc/os-release 2>/dev/null | head -5'),
    ('nvidia驱动详情', 'nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv,noheader'),
    ('CUDA版本', 'nvcc --version 2>/dev/null || echo no nvcc'),
    ('已装包', 'pip3 list 2>/dev/null | head -40 || pip list 2>/dev/null | head -40'),
]

for name, cmd in commands:
    print(f"\n=== {name} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out if out else err)

client.close()
