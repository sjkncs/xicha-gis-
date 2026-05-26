import subprocess, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
result = subprocess.run(
    [sys.executable, r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\generate_real_figures.py"],
    capture_output=True, cwd=r"E:\xicha gis 智能定位\15分钟城市时间贫困研究",
    text=True, encoding='utf-8', errors='replace'
)
print("STDOUT:", result.stdout[:12000])
if result.stderr:
    print("STDERR:", result.stderr[:3000])
print("Return code:", result.returncode)
