import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('connect.bjb1.seetacloud.com', port=50405, username='root', password='roBbKv+ed3Vm', timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace').strip()

# Check python3
print("=== Python3 check ===")
print(run("which python3"))
print(run("python3 --version"))

# Start the script with python3
print("\n=== Starting script ===")
run("cd /root/autodl-tmp && nohup python3 sim_run_cpu.py > sim_cpu.log 2>&1 &")
print("Started")

# Give it 10s then check
import time
time.sleep(10)

print("\n=== Initial log ===")
print(run("tail -15 /root/autodl-tmp/sim_cpu.log"))

print("\n=== Process check ===")
print(run("ps aux | grep sim_run_cpu | grep -v grep"))

client.close()
