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

print("=== Inference Progress ===")
count = q(client, "grep ' OK ' /root/gis_project/logs/seg_inference_offline.log | wc -l")
print(f"Processed: {count.strip()} images")
print("\n=== Last 5 lines ===")
print(q(client, "tail -5 /root/gis_project/logs/seg_inference_offline.log"))
print("\n=== Checkpoint files ===")
print(q(client, "ls -la /root/gis_project/outputs/segmentation/"))
print("\n=== Viz files ===")
viz_count = q(client, "ls /root/gis_project/outputs/segmentation/viz/ 2>/dev/null | wc -l")
print(f"Viz count: {viz_count.strip()}")
print("\n=== Process alive ===")
alive = q(client, "ps aux | grep seg_inference_offline | grep -v grep | wc -l")
print(f"Processes: {alive.strip()}")
if int(alive.strip() or 0) == 0:
    print("ERROR: Process died!")
    print(q(client, "tail -30 /root/gis_project/logs/seg_inference_offline.log"))

client.close()
