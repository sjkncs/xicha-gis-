import random
from pathlib import Path
import paramiko

HOST = 'connect.bjb1.seetacloud.com'
PORT = 37625
USER = 'root'
PWD = 'roBbKv+ed3Vm'

REMOTE_VIZ_DIR = '/root/gis_project/outputs/segmentation/viz'
LOCAL_DIR = Path(r"E:\xicha gis 智能定位\自选年份\gpu_scripts\results\viz_samples")
LOCAL_DIR.mkdir(parents=True, exist_ok=True)

N = 6

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)

stdin, stdout, stderr = client.exec_command(f"ls -1 {REMOTE_VIZ_DIR}/*.png 2>/dev/null || true")
files = [line.strip() for line in stdout.read().decode(errors='replace').splitlines() if line.strip()]

if not files:
    print('No viz png files found on remote yet.')
    client.close()
    raise SystemExit(0)

pick = files if len(files) <= N else random.sample(files, N)
print(f"Found {len(files)} viz pngs, downloading {len(pick)}...")

sftp = client.open_sftp()
for rp in pick:
    name = rp.split('/')[-1]
    lp = LOCAL_DIR / name
    sftp.get(rp, str(lp))
    print(f"  downloaded: {name}")

# Also download overlay images if present
stdin, stdout, stderr = client.exec_command(f"ls -1 {REMOTE_VIZ_DIR}/*__overlay.png 2>/dev/null || true")
overlays = [line.strip() for line in stdout.read().decode(errors='replace').splitlines() if line.strip()]

if overlays:
    # Prefer overlays matching the sampled basenames
    sampled_bases = {Path(p.split('/')[-1]).stem for p in pick}
    matching = [p for p in overlays if Path(p.split('/')[-1]).stem.replace('__overlay', '') in sampled_bases]
    extra = matching
    if not extra:
        extra = overlays if len(overlays) <= N else random.sample(overlays, N)

    print(f"\nFound {len(overlays)} overlay pngs, downloading {len(extra)}...")
    for rp in extra:
        name = rp.split('/')[-1]
        lp = LOCAL_DIR / name
        sftp.get(rp, str(lp))
        print(f"  downloaded: {name}")
else:
    print("\nNo overlay pngs found yet (need to re-generate viz after code update).")

sftp.close()
client.close()

print(f"\nSaved samples to: {LOCAL_DIR}")
