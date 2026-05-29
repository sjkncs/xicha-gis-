import py_compile, sys
path = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_offline.py"
try:
    py_compile.compile(path, doraise=True)
    print("Syntax OK!")
except py_compile.PyCompileError as e:
    print("ERROR:", e)
