import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('connect.bjb1.seetacloud.com', port=50405, username='root', password='roBbKv+ed3Vm', timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode().strip()

print("=== GPU ===")
print(run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"))

print("\n=== Images count ===")
print(run("find /root/autodl-tmp -name '*.jpg' 2>/dev/null | wc -l"))

print("\n=== Models ===")
print(run("ls /root/autodl-tmp/*.pt /root/autodl-tmp/*.pth 2>/dev/null"))

print("\n=== Streetview data ===")
print(run("ls /root/autodl-tmp/streetview_analysis/ 2>/dev/null"))
print(run("ls /root/autodl-tmp/autodl-tmp/ 2>/dev/null | head -20"))

print("\n=== Previous results ===")
print(run("ls /root/autodl-tmp/streetview_analysis/results/ 2>/dev/null | head -20"))
print(run("ls /root/autodl-tmp/streetview_analysis/viz_sim/ 2>/dev/null"))
print(run("ls /root/autodl-tmp/streetview_analysis/viz_sim/viz_sim_samples/ 2>/dev/null | wc -l"))

print("\n=== Data directories ===")
print(run("find /root/autodl-tmp -maxdepth 3 -type d 2>/dev/null | head -30"))

client.close()
print("DONE")
