#!/usr/bin/env python3
"""Check local transformers version and config."""
import os, json

SNAP_PATH = r"C:\Users\Administrator\.cache\huggingface\hub\models--nvidia--segformer-b3-finetuned-ade-512-512\snapshots\a820c29fc1e53723079d94ca0e09a14d2657fae6"

print("=== Files ===")
for f in os.listdir(SNAP_PATH):
    fp = os.path.join(SNAP_PATH, f)
    sz = os.path.getsize(fp)
    print(f"  {f}: {sz/1024/1024:.1f}MB")

print("\n=== Config ===")
with open(os.path.join(SNAP_PATH, "config.json")) as f:
    cfg = json.load(f)
for k in ["model_type", "architectures", "depths", "hidden_sizes", "num_labels"]:
    if k in cfg:
        print(f"  {k}: {cfg[k]}")

print("\n=== Local transformers version ===")
try:
    import transformers
    print(f"  transformers {transformers.__version__}")
except:
    print("  not installed locally")

# Check pytorch_model.bin keys
import torch
sd = torch.load(os.path.join(SNAP_PATH, "pytorch_model.bin"), map_location="cpu")
print(f"\n=== Weight keys ({len(sd)} total) ===")
print("  encoder.*:", [k for k in sd if k.startswith("segformer.encoder")][:3])
print("  stages.*:", [k for k in sd if "stages" in k][:3])
print("  decode.*:", [k for k in sd if "decode" in k][:3])
print("  linear_c.*:", [k for k in sd if "linear_c" in k][:3])

# Try loading with local transformers
print("\n=== Try loading with local transformers ===")
try:
    from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
    processor = AutoImageProcessor.from_pretrained(SNAP_PATH)
    model = AutoModelForSemanticSegmentation.from_pretrained(SNAP_PATH)
    print("  SUCCESS! Model loaded.")
    print("  Model type:", type(model).__name__)
    # Test a forward pass
    import numpy as np
    from PIL import Image
    dummy = Image.fromarray(np.random.randint(0,255,(512,512,3),dtype=np.uint8))
    inputs = processor(images=[dummy], return_tensors="pt")
    with torch.no_grad():
        out = model(**inputs)
    print("  Forward pass OK, logits shape:", out.logits.shape)
except Exception as e:
    print(f"  FAILED: {e}")
    import traceback
    traceback.print_exc()
