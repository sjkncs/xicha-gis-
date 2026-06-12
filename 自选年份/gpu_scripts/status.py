import paramiko, time

HOST = 'connect.bjb1.seetacloud.com'
PORT = 37625
USER = 'root'
PWD = 'roBbKv+ed3Vm'

def q(ssh, cmd):
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

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)

print("=== Status Check ===")
print(q(client, "tail -30 /root/gis_project/logs/seg_inference_offline.log"))
print("\n=== GPU ===")
print(q(client, "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv"))
print("\n=== Process ===")
print(q(client, "ps aux | grep seg_inference | grep -v grep | head -2"))
print("\n=== Processed files ===")
print(q(client, "ls /root/gis_project/outputs/segmentation/viz/ | wc -l"))
print(q(client, "cat /root/gis_project/outputs/segmentation/checkpoint.json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f\"Done: {len(d[\\\"done\\\"])}/{294}\")' 2>/dev/null || echo 'checkpoint not found'"))

client.close()
