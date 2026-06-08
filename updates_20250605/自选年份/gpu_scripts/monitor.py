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

print("=== Progress ===")
count = q(client, "grep ' OK ' /root/gis_project/logs/seg_inference_offline.log | wc -l")
print(f"Processed: {count.strip()}/294")

print("\n=== Last 3 lines ===")
print(q(client, "tail -3 /root/gis_project/logs/seg_inference_offline.log"))

print("\n=== Process alive ===")
alive = q(client, "ps aux | grep seg_inference_offline | grep -v grep | wc -l")
print(f"Count: {alive.strip()}")

if int(alive.strip() or 0) == 0:
    print("\n*** PROCESS COMPLETED ***")
    print("\n=== Final log ===")
    print(q(client, "tail -10 /root/gis_project/logs/seg_inference_offline.log"))
    print("\n=== Results ===")
    print(q(client, "wc -l /root/gis_project/outputs/segmentation/seg_results.csv"))
    print(q(client, "ls /root/gis_project/outputs/segmentation/viz/ | wc -l"))
else:
    print("Still running...")

client.close()
