#!/usr/bin/env python3
"""Test model output distribution on server."""
import sys
sys.path.insert(0, "/root/autodl-tmp")
import numpy as np
from pathlib import Path
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

snap = "/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default"
processor = AutoImageProcessor.from_pretrained(snap, local_files_only=True)
model = AutoModelForSemanticSegmentation.from_pretrained(snap, local_files_only=True)
device = torch.device("cuda")
model.to(device); model.eval()

imgs = list(Path("/root/autodl-tmp/streetview_analysis/images").rglob("*.jpg"))[:2]
out = []
for img_path in imgs:
    img = Image.open(img_path).convert("RGB")
    inputs = processor(images=[img], return_tensors="pt").to(device)
    with torch.no_grad():
        logits = model(**inputs).logits
    pred = torch.argmax(logits[0], dim=0).cpu().numpy()
    uniq, cnt = np.unique(pred, return_counts=True)
    total = pred.size
    city = {"building":0,"road":0,"green":0,"sky":0,"person":0,"car":0,"other":0}
    cls_map = {0:"road",1:"road",2:"building",3:"building",5:"other",6:"other",7:"other",8:"other",9:"green",10:"green",11:"sky",12:"person",13:"person",14:"car",15:"car",16:"car",17:"car",18:"car",19:"car"}
    for c in uniq:
        if c in cls_map: city[cls_map[c]] += cnt[np.where(uniq==c)[0][0]]
    result = {k: f"{v/total*100:.1f}%" for k,v in city.items()}
    result["top5"] = [(int(uniq[np.argsort(-cnt)[i]]), int(cnt[np.argsort(-cnt)[i]])) for i in range(min(5,len(uniq)))]
    result["logits_shape"] = str(logits.shape)
    out.append((str(img_path.name), result))
    print(f"{img_path.name}: {result}")
