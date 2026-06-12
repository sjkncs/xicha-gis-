import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('connect.bjb1.seetacloud.com', port=50405, username='root', password='roBbKv+ed3Vm', timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace').strip()

print("=== Log ===")
print(run("tail -15 /root/autodl-tmp/sim_v2.log"))
print("\n=== Count ===")
print(run("ls /root/autodl-tmp/streetview_sim_v2/samples/ 2>/dev/null | wc -l"))
print("\n=== Last 5 ===")
print(run("ls /root/autodl-tmp/streetview_sim_v2/samples/ 2>/dev/null | tail -5"))
print("\n=== Process ===")
print(run("ps aux | grep sim_run_v2 | grep -v grep"))
client.close()
