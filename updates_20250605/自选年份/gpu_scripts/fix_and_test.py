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

print("torch/torchvision versions:")
print(q(client, "cd /root/gis_project && source ~/venv/bin/activate && python -c 'import torch, torchvision; print(\"torch:\", torch.__version__, \"| torchvision:\", torchvision.__version__)'"))

print("\nCUDA available:")
print(q(client, "cd /root/gis_project && source ~/venv/bin/activate && python -c 'import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\")'"))

print("\nReinstalling torch 2.5.1 if needed...")
transport = client.get_transport()
session = transport.open_session()
cmd = 'cd /root/gis_project && source ~/venv/bin/activate && pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121 -q 2>&1'
session.exec_command(cmd)
time.sleep(10)
out = b''
while True:
    if session.recv_ready():
        out += session.recv(4096)
    if session.exit_status_ready():
        break
    time.sleep(2)
print("Install output:", out.decode()[:500])

print("\nFinal versions:")
print(q(client, "cd /root/gis_project && source ~/venv/bin/activate && python -c 'import torch, torchvision; print(torch.__version__, torchvision.__version__)'"))

print("\nTest model load:")
transport2 = client.get_transport()
session2 = transport2.open_session()
session2.exec_command('cd /root/gis_project && source ~/venv/bin/activate && python -c "from transformers import SegformerForSemanticSegmentation; print(\'model class OK\')" 2>&1')
time.sleep(15)
out2 = b''
while time.time() < time.time() + 60:
    if session2.recv_ready():
        out2 += session2.recv(4096)
    if session2.exit_status_ready():
        break
    time.sleep(1)
print(out2.decode()[:2000])

client.close()
