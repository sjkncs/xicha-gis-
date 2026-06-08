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

print("=== Upgrade torchvision + torchaudio ===")

# Start upgrade in background
transport = client.get_transport()
session = transport.open_session()
session.exec_command('cd /root/gis_project && source ~/venv/bin/activate && pip install torchvision torchaudio -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1')
time.sleep(5)

# Read initial output
out = b''
start = time.time()
while time.time() - start < 300:
    if session.recv_ready():
        out += session.recv(4096)
    if session.exit_status_ready():
        break
    time.sleep(2)

result = out.decode()
print(result[-3000:] if len(result) > 3000 else result)

print("\n=== Verify ===")
print(q(client, "cd /root/gis_project && source ~/venv/bin/activate && python -c 'import torch, torchvision; print(torch.__version__, torchvision.__version__)'"))

# Test import
print("\n=== Test import ===")
transport2 = client.get_transport()
session2 = transport2.open_session()
session2.exec_command('cd /root/gis_project && source ~/venv/bin/activate && python -c "from transformers import AutoModel; print(\"OK\")" 2>&1')
time.sleep(10)
out2 = b''
start = time.time()
while time.time() - start < 30:
    if session2.recv_ready():
        out2 += session2.recv(4096)
    if session2.exit_status_ready():
        break
    time.sleep(1)
print(out2.decode()[:1000])

client.close()
