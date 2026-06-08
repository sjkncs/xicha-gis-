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

def wait_for(session, timeout=600):
    out = b''
    start = time.time()
    while time.time() - start < timeout:
        if session.recv_ready():
            out += session.recv(4096)
        if session.exit_status_ready():
            break
        time.sleep(3)
        print(".", end="", flush=True)
    return out.decode()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)

# Downgrade transformers to 4.40.2 (last version without this CVE check)
print("=== Downgrade transformers ===")
transport = client.get_transport()
session = transport.open_session()
session.exec_command('cd /root/gis_project && source ~/venv/bin/activate && pip install transformers==4.40.2 -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1')
print("Installing...")
out = wait_for(session)
print("\n" + out[-3000:] if len(out) > 3000 else out)

print("\n=== Verify version ===")
print(q(client, "cd /root/gis_project && source ~/venv/bin/activate && pip show transformers | grep Version"))

print("\n=== Test model load ===")
transport2 = client.get_transport()
session2 = transport2.open_session()
session2.exec_command('cd /root/gis_project && source ~/venv/bin/activate && python -c "from transformers import SegformerForSemanticSegmentation; print(\\\"Model class OK\\\")" 2>&1')
time.sleep(5)
out2 = wait_for(session2, timeout=120)
print(out2[:3000])

client.close()
