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

# Step 1: Patch transformers so it doesn't try to import torchvision
print("=== Step 1: Patch image_utils.py ===")
patch = '''sed -i 's/from torchvision.io import ImageReadMode, decode_image/# torchvision disabled/g' /root/venv/lib/python3.10/site-packages/transformers/image_utils.py'''
q(client, patch)
result = q(client, "grep -n 'torchvision disabled' /root/venv/lib/python3.10/site-packages/transformers/image_utils.py")
print("Patch:", result[:200])

# Step 2: Also patch torchvision/__init__.py to make it a no-op if loaded
print("\n=== Step 2: Patch torchvision __init__ ===")
patch2 = '''sed -i 's/from torchvision import/_disable_torchvision = True\\n# torchvision/' /root/venv/lib/python3.10/site-packages/torchvision/__init__.py'''
q(client, patch2)
result2 = q(client, "grep -n 'disabled' /root/venv/lib/python3.10/site-packages/torchvision/__init__.py | head -3")
print("Patch2:", result2[:200])

# Step 3: Now test import
print("\n=== Step 3: Test import ===")
transport2 = client.get_transport()
session2 = transport2.open_session()
session2.exec_command('cd /root/gis_project && source ~/venv/bin/activate && python -c "from transformers import AutoModelForSemanticSegmentation; print(\'transformers OK\')" 2>&1')
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
