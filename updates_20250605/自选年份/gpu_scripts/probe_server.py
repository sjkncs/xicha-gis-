#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

cmds = [
    ("total disk", "df -h"),
    ("autodl-tmp size", "du -sh /root/autodl-tmp/ 2>&1"),
    ("streetview images count", "find /root/autodl-tmp/streetview_analysis/images/ -name '*.jpg' -type f 2>/dev/null | wc -l"),
    ("streetview top dirs", "find /root/autodl-tmp/streetview_analysis/images/ -maxdepth 2 -type d 2>/dev/null"),
    ("cityscapes contents", "ls /root/autodl-pub/cityscapes/ 2>&1"),
    ("ADE contents", "ls /root/autodl-pub/ADEChallengeData2016/ 2>&1"),
    ("model cache locations", "find /root -name '*.bin' -o -name '*.safetensors' -o -name 'config.json' 2>/dev/null | head -20"),
    ("pip list transformers", "pip list 2>/dev/null | grep -i -E 'torch|transformers|numpy|pillow|cv2'"),
    ("venv pip list", "source /root/venv/bin/activate && pip list 2>/dev/null | grep -i -E 'torch|transformers|numpy|pillow|cv2'"),
    ("venv packages", "source /root/venv/bin/activate && pip list 2>/dev/null | head -20"),
]
for name, cmd in cmds:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    print(f"=== {name} ===")
    print(out[:800] if out else err[:300])
    print()

client.close()
