# -*- coding: utf-8 -*-
"""Test segment_inference after fix"""
import os
import sys
import subprocess

work_dir = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility'
data_dir = os.path.join(work_dir, 'data', 'dl_pipeline')
images_dir = os.path.join(data_dir, 'images', 'raw')
infer_py = os.path.join(work_dir, 'algorithms', 'deep_learning', 'dl_pipeline', 'segment_inference.py')

# Check images
files = [f for f in os.listdir(images_dir) if f.endswith('.png')]
print(f'Images: {len(files)}')

# Run inference
print('Running inference (deeplabv3_resnet50, CPU)...')
result = subprocess.run(
    [sys.executable, infer_py,
     '--input', images_dir,
     '--models', 'deeplabv3_resnet50',
     '--output-csv', os.path.join(data_dir, 'results_test.csv'),
     '--device', 'cpu',
     '--output-dir', os.path.join(data_dir, 'images', 'results'),
     '--no-masks'],
    cwd=work_dir,
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace',
    timeout=300,
)
print(f'Inference exit: {result.returncode}')

# Check results
results_csv = os.path.join(data_dir, 'results_test.csv')
if os.path.exists(results_csv):
    import pandas as pd
    df = pd.read_csv(results_csv)
    print(f'Results: {len(df)} rows')
    print(f'Columns: {list(df.columns)}')
    if len(df) > 0:
        for col in ['SCR', 'GVR', 'VVR', 'CSR']:
            if col in df.columns:
                vals = df[col].dropna()
                if len(vals) > 0:
                    print(f'  {col}: mean={vals.mean():.4f}, min={vals.min():.4f}, max={vals.max():.4f}')
        # Show first row
        print(f'  First result: {dict(df.iloc[0])}')
    else:
        print('  No valid results')
else:
    print('Results CSV not found')
    # Check stderr
    if result.stderr:
        for line in result.stderr.split('\n'):
            if line.strip():
                print(f'  ERR: {line[:200]}')
