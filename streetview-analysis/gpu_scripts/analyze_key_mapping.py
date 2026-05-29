#!/usr/bin/env python3
"""Test key remapping between old and new SegFormer architectures."""
import torch, json, os

SNAP_PATH = r"C:\Users\Administrator\.cache\huggingface\hub\models--nvidia--segformer-b3-finetuned-ade-512-512\snapshots\a820c29fc1e53723079d94ca0e09a14d2657fae6"

sd = torch.load(os.path.join(SNAP_PATH, "pytorch_model.bin"), map_location="cpu")
print(f"Total keys: {len(sd)}")

# Analyze old naming patterns
old_keys = sorted([k for k in sd.keys()])
print("\n=== Old key patterns ===")
for k in old_keys:
    print(f"  {k}")

# The new naming uses 'stages' and 'blocks' instead of direct encoder indexing
# Old: segformer.encoder.patch_embeddings.0.proj.weight
# New: segformer.stages.0.patch_embeddings.proj.weight
# Old: segformer.encoder.block.0.layers.0.attention.self.query.weight
# New: segformer.stages.0.blocks.0.attn.q_linear.weight
# Old: segformer.encoder.layer_norm.0.weight
# New: segformer.stages.0.layer_norm.weight

print("\n=== Old keys that need mapping ===")
# Group by pattern
patterns = {}
for k in old_keys:
    # Extract prefix
    if "encoder.patch_embeddings" in k:
        prefix = "patch_emb"
    elif "encoder.block" in k or "encoder.layer_norm" in k:
        # Extract stage number
        parts = k.split(".")
        for i, p in enumerate(parts):
            if p in ("block", "layer_norm"):
                prefix = f"encoder_{p}_{parts[i+1]}"
                break
        else:
            prefix = "other"
    else:
        prefix = "other"
    patterns.setdefault(prefix, []).append(k)

for p, ks in sorted(patterns.items()):
    print(f"\n{p}:")
    for k in ks[:5]:
        print(f"  {k}")
    if len(ks) > 5:
        print(f"  ... ({len(ks)} total)")
