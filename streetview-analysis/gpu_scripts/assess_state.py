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

print("1. Current versions:")
print(q(client, "cd /root/gis_project && source ~/venv/bin/activate && python -c 'import torch, torchvision; print(torch.__version__, torchvision.__version__)'"))

print("\n2. Test transformers (current state):")
transport2 = client.get_transport()
session2 = transport2.open_session()
session2.exec_command('cd /root/gis_project && source ~/venv/bin/activate && python -c "from transformers import AutoModelForSemanticSegmentation; print(\'OK\')" 2>&1')
time.sleep(20)
out2 = b''
start = time.time()
while time.time() - start < 60:
    if session2.recv_ready():
        out2 += session2.recv(4096)
    if session2.exit_status_ready():
        break
    time.sleep(1)
print(out2.decode()[:3000])

client.close()
