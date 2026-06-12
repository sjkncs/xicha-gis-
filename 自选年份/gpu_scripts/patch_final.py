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

# Step 1: Check current state
print("=== Current state ===")
print(q(client, "cd /root/gis_project && source ~/venv/bin/activate && python -c 'import torch, torchvision; print(torch.__version__, torchvision.__version__)'"))

# Step 2: Patch transformers to avoid torchvision import
# The problematic import is: from torchvision.io import ImageReadMode, decode_image
print("\n=== Patch transformers image_utils.py ===")

# Read current content around the problematic line
content = q(client, "grep -n 'torchvision' /root/venv/lib/python3.10/site-packages/transformers/image_utils.py | head -10")
print("Current torchvision refs:", content[:500])

# Apply patch using Python on remote server
patch_cmd = '''
cd /root/gis_project && source ~/venv/bin/activate && python -c "
import re
fpath = '/root/venv/lib/python3.10/site-packages/transformers/image_utils.py'
with open(fpath, 'r') as f:
    content = f.read()

# Replace the torchvision import line
old = 'from torchvision.io import ImageReadMode, decode_image'
new = '# torchvision import disabled for compatibility\nImageReadMode = None\ndecode_image = None'
if old in content:
    content = content.replace(old, new)
    print(\"Patched torchvision import\")
else:
    print(\"Import line not found, checking...\")
    if 'torchvision' in content:
        # Try to find and comment out any torchvision import
        content = re.sub(r'^\\s*from torchvision[^\n]+\n', '# torchvision disabled\\n', content, flags=re.MULTILINE)
        print(\"Used regex patch\")
    else:
        print(\"No torchvision found\")

with open(fpath, 'w') as f:
    f.write(content)
print(\"Done\")
"
'''
result = q(client, patch_cmd.replace('\n', ' '))
print("Patch result:", result)

# Step 3: Also patch is_vision_available to return False
print("\n=== Patch is_vision_available ===")
patch_cmd2 = '''
cd /root/gis_project && source ~/venv/bin/activate && python -c "
fpath = '/root/venv/lib/python3.10/site-packages/transformers/image_utils.py'
with open(fpath, 'r') as f:
    content = f.read()

# Add is_vision_available override at the end
override = '''

def is_vision_available() -> bool:
    return False

'''
if 'def is_vision_available() -> bool:\\n    return False' not in content:
    content = content.rstrip() + override
    print(\"Added is_vision_available override\")
else:
    print(\"Already overridden\")

with open(fpath, 'w') as f:
    f.write(content)
"
'''
result2 = q(client, patch_cmd2.replace('\n', ' '))
print("Patch2 result:", result2)

# Step 4: Test import
print("\n=== Test import ===")
transport2 = client.get_transport()
session2 = transport2.open_session()
session2.exec_command('cd /root/gis_project && source ~/venv/bin/activate && python -c "from transformers import AutoModelForSemanticSegmentation; print(\'SUCCESS\')" 2>&1')
time.sleep(10)
out2 = b''
while time.time() < time.time() + 30:
    if session2.recv_ready():
        out2 += session2.recv(4096)
    if session2.exit_status_ready():
        break
    time.sleep(1)
print(out2.decode()[:3000])

client.close()
