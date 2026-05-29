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

def nohup(ssh, cmd, wait=5):
    transport = ssh.get_transport()
    session = transport.open_session()
    session.exec_command(f'nohup {cmd} > /tmp/upgrade_torch.log 2>&1 &')
    time.sleep(wait)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)

print('=== 当前版本 ===')
print(q(client, 'cd /root/gis_project && source ~/venv/bin/activate && python -c "import torch; print(torch.__version__)"'))

print('\n=== 升级 torch ===')
nohup(client, 'cd /root/gis_project && source ~/venv/bin/activate && pip install torch>=2.6.0 -q')

print('等待 60s...')
time.sleep(60)

print('\n=== 检查日志 ===')
stdin, stdout, stderr = client.exec_command('cat /tmp/upgrade_torch.log')
print(stdout.read().decode()[:2000])

print('\n=== 新版本 ===')
print(q(client, 'cd /root/gis_project && source ~/venv/bin/activate && python -c "import torch; print(torch.__version__)"'))

client.close()
