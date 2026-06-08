#!/usr/bin/env python3
"""Download SegFormer B3 model to local cache."""
import os, time
from pathlib import Path

# Set cache to a known location
CACHE_DIR = Path(r"C:\Users\Administrator\.cache\huggingface\hub")
os.environ["HF_HOME"] = str(CACHE_DIR)
os.environ["TRANSFORMERS_CACHE"] = str(CACHE_DIR)

MODEL_ID = "nvidia/segformer-b3-finetuned-ade-512-512"

print(f"Downloading {MODEL_ID} to {CACHE_DIR}")
print(f"HF_HOME: {os.environ.get('HF_HOME')}")
print()

# Use huggingface_hub directly
from huggingface_hub import snapshot_download

t0 = time.time()
try:
    path = snapshot_download(
        repo_id=MODEL_ID,
        cache_dir=str(CACHE_DIR),
        local_files_only=False,
        resume_download=True,
    )
    elapsed = time.time() - t0
    print(f"Downloaded to: {path}")
    print(f"Time: {elapsed:.1f}s ({elapsed/60:.1f}min)")

    # List files
    p = Path(path)
    total = 0
    for f in sorted(p.rglob("*")):
        if f.is_file():
            sz = f.stat().st_size
            total += sz
            print(f"  {f.name}: {sz/1024/1024:.1f}MB")
    print(f"Total: {total/1024/1024:.1f}MB")

except Exception as e:
    print(f"Error: {e}")
    # Try with transformers instead
    print("\nTrying with transformers...")
    from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
    try:
        processor = SegformerImageProcessor.from_pretrained(MODEL_ID)
        print(f"Processor downloaded to: {processor.cache_folder}")
        model = SegformerForSemanticSegmentation.from_pretrained(MODEL_ID)
        print(f"Model downloaded successfully")
        # Get the actual path
        cfg = model.config
        print(f"Model class: {type(model).__name__}")
    except Exception as e2:
        print(f"Transformers error: {e2}")
