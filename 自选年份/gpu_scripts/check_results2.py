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

print("=== CSV results (first 20 rows) ===")
print(q(client, "head -20 /root/gis_project/outputs/segmentation/seg_results.csv"))

print("\n=== Summary stats ===")
cmd = """cd /root/gis_project && source ~/venv/bin/activate && python3 << 'PYEOF'
import csv
r = list(csv.DictReader(open('outputs/segmentation/seg_results.csv')))
n = len(r)
if n > 0:
    print(f'Total: {n}')
    print(f'Avg building: {sum(float(x["pct_building"])/n for x in r):.1f}%')
    print(f'Avg road: {sum(float(x["pct_road"])/n for x in r):.1f}%')
    print(f'Avg green: {sum(float(x["pct_green"])/n for x in r):.1f}%')
    print(f'Avg sky: {sum(float(x["pct_sky"])/n for x in r):.1f}%')
    print(f'Avg openness: {sum(float(x["openness"])/n for x in r):.2f}')
    print(f'Avg walkability: {sum(float(x["walkability"])/n for x in r):.2f}')
else:
    print('No results yet')
PYEOF"""
print(q(client, cmd))

client.close()
