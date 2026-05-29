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

print("=== Latest log lines ===")
print(q(client, "tail -15 /root/gis_project/logs/seg_inference_offline.log"))

print("\n=== Checkpoint ===")
print(q(client, "ls -la /root/gis_project/outputs/segmentation/"))

print("\n=== CSV results ===")
print(q(client, "cat /root/gis_project/outputs/segmentation/segmentation_metrics.csv 2>/dev/null | head -15 || echo 'No CSV yet'"))

print("\n=== Process ===")
print(q(client, "ps aux | grep seg_inference | grep -v grep | awk '{print $11, $12, $13}'"))

print("\n=== CPU ===")
print(q(client, "ps aux | grep seg_inference | grep -v grep | awk '{print $3\"% CPU\", $4\"% MEM\"}'"))

client.close()
