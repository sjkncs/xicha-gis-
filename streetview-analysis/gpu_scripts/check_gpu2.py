import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('connect.bjb1.seetacloud.com', port=50405, username='root', password='roBbKv+ed3Vm', timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode().strip()

print("=== Nanshan images structure ===")
print(run("find /root/autodl-tmp/streetview_images/南山区 -name '*.jpg' 2>/dev/null | head -10"))
print("\n=== Nanshan subdirs ===")
print(run("find /root/autodl-tmp/streetview_images/南山区 -type d 2>/dev/null | head -20"))
print("\n=== Nanshan image count ===")
print(run("find /root/autodl-tmp/streetview_images/南山区 -name '*.jpg' 2>/dev/null | wc -l"))
print("\n=== Segmentation results ===")
print(run("ls /root/autodl-tmp/streetview_seg/results/ 2>/dev/null | head -10"))
print("\n=== Python env ===")
print(run("python3 -c 'import torch; print(torch.__version__, torch.cuda.is_available())'"))
print(run("python3 -c 'from ultralytics import YOLO; print(\"ultralytics ok\")'"))
print(run("python3 -c 'import torchvision; print(\"torchvision ok\")'"))
client.close()
print("DONE")
