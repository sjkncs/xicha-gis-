import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('connect.bjb1.seetacloud.com', port=50405, username='root', password='roBbKv+ed3Vm', timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace').strip()

log = run("tail -50 /root/autodl-tmp/sim_cpu.log 2>/dev/null")
print("=== LOG TAIL ===")
print(log)

cnt = run("ls /root/autodl-tmp/streetview_sim/samples/ 2>/dev/null | wc -l")
print("\n=== SAMPLE COUNT ===")
print(cnt)

files = run("ls /root/autodl-tmp/streetview_sim/samples/ 2>/dev/null | head -10")
print("\n=== FILES ===")
print(files)

# Check if script is running
proc = run("ps aux | grep sim_run_cpu | grep -v grep")
print("\n=== PROCESS ===")
print(proc if proc else "NOT RUNNING")

client.close()
