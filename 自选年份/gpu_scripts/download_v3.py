import paramiko, sys, os
sys.stdout.reconfigure(encoding='utf-8')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('connect.bjb1.seetacloud.com', port=50405, username='root', password='roBbKv+ed3Vm', timeout=30)
sftp = client.open_sftp()

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace').strip()

# Download JSON
local_results = r'e:\xicha gis 智能定位\自选年份\gpu_scripts\results'
os.makedirs(local_results, exist_ok=True)
sftp.get('/root/autodl-tmp/streetview_sim_v2/sim_results_v2.json',
          os.path.join(local_results, 'sim_results_v2.json'))
print("JSON downloaded")

# Download all annotated images
samples_dir = os.path.join(local_results, 'sim_v2_samples')
os.makedirs(samples_dir, exist_ok=True)

files_out = run("ls /root/autodl-tmp/streetview_sim_v2/samples/")
file_list = files_out.strip().split() if files_out.strip() else []
print(f"Files on server: {len(file_list)}")

for i, fn in enumerate(file_list):
    local = os.path.join(samples_dir, fn)
    try:
        sftp.get('/root/autodl-tmp/streetview_sim_v2/samples/' + fn, local)
    except Exception as e:
        print(f"FAIL {fn}: {e}")
    if (i + 1) % 10 == 0:
        print(f"  {i+1}/{len(file_list)}...")

print(f"\nTotal downloaded: {len(os.listdir(samples_dir))} images")

# Also download the log
sftp.get('/root/autodl-tmp/sim_v2.log',
          os.path.join(local_results, 'sim_v2.log'))
print("Log downloaded")

sftp.close()
client.close()
print("ALL DONE")
