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

def run_bg(ssh, cmd, wait=5):
    transport = ssh.get_transport()
    session = transport.open_session()
    session.exec_command(cmd)
    time.sleep(wait)
    return session

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)

# Step 1: Restore torch 2.5.1
print("=== Step 1: Restore torch 2.5.1 ===")
print(q(client, "cd /root/gis_project && source ~/venv/bin/activate && pip show torch | grep Version"))

transport = client.get_transport()
session = transport.open_session()
session.exec_command('cd /root/gis_project && source ~/venv/bin/activate && pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121 2>&1')

out = b''
start = time.time()
while time.time() - start < 300:
    if session.recv_ready():
        out += session.recv(4096)
    if session.exit_status_ready():
        break
    time.sleep(3)
    print(f"  {int(time.time()-start)}s...", end="\r", flush=True)

result = out.decode()
print("\n" + result[-3000:] if len(result) > 3000 else result)

print("\nVersion:", q(client, "cd /root/gis_project && source ~/venv/bin/activate && python -c 'import torch, torchvision; print(torch.__version__, torchvision.__version__)'"))

# Step 2: Patch image_utils.py to avoid torchvision import
print("\n=== Step 2: Patch transformers/image_utils.py ===")
patch1 = 'sed -i \'s/from torchvision.io import ImageReadMode, decode_image/# torchvision import removed/g\' /root/venv/lib/python3.10/site-packages/transformers/image_utils.py'
result = q(client, patch1)
# Verify
check = q(client, "grep -n 'torchvision import removed' /root/venv/lib/python3.10/site-packages/transformers/image_utils.py")
print("Patch result:", check[:300])

# Step 3: Also patch image_utils.py for is_vision_available
print("\n=== Step 3: Check is_vision_available ===")
check2 = q(client, "grep -n 'is_vision_available' /root/venv/lib/python3.10/site-packages/transformers/image_utils.py | head -5")
print(check2[:500])

# Step 4: Test import
print("\n=== Step 4: Test import ===")
transport2 = client.get_transport()
session2 = transport2.open_session()
session2.exec_command('cd /root/gis_project && source ~/venv/bin/activate && python -c "from transformers import AutoModelForSemanticSegmentation; print(\'SUCCESS\')" 2>&1')
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
