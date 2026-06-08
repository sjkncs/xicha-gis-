import paramiko, time, sys

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

print("=== Latest log (last 20 lines) ===")
print(q(client, "tail -20 /root/gis_project/logs/seg_inference_offline.log"))

print("\n=== How many processed? ===")
print(q(client, "grep ' OK ' /root/gis_project/logs/seg_inference_offline.log | wc -l"))

print("\n=== CSV file ===")
csv = q(client, "cat /root/gis_project/outputs/segmentation/segmentation_metrics.csv 2>/dev/null | head -5 || echo 'No CSV yet'")
print(csv[:500])

print("\n=== Viz dir ===")
print(q(client, "ls /root/gis_project/outputs/segmentation/viz/ 2>/dev/null | wc -l || echo 'empty'"))

print("\n=== Process alive? ===")
alive = q(client, "ps aux | grep seg_inference_offline | grep -v grep | wc -l")
print(alive)
if int(alive.strip() or 0) == 0:
    print("PROCESS DIED - check log tail above for errors")
    print("\n=== Full log tail ===")
    print(q(client, "tail -50 /root/gis_project/logs/seg_inference_offline.log"))

client.close()
