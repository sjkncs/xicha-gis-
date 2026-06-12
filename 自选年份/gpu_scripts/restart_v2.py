import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('connect.bjb1.seetacloud.com', port=50405, username='root', password='roBbKv+ed3Vm', timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace').strip()

# Check if script was uploaded
print("Script uploaded?", run("ls -la /root/autodl-tmp/sim_run_v2.py"))
print("\nPython3 verify:", run("which python3"))

# Upload fresh
sftp = client.open_sftp()
sftp.put(r'e:\xicha gis 智能定位\自选年份\gpu_scripts\sim_run_v2.py', '/root/autodl-tmp/sim_run_v2.py')
print("Uploaded OK")
sftp.close()

# Start
run("cd /root/autodl-tmp && nohup python3 sim_run_v2.py > sim_v2.log 2>&1 &")
print("Started at:", run("date"))

import time
time.sleep(15)

print("\n=== Initial output ===")
print(run("tail -15 /root/autodl-tmp/sim_v2.log"))

client.close()
