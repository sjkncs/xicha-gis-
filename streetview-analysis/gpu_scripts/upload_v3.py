import paramiko, time, sys
from pathlib import Path

HOST = 'connect.bjb1.seetacloud.com'
PORT = 37625
USER = 'root'
PWD = 'roBbKv+ed3Vm'
SCRIPT = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v3.py"
REMOTE = "/root/gis_project/gpu_scripts/seg_inference_v3.py"

def q(ssh, cmd, timeout=30):
    transport = ssh.get_transport()
    session = transport.open_session()
    session.exec_command(cmd)
    out = b''
    while True:
        if session.recv_ready():
            out += session.recv(4096)
        if session.exit_status_ready():
            break
        time.sleep(0.3)
    return out.decode().strip()

def nohup(ssh, cmd):
    transport = ssh.get_transport()
    session = transport.open_session()
    session.exec_command(f'nohup {cmd} > /tmp/seg_v3.log 2>&1 &')
    time.sleep(3)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)

print("=== Upload script ===")
sftp = client.open_sftp()
sftp.put(SCRIPT, REMOTE)
sftp.close()
print("Uploaded!")

print("\n=== Kill old processes ===")
q(client, "pkill -f seg_inference 2>/dev/null; rm -f /root/gis_project/outputs/segmentation/checkpoint.json; rm -f /root/gis_project/outputs/segmentation/segmentation_metrics.csv")

print("\n=== Start inference v3 ===")
nohup(client, f'cd /root/gis_project && source ~/venv/bin/activate && python {REMOTE}')

print("\n=== Wait 30s ===")
time.sleep(30)

print("\n=== Log ===")
print(q(client, "tail -40 /tmp/seg_v3.log"))

print("\n=== GPU ===")
print(q(client, "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv"))

print("\n=== Process ===")
print(q(client, "ps aux | grep seg_inference | grep -v grep"))

client.close()
