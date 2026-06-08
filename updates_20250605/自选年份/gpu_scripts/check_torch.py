import paramiko

HOST = 'connect.bjb1.seetacloud.com'
PORT = 37625
USER = 'root'
PWD = 'roBbKv+ed3Vm'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=10)

# Check torch version
stdin, stdout, stderr = client.exec_command('cd /root/gis_project && source ~/venv/bin/activate && python -c "import torch; print(torch.__version__)"')
print('torch:', stdout.read().decode().strip())

# Check model files
stdin, stdout, stderr = client.exec_command('ls /root/gis_project/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/')
files = stdout.read().decode()
print('Model files:', files)

# Check if safetensors
has_safetensors = 'safetensors' in files
print('Has safetensors:', has_safetensors)

# Check config for file format
stdin, stdout, stderr = client.exec_command('cat /root/gis_project/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/config.json')
config = stdout.read().decode()
print('Config snippet:', config[:500])

client.close()
