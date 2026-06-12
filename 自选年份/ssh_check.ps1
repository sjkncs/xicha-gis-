$pass = "roBbKv+ed3Vm"
$cmd = "nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader; echo '---'; python3 --version; pip3 list 2>/dev/null | grep -iE 'torch|segmentation|timm|opencv'"
$sshCmd = "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p 10244 root@connect.bjb1.seetacloud.com '$cmd'"
$proc = Start-Process cmd -ArgumentList "/c", "echo $pass | $sshCmd" -NoNewWindow -Wait -PassThru
Write-Output "Exit: $($proc.ExitCode)"
