#!/usr/bin/env python3
"""全面扫描GPU全量数据，统计、分类、建立下载清单"""
import paramiko, os, json

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, banner_timeout=30)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read()
    err = stderr.read()
    return out, err

# 1. 扫描所有街景图片，按类别统计
print("=== 按类别统计 ===")
out, err = run('find /root/autodl-tmp/streetview_images/ -name "*.jpg" | wc -l')
print(f"总 JPG 图片: {out.decode().strip()}")

# 按子目录统计
out, err = run('for d in /root/autodl-tmp/streetview_images/*/; do echo "$(basename "$d"): $(find "$d" -name "*.jpg" | wc -l)"; done')
print(out.decode())

# 2. 列出所有图片的路径（用于构建下载清单）
out, err = run('find /root/autodl-tmp/streetview_images/ -name "*.jpg" 2>/dev/null | sort')
all_files = [f.strip() for f in out.decode().strip().split("\n") if f.strip()]
print(f"\n找到 {len(all_files)} 个文件")

# 3. 建立本地映射目录
LOCAL_ROOT = r"e:\xicha gis 智能定位\自选年份\raw_streetview"
os.makedirs(LOCAL_ROOT, exist_ok=True)

# 4. 下载脚本生成（处理中文路径）
download_script = []
for remote_path in all_files:
    remote_path = remote_path.strip()
    if not remote_path:
        continue
    # 保持原始目录结构
    rel = remote_path.replace("/root/autodl-tmp/streetview_images/", "")
    local_path = os.path.join(LOCAL_ROOT, rel)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    download_script.append({"remote": remote_path, "local": local_path})

print(f"\n下载清单: {len(download_script)} 个文件")

# 5. 估算总大小
out, err = run('find /root/autodl-tmp/streetview_images/ -name "*.jpg" -exec ls -l {} \\; | awk "{sum+=$5} END {print sum}"')
total_bytes = int(out.decode().strip() or 0)
print(f"估算总大小: {total_bytes/1024/1024:.1f} MB")

# 保存清单
list_path = os.path.join(os.path.dirname(LOCAL_ROOT), "download_list.json")
with open(list_path, "w", encoding="utf-8") as f:
    json.dump(download_script, f, ensure_ascii=False, indent=1)
print(f"清单已保存: {list_path}")

ssh.close()
print("\nDone")
