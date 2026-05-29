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

print('=== 检查 pip 可用性 ===')
print(q(client, 'cd /root/gis_project && source ~/venv/bin/activate && pip --version'))
print(q(client, 'cd /root/gis_project && source ~/venv/bin/activate && pip install torch --dry-run 2>&1 | head -20'))

print('\n=== 尝试 pip install torch>=2.6 ===')
transport = client.get_transport()
session = transport.open_session()
session.exec_command('cd /root/gis_project && source ~/venv/bin/activate && pip install "torch>=2.6" -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tail -20')
time.sleep(5)
out = b''
while True:
    if session.recv_ready():
        out += session.recv(4096)
    if session.exit_status_ready():
        break
    time.sleep(1)
print(out.decode())

print('\n=== 再次检查版本 ===')
print(q(client, 'cd /root/gis_project && source ~/venv/bin/activate && python -c "import torch; print(torch.__version__)"'))

client.close()
