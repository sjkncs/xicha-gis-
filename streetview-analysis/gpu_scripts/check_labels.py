import paramiko

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

import time
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)

print("=== Model id2label config ===")
cmd = """cd /root/gis_project && source ~/venv/bin/activate && python3 << 'PYEOF'
import json
with open('/root/gis_project/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/config.json') as f:
    config = json.load(f)
id2label = config.get('id2label', {})
for k in sorted(id2label.keys(), key=lambda x: int(x)):
    print(f'{int(k):3d}: {id2label[k]}')
PYEOF"""
print(q(client, cmd))

client.close()
