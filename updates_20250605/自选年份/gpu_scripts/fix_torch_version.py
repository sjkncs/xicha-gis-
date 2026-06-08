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

print("=== Install torch 2.6.0 + CUDA 12.x ===")
print(q(client, "cd /root/gis_project && source ~/venv/bin/activate && pip show torch | grep Version"))

# Start install in background
transport = client.get_transport()
session = transport.open_session()
install_cmd = 'cd /root/gis_project && source ~/venv/bin/activate && pip install torch==2.6.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 2>&1'
session.exec_command(install_cmd)

print("Waiting for install (up to 10 min)...")
out = b''
start = time.time()
while time.time() - start < 600:
    if session.recv_ready():
        out += session.recv(4096)
    if session.exit_status_ready():
        break
    time.sleep(3)
    # Print progress dots
    elapsed = int(time.time() - start)
    print(f"  {elapsed}s...", end="\r", flush=True)

result = out.decode()
print("\n" + "="*50)
print(result[-5000:] if len(result) > 5000 else result)

print("\n=== Version check ===")
print(q(client, "cd /root/gis_project && source ~/venv/bin/activate && python -c 'import torch, torchvision; print(torch.__version__, torchvision.__version__)'"))

print("\n=== Test transformers import ===")
transport2 = client.get_transport()
session2 = transport2.open_session()
session2.exec_command('cd /root/gis_project && source ~/venv/bin/activate && python -c "from transformers import AutoModel; print(\"transformers OK\")" 2>&1')
time.sleep(15)
out2 = b''
start2 = time.time()
while time.time() - start2 < 60:
    if session2.recv_ready():
        out2 += session2.recv(4096)
    if session2.exit_status_ready():
        break
    time.sleep(1)
print(out2.decode()[:2000])

client.close()
