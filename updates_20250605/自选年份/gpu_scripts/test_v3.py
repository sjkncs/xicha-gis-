import paramiko, time

HOST = 'connect.bjb1.seetacloud.com'
PORT = 37625
USER = 'root'
PWD = 'roBbKv+ed3Vm'

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

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)

# Run inference directly (not nohup) so we can see output
cmd = 'cd /root/gis_project && source ~/venv/bin/activate && python /root/gis_project/gpu_scripts/seg_inference_v3.py 2>&1 | head -60'
transport = client.get_transport()
session = transport.open_session()
session.exec_command(cmd)

# Read output for up to 60 seconds
start = time.time()
out = b''
while time.time() - start < 60:
    if session.recv_ready():
        out += session.recv(65536)
    if session.exit_status_ready():
        break
    time.sleep(1)

print(out.decode())

client.close()
