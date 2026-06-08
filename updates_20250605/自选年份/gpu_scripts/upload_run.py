import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('connect.bjb1.seetacloud.com', port=50405, username='root', password='roBbKv+ed3Vm', timeout=15)
sftp = client.open_sftp()
sftp.put('e:\\xicha gis 智能定位\\自选年份\\gpu_scripts\\sim_run.py', '/root/autodl-tmp/sim_run.py')
sftp.close()
print('Uploaded')
client.close()
