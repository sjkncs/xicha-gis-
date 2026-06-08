#!/usr/bin/env python3
"""快速诊断远端：文件/日志/进程/图片数"""
import paramiko

HOST = "connect.bjb1.seetacloud.com"
PORT = 12996
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"
OUT_DIR = REMOTE_DIR + "/output"


def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c


c = ssh()

print("=== 1) 进程 ===")
stdin, stdout, stderr = c.exec_command("pgrep -fa 'analyze.py' || true", timeout=15)
print(stdout.read().decode("utf-8", errors="replace").strip() or "(none)")

print("\n=== 2) 关键文件是否存在 ===")
checks = [
    ("analyze.py", f"test -f {REMOTE_DIR}/analyze.py && echo OK || echo MISSING"),
    ("output dir", f"test -d {OUT_DIR} && echo OK || echo MISSING"),
    ("analyze.log", f"test -f {OUT_DIR}/analyze.log && echo OK || echo MISSING"),
    ("results.json", f"test -f {OUT_DIR}/results.json && echo OK || echo MISSING"),
    ("street_summary.json", f"test -f {OUT_DIR}/street_summary.json && echo OK || echo MISSING"),
    ("summary.png", f"test -f {OUT_DIR}/summary.png && echo OK || echo MISSING"),
    ("heatmaps dir", f"test -d {OUT_DIR}/heatmaps && echo OK || echo MISSING"),
]
for name, cmd in checks:
    stdin, stdout, stderr = c.exec_command(cmd, timeout=15)
    print(f"{name:18s} {stdout.read().decode().strip()}")

print("\n=== 3) 图片数量 ===")
stdin, stdout, stderr = c.exec_command(
    f"(find {REMOTE_DIR}/images -type f \\( -iname '*.jpg' -o -iname '*.png' \\) 2>/dev/null | wc -l) || echo 0",
    timeout=30,
)
print("remote images:", stdout.read().decode().strip())

print("\n=== 4) analyze.log 尾部 ===")
stdin, stdout, stderr = c.exec_command(f"tail -n 40 {OUT_DIR}/analyze.log 2>/dev/null || true", timeout=30)
log_tail = stdout.read().decode("utf-8", errors="replace").strip()
print(log_tail or "(no log)")

print("\n=== 5) 如果结果存在：统计条数 ===")
cmd = (
    f"test -f {OUT_DIR}/results.json && "
    f"python3 - <<'PY'\n"
    f"import json\n"
    f"p='{OUT_DIR}/results.json'\n"
    f"print(len(json.load(open(p,'r',encoding='utf-8'))))\n"
    f"PY || true"
)
stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
print("results count:", stdout.read().decode().strip() or "(n/a)")

c.close()
