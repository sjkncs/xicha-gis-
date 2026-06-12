#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

# Check data directory
print("=== Data directory check ===")
out, _ = ssh("ls /root/autodl-tmp/streetview_analysis/ 2>/dev/null")
print("streetview_analysis:", out[:200])

out, _ = ssh("ls /root/autodl-tmp/streetview_analysis/images/ 2>/dev/null | head -5")
print("images/", out[:200])

out, _ = ssh("find /root/autodl-tmp/streetview_analysis -name '*.jpg' 2>/dev/null | head -5")
print("find jpg:", out[:200])

out, _ = ssh("find /root/autodl-tmp/streetview_analysis -type f 2>/dev/null | head -10")
print("all files:", out[:400])

# Check autodl-pub
print("\n=== autodl-pub check ===")
out, _ = ssh("ls /autodl-pub/data/ 2>/dev/null | head -10")
print("autodl-pub/data:", out[:300])

out, _ = ssh("find /autodl-pub/data -name '*.jpg' 2>/dev/null | head -5")
print("find jpg:", out[:200])

# Check root gis_project
print("\n=== gis_project check ===")
out, _ = ssh("ls /root/gis_project/ 2>/dev/null")
print("gis_project:", out[:200])

# Check all jpg files on the system
print("\n=== All JPG files ===")
out, _ = ssh("find /root -name '*.jpg' 2>/dev/null | head -10")
print("jpg in /root:", out[:400])

out, _ = ssh("find /root -name '*.JPG' 2>/dev/null | head -10")
print("JPG in /root:", out[:400])

client.close()
