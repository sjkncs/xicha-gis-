#!/usr/bin/env python3
import paramiko, time

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
SCRIPT = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v6.py"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

client.exec_command("ps aux | grep seg_inference | grep -v grep | awk '{print $2}' | xargs -r kill -9")
sftp.put(SCRIPT, "/root/autodl-tmp/seg_inference_v6.py")
client.exec_command("rm -f /root/autodl-tmp/outputs/segmentation/checkpoint.json /root/autodl-tmp/seg_inference_v6.log")
client.exec_command("cd /root/autodl-tmp && nohup python3 seg_inference_v6.py > seg_inference_v6.log 2>&1 &")
print("Started. Waiting 25s...")
time.sleep(25)

stdin, stdout, stderr = client.exec_command("tail -10 /root/autodl-tmp/seg_inference_v6.log; echo '---CSV:'; wc -l /root/autodl-tmp/outputs/segmentation/seg_results.csv; echo '---Viz:'; ls /root/autodl-tmp/outputs/segmentation/viz/ | wc -l; echo '---GPU:'; nvidia-smi --query-gpu=memory.used --format=csv,noheader")
print(stdout.read().decode()[:1200])

stdin, stdout, stderr = client.exec_command("tail -3 /root/autodl-tmp/outputs/segmentation/seg_results.csv")
print("Recent:", stdout.read().decode()[:500])

sftp.close()
client.close()
