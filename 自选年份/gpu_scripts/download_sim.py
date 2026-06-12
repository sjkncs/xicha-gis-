import paramiko, sys, os
sys.stdout.reconfigure(encoding='utf-8')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('connect.bjb1.seetacloud.com', port=50405, username='root', password='roBbKv+ed3Vm', timeout=30)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace').strip()

sftp = client.open_sftp()

# Download JSON
local_json = r'e:\xicha gis 智能定位\自选年份\gpu_scripts\results\sim_results_cloud.json'
sftp.get('/root/autodl-tmp/streetview_sim/sim_results.json', local_json)
print("JSON downloaded:", os.path.getsize(local_json), "bytes")

# Download all annotated images
samples_dir = r'e:\xicha gis 智能定位\自选年份\gpu_scripts\results\sim_samples'
os.makedirs(samples_dir, exist_ok=True)

files_out = run("ls /root/autodl-tmp/streetview_sim/samples/")
file_list = files_out.strip().split()
print(f"Files on server: {len(file_list)}")

for i, fn in enumerate(file_list):
    local_path = os.path.join(samples_dir, fn)
    try:
        sftp.get('/root/autodl-tmp/streetview_sim/samples/' + fn, local_path)
        print(f"[{i+1}/{len(file_list)}] {fn}")
    except Exception as e:
        print(f"FAIL {fn}: {e}")

print(f"\nDownloaded to {samples_dir}")
print("Files count:", len(os.listdir(samples_dir)))

sftp.close()
client.close()
print("Done!")
