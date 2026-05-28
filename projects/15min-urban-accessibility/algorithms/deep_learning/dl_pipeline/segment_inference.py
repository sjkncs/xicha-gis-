# -*- coding: utf-8 -*-
"""
GPU 语义分割推理管线 - 多模型批量推理
支持 12+ 预训练分割模型，一键批量处理街景图像

模型列表（按推理速度/精度排序）:
  1. torchvision: DeepLabV3-ResNet50    (~20ms/图, COCO预训练)
  2. torchvision: DeepLabV3-ResNet101   (~40ms/图, COCO预训练)
  3. HuggingFace: Intel/deeplabv3-base  (~60ms/图, ADE20K预训练)  [已有]
  4. HuggingFace: nvidia/mit-b0        (~15ms/图, Cityscapes轻量)   [已有]
  5. HuggingFace: nvidia/mit-b1        (~25ms/图, Cityscapes)
  6. HuggingFace: nvidia/mit-b2        (~40ms/图, Cityscapes)
  7. HuggingFace: nvidia/mit-b3        (~60ms/图, Cityscapes)
  8. HuggingFace: nvidia/mit-b4        (~90ms/图, Cityscapes高精度)
  9. HuggingFace: facebook/sam-vit-h   (~200ms/图, SAM万物分割)    [备用]
 10. HuggingFace: DeepLabV3+ (MobileViT) (~30ms/图, 移动端轻量)
 11. HuggingFace: segformer-b0          (~10ms/图, 最高效)          [已有基础款]
 12. HuggingFace: segformer-b1          (~18ms/图)
 13. HuggingFace: segformer-b2          (~30ms/图, 推荐平衡)
 14. HuggingFace: segformer-b3          (~50ms/图)
 15. HuggingFace: segformer-b4          (~80ms/图)

城市形态分割专用类别映射（适配ADE20K/Cityscapes）:
  - sidewalk: 人行道
  - road: 道路
  - building: 建筑
  - vegetation/tree: 绿化/树木
  - sky: 天空
  - person: 行人
  - car/truck/bus: 车辆
  - fence/wall: 围墙/栏杆
  - pole: 电线杆/路灯
  - traffic_light/sign: 交通设施
  - crosswalk: 人行横道
  - curb: 路缘石

步行可达性指标计算:
  SCR = 人行道像素 / (人行道+道路)像素
  GVR = 绿化像素 / 天空以外总像素
  VVR = 车辆像素 / 可见区域总像素
  CSR = 建筑立面像素占比
"""

import os
import sys
import json
import time
import math
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
import shutil
import tempfile

import numpy as np
import pandas as pd

# ============================================================
# PyTorch & 模型
# ============================================================

try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print('[WARN] PyTorch 未安装，无法运行 GPU 推理')

try:
    import torchvision
    from torchvision.models.segmentation import (
        deeplabv3_resnet50, deeplabv3_resnet101,
        deeplabv3_mobilenet_v3_large,
    )
    from torchvision.models.segmentation.fcn import fcn_resnet50, fcn_resnet101
    from torchvision.models import ResNet50_Weights, ResNet101_Weights
    from torchvision.models.segmentation.deeplabv3 import (
        DeepLabV3_ResNet50_COCO_States, DeepLabV3_ResNet101_COCO_States,
    )
    TORCHVISION_AVAILABLE = True
except ImportError:
    TORCHVISION_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MPL_AVAILABLE = True
except Exception:
    MPL_AVAILABLE = False


# ============================================================
# 路径配置
# ============================================================

BASE_DIR = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility'
DATA_DIR = os.path.join(BASE_DIR, 'data', 'dl_pipeline')
IMAGES_DIR = os.path.join(DATA_DIR, 'images', 'raw')
MASKS_DIR = os.path.join(DATA_DIR, 'images', 'masks')
RESULTS_DIR = os.path.join(DATA_DIR, 'images', 'results')
MODEL_CACHE_DIR = os.path.join(DATA_DIR, 'models', 'pretrained')
CHECKPOINT_DIR = os.path.join(DATA_DIR, 'checkpoints')

for d in [MASKS_DIR, RESULTS_DIR, MODEL_CACHE_DIR]:
    os.makedirs(d, exist_ok=True)


# ============================================================
# 设备检测
# ============================================================

def get_device() -> str:
    """检测可用设备"""
    if not TORCH_AVAILABLE:
        return 'cpu'
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f'  [设备] GPU: {gpu_name} ({gpu_mem:.1f} GB)')
        return 'cuda'
    print('  [设备] GPU 不可用，使用 CPU')
    return 'cpu'


# ============================================================
# 模型注册表
# ============================================================

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    # --- torchvision 内置 (最快，无需下载) ---
    'deeplabv3_resnet50': {
        'name': 'DeepLabV3-ResNet50 (COCO)',
        'source': 'torchvision',
        'speed': 'fast',        # ~20ms
        'pretrained_dataset': 'COCO',
        'num_classes': 21,
        'model_args': {'weights': 'DEFAULT'},
        'class_names': [
            'background', 'aeroplane', 'bicycle', 'bird', 'boat',
            'bottle', 'bus', 'car', 'cat', 'chair', 'cow',
            'diningtable', 'dog', 'horse', 'motorbike', 'person',
            'pottedplant', 'sheep', 'sofa', 'train', 'tvmonitor',
        ],
        'category_map': {
            'person': 'pedestrian',
            'bus': 'vehicle', 'car': 'vehicle', 'train': 'vehicle', 'boat': 'vehicle',
        },
        'notes': 'COCO 20类，person/bus/car/boat 适合街景',
    },
    'deeplabv3_resnet101': {
        'name': 'DeepLabV3-ResNet101 (COCO)',
        'source': 'torchvision',
        'speed': 'medium',       # ~40ms
        'pretrained_dataset': 'COCO',
        'num_classes': 21,
        'model_args': {'weights': 'DEFAULT'},
        'class_names': [
            'background', 'aeroplane', 'bicycle', 'bird', 'boat',
            'bottle', 'bus', 'car', 'cat', 'chair', 'cow',
            'diningtable', 'dog', 'horse', 'motorbike', 'person',
            'pottedplant', 'sheep', 'sofa', 'train', 'tvmonitor',
        ],
        'category_map': {
            'person': 'pedestrian',
            'bus': 'vehicle', 'car': 'vehicle', 'train': 'vehicle',
        },
        'notes': '比 ResNet50 更高精度',
    },
    'deeplabv3_mobilenet': {
        'name': 'DeepLabV3-MobileNetV3 (COCO)',
        'source': 'torchvision',
        'speed': 'fastest',     # ~10ms
        'pretrained_dataset': 'COCO',
        'num_classes': 21,
        'model_args': {},
        'class_names': [
            'background', 'aeroplane', 'bicycle', 'bird', 'boat',
            'bottle', 'bus', 'car', 'cat', 'chair', 'cow',
            'diningtable', 'dog', 'horse', 'motorbike', 'person',
            'pottedplant', 'sheep', 'sofa', 'train', 'tvmonitor',
        ],
        'category_map': {
            'person': 'pedestrian',
            'bus': 'vehicle', 'car': 'vehicle',
        },
        'notes': '最轻量，适合批量处理',
    },
    'fcn_resnet50': {
        'name': 'FCN-ResNet50 (COCO)',
        'source': 'torchvision',
        'speed': 'fast',        # ~18ms
        'pretrained_dataset': 'COCO',
        'num_classes': 21,
        'model_args': {},
        'class_names': [
            'background', 'aeroplane', 'bicycle', 'bird', 'boat',
            'bottle', 'bus', 'car', 'cat', 'chair', 'cow',
            'diningtable', 'dog', 'horse', 'motorbike', 'person',
            'pottedplant', 'sheep', 'sofa', 'train', 'tvmonitor',
        ],
        'category_map': {
            'person': 'pedestrian', 'bus': 'vehicle', 'car': 'vehicle',
        },
        'notes': '全卷积网络，语义分割经典',
    },

    # --- HuggingFace (需下载) ---
    'intel_deeplabv3': {
        'name': 'Intel DeepLabV3+ (ADE20K)',
        'source': 'huggingface',
        'speed': 'medium',       # ~60ms
        'model_id': 'Intel/deeplabv3-base',
        'pretrained_dataset': 'ADE20K',
        'num_classes': 150,
        'class_names_url': None,
        'notes': 'ADE20K 150类，包含 sidewalk/building/tree 等丰富类别',
    },
    'nvidia_mit_b0': {
        'name': 'SegFormer-B0 (Cityscapes)',
        'source': 'huggingface',
        'speed': 'fastest',     # ~15ms
        'model_id': 'nvidia/mit-b0',
        'pretrained_dataset': 'Cityscapes',
        'num_classes': 20,
        'notes': '极轻量，Cityscapes 20类，适合街景',
    },
    'nvidia_mit_b2': {
        'name': 'SegFormer-B2 (Cityscapes)',
        'source': 'huggingface',
        'speed': 'medium',       # ~40ms
        'model_id': 'nvidia/mit-b2',
        'pretrained_dataset': 'Cityscapes',
        'num_classes': 20,
        'notes': '推荐平衡款，精度与速度兼顾',
    },
    'nvidia_mit_b4': {
        'name': 'SegFormer-B4 (Cityscapes)',
        'source': 'huggingface',
        'speed': 'slow',         # ~90ms
        'model_id': 'nvidia/mit-b4',
        'pretrained_dataset': 'Cityscapes',
        'num_classes': 20,
        'notes': '高精度，适合高质量分析',
    },
    'segformer_b0': {
        'name': 'SegFormer-B0 (ADE20K)',
        'source': 'huggingface',
        'speed': 'fastest',     # ~10ms
        'model_id': 'nvidia/segformer-b0-finetuned-cityscapes-1024-1024',
        'pretrained_dataset': 'Cityscapes',
        'num_classes': 20,
        'notes': '最新 SegFormer，MIT-B0 架构，极速',
    },
    'segformer_b2': {
        'name': 'SegFormer-B2 (ADE20K)',
        'source': 'huggingface',
        'speed': 'medium',       # ~30ms
        'model_id': 'nvidia/segformer-b2-finetuned-cityscapes-1024-1024',
        'pretrained_dataset': 'Cityscapes',
        'num_classes': 20,
        'notes': '推荐平衡款，SegFormer 架构更现代',
    },
    'segformer_b3': {
        'name': 'SegFormer-B3 (ADE20K)',
        'source': 'huggingface',
        'speed': 'slow',         # ~50ms
        'model_id': 'nvidia/segformer-b3-finetuned-cityscapes-1024-1024',
        'pretrained_dataset': 'Cityscapes',
        'num_classes': 20,
        'notes': '高精度版本',
    },
}


# ============================================================
# ADE20K 类别映射（用于高德/SegFormer模型）
# ============================================================

# ADE20K 完整类别（简化版，关键类别）
ADE20K_CLASSES = {
    0: 'wall', 1: 'building', 2: 'sky', 3: 'floor', 4: 'tree',
    5: 'ceiling', 6: 'road', 7: 'cabinet', 8: 'person', 9: 'grass',
    10: 'animal', 11: 'mountain', 12: 'plant', 13: 'grass', 14: 'pole',
    15: 'water', 16: 'house', 17: 'sea', 18: 'mirror', 19: 'rug',
    20: 'field', 21: 'armchair', 22: 'seat', 23: 'fence', 24: 'desk',
    25: 'rock', 26: 'wardrobe', 27: 'lamp', 28: 'bathtub', 29: 'pillow',
    30: 'screen', 31: 'pool', 32: 'shelves', 33: 'bench', 34: 'toilet',
    35: 'sink', 36: 'stairs', 37: 'swivelchair', 38: 'mirror', 39: 'tvmonitor',
    40: 'boat', 41: 'book', 42: 'tissue', 43: 'vase', 44: 'truck', 45: 'chandelier',
    46: 'coffee maker', 47: 'basket', 48: 'washer', 49: 'sports car', 50: 'chair',
    51: 'bicycle', 52: 'stair', 53: 'small_offset', 54: 'escalator', 55: 'tread',
    56: 'central offset', 57: 'bus', 58: 'motorbike', 59: 'traffic light', 60: 'fire hydrant',
    61: 'parking meter', 62: 'car', 63: 'cart', 64: 'stroller', 65: 'trailer',
    66: 'person', 67: 'trailer', 68: 'truck', 69: 'parking', 70: 'stairs',
    71: 'curb', 72: 'pot', 73: 'bicycle', 74: 'car', 75: 'truck',
    76: 'bus', 77: 'trailer', 78: 'skateboard', 79: 'tripod', 80: 'building',
    81: 'curb', 82: 'crosswalk', 83: 'sidewalk', 84: 'parking', 85: 'traffic light',
}

# 步行可达性关键类别
WALKABILITY_CLASSES = {
    'sidewalk': {  # 人行道
        'ade20k': [83],
        'cityscapes': [],  # 需要按实际类别
    },
    'road': {
        'ade20k': [6],
    },
    'building': {
        'ade20k': [1, 80],
    },
    'tree': {
        'ade20k': [4, 12, 13],
    },
    'sky': {
        'ade20k': [2],
    },
    'person': {
        'ade20k': [8, 66],
        'coco': [15],  # COCO person class
    },
    'vehicle': {
        'ade20k': [44, 49, 57, 58, 62, 68, 74, 75, 76],
        'coco': [2, 3, 6, 7, 8, 14],  # car, motorcycle, bus, truck, train, boat
    },
    'fence': {
        'ade20k': [23],
    },
    'pole': {
        'ade20k': [14],
    },
    'traffic_light': {
        'ade20k': [59],
        'coco': [9],
    },
    'crosswalk': {
        'ade20k': [82],
    },
    'curb': {
        'ade20k': [71, 81],
    },
}


# ============================================================
# 数据结构
# ============================================================

@dataclass
class SegmentationOutput:
    """单张图像分割结果"""
    image_path: str
    model_name: str
    model_id: str
    mask: np.ndarray       # H x W, 类别ID
    shape: Tuple[int, int]  # (H, W)
    class_counts: Dict[int, int]  # {class_id: pixel_count}
    processing_time_ms: float

    def get_coverage(self, class_ids: List[int]) -> float:
        """计算指定类别覆盖率"""
        if len(self.mask) == 0:
            return 0.0
        total = self.mask.size
        covered = sum((self.mask == cid).sum() for cid in class_ids)
        return float(covered / total)


@dataclass
class WalkabilityIndices:
    """步行可达性指标"""
    scr: float = 0.0   # Sidewalk Coverage Ratio
    gvr: float = 0.0   # Green Visibility Ratio
    vvr: float = 0.0   # Vehicle View Ratio
    csr: float = 0.0   # Building/Sky Ratio
    pedestrian_density: float = 0.0  # 行人密度
    obstacle_ratio: float = 0.0       # 障碍物比例

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class InferenceResult:
    """完整推理结果"""
    image_path: str
    sample_id: str
    model_name: str
    segmentation: SegmentationOutput
    walkability: WalkabilityIndices
    metrics: Dict[str, Any]


# ============================================================
# 分割模型基类
# ============================================================

class SegmentationModel:
    """语义分割模型基类"""

    def __init__(self, model_key: str, device: str = 'auto'):
        self.model_key = model_key
        self.config = MODEL_REGISTRY.get(model_key)
        if not self.config:
            raise ValueError(f'未知模型: {model_key}，可用: {list(MODEL_REGISTRY.keys())}')

        if device == 'auto':
            device = get_device()
        self.device = torch.device(device) if TORCH_AVAILABLE else None
        self._model = None
        self._processor = None

    @property
    def model(self):
        raise NotImplementedError

    def segment(self, image_path: str) -> Tuple[np.ndarray, float]:
        """
        分割图像，返回 (mask, processing_time_ms)
        mask: H x W numpy array, dtype=int64
        """
        raise NotImplementedError

    def _load_image(self, image_path: str) -> np.ndarray:
        """加载图像为 numpy RGB 数组"""
        if CV2_AVAILABLE:
            img = cv2.imread(image_path)
            if img is not None:
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if PIL_AVAILABLE:
            img = Image.open(image_path)
            return np.array(img.convert('RGB'))
        raise RuntimeError('需要 OpenCV 或 Pillow 来加载图像')

    def _load_image_pil(self, image_path: str) -> 'Image.Image':
        """加载图像为 PIL Image"""
        if PIL_AVAILABLE:
            return Image.open(image_path).convert('RGB')
        if CV2_AVAILABLE:
            img = cv2.imread(image_path)
            if img is not None:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                return Image.fromarray(img)
        raise RuntimeError('需要 OpenCV 或 Pillow 来加载图像')


class TorchVisionSegmentationModel(SegmentationModel):
    """torchvision 内置分割模型"""

    @property
    def model(self):
        if self._model is None:
            key = self.model_key
            print(f'  加载 torchvision 模型: {key}')

            if key == 'deeplabv3_resnet50':
                self._model = deeplabv3_resnet50(**self.config.get('model_args', {}))
            elif key == 'deeplabv3_resnet101':
                self._model = deeplabv3_resnet101(**self.config.get('model_args', {}))
            elif key == 'deeplabv3_mobilenet':
                self._model = deeplabv3_mobilenet_v3_large(weights='DEFAULT')
            elif key == 'fcn_resnet50':
                self._model = fcn_resnet50(weights='DEFAULT')
            elif key == 'fcn_resnet101':
                self._model = fcn_resnet101(weights='DEFAULT')
            else:
                raise ValueError(f'torchvision 不支持: {key}')

            if self.device:
                self._model.to(self.device)
            self._model.eval()
        return self._model

    def segment(self, image_path: str) -> Tuple[np.ndarray, float]:
        t0 = time.time()
        img = self._load_image_pil(image_path)

        # 预处理
        from torchvision import transforms
        preprocess = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])
        input_tensor = preprocess(img).unsqueeze(0)

        if self.device:
            input_tensor = input_tensor.to(self.device)

        with torch.no_grad():
            output = self.model(input_tensor)['out']

        # 上采样到原图尺寸
        H_orig, W_orig = img.size[1], img.size[0]
        output = F.interpolate(output, size=(H_orig, W_orig),
                              mode='bilinear', align_corners=False)
        pred_mask = output.argmax(dim=1)[0].cpu().numpy().astype(np.int64)

        elapsed = (time.time() - t0) * 1000
        return pred_mask, elapsed


class HuggingFaceSegmentationModel(SegmentationModel):
    """HuggingFace 分割模型"""

    HF_CACHE = os.environ.get('HF_HOME', os.path.join(os.path.expanduser('~'), '.cache', 'huggingface'))

    @property
    def model(self):
        if self._model is None:
            model_id = self.config['model_id']
            print(f'  加载 HuggingFace 模型: {model_id}')

            try:
                from transformers import (
                    AutoModelForSemanticSegmentation,
                    AutoImageProcessor,
                )
                self._processor = AutoImageProcessor.from_pretrained(
                    model_id,
                    cache_dir=self.HF_CACHE,
                )
                self._model = AutoModelForSemanticSegmentation.from_pretrained(
                    model_id,
                    cache_dir=self.HF_CACHE,
                )
                if self.device:
                    self._model.to(self.device)
                self._model.eval()
            except Exception as e:
                print(f'  [WARN] HuggingFace 模型加载失败: {e}')
                print(f'  [WARN] 模型将设为 None，后续推理将被跳过')
                self._model = None
        return self._model

    def segment(self, image_path: str) -> Tuple[np.ndarray, float]:
        if self.model is None:
            # 返回空mask
            img = self._load_image_pil(image_path)
            h, w = img.size[1], img.size[0]
            return np.zeros((h, w), dtype=np.int64), 0.0

        t0 = time.time()
        img = self._load_image_pil(image_path)
        H_orig, W_orig = img.size[1], img.size[0]

        try:
            from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
            inputs = self._processor(images=img, return_tensors='pt')

            if self.device:
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)

            logits = outputs.logits
            logits = F.interpolate(logits, size=(H_orig, W_orig),
                                   mode='bilinear', align_corners=False)
            pred_mask = logits.argmax(dim=1)[0].cpu().numpy().astype(np.int64)
        except Exception as e:
            print(f'  [WARN] 推理失败 {image_path}: {e}')
            pred_mask = np.zeros((H_orig, W_orig), dtype=np.int64)

        elapsed = (time.time() - t0) * 1000
        return pred_mask, elapsed


def create_model(model_key: str, device: str = 'auto') -> SegmentationModel:
    """工厂函数：创建分割模型"""
    config = MODEL_REGISTRY.get(model_key)
    if not config:
        raise ValueError(f'未知模型: {model_key}')

    source = config['source']
    if source == 'torchvision':
        return TorchVisionSegmentationModel(model_key, device)
    elif source == 'huggingface':
        return HuggingFaceSegmentationModel(model_key, device)
    else:
        raise ValueError(f'未知模型来源: {source}')


# ============================================================
# 指标计算
# ============================================================

def compute_walkability(mask: np.ndarray, class_names: List[str]) -> WalkabilityIndices:
    """
    从分割 mask 计算步行可达性指标

    策略：
    - COCO 模型：person(15), bus(6), car(2), truck(7) 等
    - ADE20K 模型：sidewalk(83), tree(4/12), person(8/66) 等
    """
    H, W = mask.shape
    total = H * W
    if total == 0:
        return WalkabilityIndices()

    indices = WalkabilityIndices()

    # SCR: 人行道覆盖率
    sidewalk_ids = []
    for cls_name, cls_ids_list in WALKABILITY_CLASSES.items():
        if 'sidewalk' in cls_name and 'ade20k' in cls_ids_list:
            sidewalk_ids.extend(cls_ids_list['ade20k'])
        elif 'sidewalk' in cls_name and 'coco' in cls_ids_list:
            # 尝试用 road 近似
            pass

    # 简化：用道路类别估计人行道
    road_ids = WALKABILITY_CLASSES['road'].get('ade20k', [6])
    road_pixels = sum((mask == rid).sum() for rid in road_ids)

    # 人行道一般占道路宽度的30-60%，保守取40%
    scr_est = min(road_pixels * 0.4 / total, 1.0)
    indices.scr = float(scr_est)

    # GVR: 绿化可见率
    tree_ids = WALKABILITY_CLASSES['tree']['ade20k']
    sky_ids = WALKABILITY_CLASSES['sky']['ade20k']
    non_sky = total - sum((mask == sid).sum() for sid in sky_ids)
    tree_pixels = sum((mask == tid).sum() for tid in tree_ids)
    if non_sky > 0:
        indices.gvr = float(tree_pixels / non_sky)

    # VVR: 车辆可见率
    vehicle_ids = (
        WALKABILITY_CLASSES['vehicle'].get('coco', []) +
        WALKABILITY_CLASSES['vehicle'].get('ade20k', [])
    )
    vehicle_pixels = sum((mask == vid).sum() for vid in vehicle_ids)
    indices.vvr = float(vehicle_pixels / total)

    # CSR: 建筑立面/天空比
    building_ids = WALKABILITY_CLASSES['building']['ade20k']
    sky_ids2 = WALKABILITY_CLASSES['sky']['ade20k']
    building_pixels = sum((mask == bid).sum() for bid in building_ids)
    sky_pixels = sum((mask == sid).sum() for sid in sky_ids2)
    if sky_pixels > 0:
        indices.csr = float(building_pixels / sky_pixels)

    # 行人密度
    person_ids = (
        WALKABILITY_CLASSES['person'].get('coco', []) +
        WALKABILITY_CLASSES['person'].get('ade20k', [])
    )
    person_pixels = sum((mask == pid).sum() for pid in person_ids)
    indices.pedestrian_density = float(person_pixels / total)

    return indices


def compute_class_stats(mask: np.ndarray) -> Dict[int, int]:
    """计算每个类别的像素数"""
    unique, counts = np.unique(mask, return_counts=True)
    return dict(zip(unique.tolist(), counts.tolist()))


# ============================================================
# 批量推理引擎
# ============================================================

class SegmentationInferenceEngine:
    """
    批量语义分割推理引擎

    功能:
    - 支持多模型串行/并行推理
    - 自动保存 mask 可视化
    - 计算步行可达性指标
    - 断点续传（跳过已处理图像）
    - 导出 CSV/JSON 结果
    """

    def __init__(
        self,
        models: List[str] = None,
        device: str = 'auto',
        output_dir: str = RESULTS_DIR,
        save_masks: bool = True,
        save_vis: bool = True,
        save_overlay: bool = False,
    ):
        if models is None:
            models = ['deeplabv3_resnet50', 'intel_deeplabv3', 'nvidia_mit_b0']

        self.models = models
        self.device = device
        self.output_dir = output_dir
        self.save_masks = save_masks
        self.save_vis = save_vis
        self.save_overlay = save_overlay

        self._model_instances: Dict[str, SegmentationModel] = {}
        self._results: List[InferenceResult] = []

    def load_models(self):
        """预加载所有模型到 GPU"""
        print('=' * 60)
        print('加载分割模型')
        print('=' * 60)

        actual_device = get_device()
        for model_key in self.models:
            try:
                model = create_model(model_key, device=actual_device)
                # 触发模型加载
                _ = model.model
                self._model_instances[model_key] = model
                print(f'  [OK] {MODEL_REGISTRY[model_key]["name"]}')
            except Exception as e:
                print(f'  [FAIL] {model_key}: {e}')

        print(f'\n  成功加载: {len(self._model_instances)}/{len(self.models)} 个模型')

    def _get_image_files(self, image_dir: str) -> List[str]:
        """获取目录下所有图像文件"""
        valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'}
        files = []
        for root, _, filenames in os.walk(image_dir):
            for f in filenames:
                if Path(f).suffix.lower() in valid_exts:
                    files.append(os.path.join(root, f))
        return sorted(files)

    def _visualize_mask(
        self,
        mask: np.ndarray,
        output_path: str,
        class_names: List[str] = None,
        alpha: float = 0.6,
    ) -> str:
        """保存 mask 可视化图像"""
        if not MPL_AVAILABLE:
            return ''

        H, W = mask.shape
        fig, ax = plt.subplots(1, 1, figsize=(W / 100, H / 100), dpi=100)

        # 生成调色板
        n_classes = int(mask.max()) + 1
        cmap = plt.cm.get_cmap('tab20', n_classes) if n_classes <= 20 else plt.cm.get_cmap('nipy_spectral', n_classes)

        ax.imshow(mask, cmap=cmap, vmin=0, vmax=max(n_classes - 1, 1))
        ax.axis('off')
        plt.tight_layout(pad=0)
        plt.savefig(output_path, dpi=100, bbox_inches='tight',
                    facecolor='white', format='png')
        plt.close(fig)
        return output_path

    def _generate_overlay(
        self,
        image_path: str,
        mask: np.ndarray,
        output_path: str,
    ) -> str:
        """生成原图+分割叠加图"""
        if not (CV2_AVAILABLE and MPL_AVAILABLE):
            return ''

        try:
            img = cv2.imread(image_path)
            if img is None:
                return ''
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            H, W = mask.shape

            # 缩放图像
            img_small = cv2.resize(img, (W, H), interpolation=cv2.INTER_LINEAR)

            # 生成颜色 mask
            n_classes = int(mask.max()) + 1
            cmap = plt.cm.get_cmap('tab20', n_classes) if n_classes <= 20 else plt.cm.get_cmap('nipy_spectral', n_classes)
            colored_mask = cmap(mask.astype(np.float64) / max(n_classes - 1, 1))[..., :3]
            colored_mask = (colored_mask * 255).astype(np.uint8)

            # 混合
            blended = (img_small * (1 - 0.5) + colored_mask * 0.5).astype(np.uint8)

            fig, axes = plt.subplots(1, 3, figsize=(15, 5))
            axes[0].imshow(img_small)
            axes[0].set_title('Original', fontsize=10)
            axes[0].axis('off')

            axes[1].imshow(colored_mask)
            axes[1].set_title('Segmentation', fontsize=10)
            axes[1].axis('off')

            axes[2].imshow(blended)
            axes[2].set_title('Overlay', fontsize=10)
            axes[2].axis('off')

            plt.tight_layout()
            plt.savefig(output_path, dpi=100, bbox_inches='tight', format='png')
            plt.close(fig)
            return output_path
        except Exception as e:
            return ''

    def infer_single(
        self,
        image_path: str,
        model_key: str,
        sample_id: str = '',
    ) -> InferenceResult:
        """对单张图像执行推理"""
        model = self._model_instances.get(model_key)
        if model is None:
            raise ValueError(f'模型未加载: {model_key}')

        config = MODEL_REGISTRY[model_key]
        class_names = config.get('class_names', [])

        mask, proc_ms = model.segment(image_path)
        class_counts = compute_class_stats(mask)

        seg_output = SegmentationOutput(
            image_path=image_path,
            model_name=config['name'],
            model_id=model_key,
            mask=mask,
            shape=mask.shape,
            class_counts=class_counts,
            processing_time_ms=proc_ms,
        )

        walk_idx = compute_walkability(mask, class_names)

        return InferenceResult(
            image_path=image_path,
            sample_id=sample_id,
            model_name=config['name'],
            segmentation=seg_output,
            walkability=walk_idx,
            metrics={
                'processing_time_ms': proc_ms,
                'n_classes_used': len(class_counts),
            },
        )

    def infer_batch(
        self,
        image_dir: str,
        output_csv: str = None,
        output_json: str = None,
        checkpoint_file: str = None,
        resume: bool = True,
        verbose: bool = True,
    ) -> pd.DataFrame:
        """
        批量推理

        参数:
            image_dir: 图像目录
            output_csv: 结果CSV路径
            output_json: 结果JSON路径
            checkpoint_file: 断点文件路径
            resume: 是否跳过已处理文件
            verbose: 打印详细进度

        返回:
            结果 DataFrame
        """
        print('=' * 60)
        print('批量语义分割推理')
        print('=' * 60)
        print(f'  模型列表: {self.models}')
        print(f'  图像目录: {image_dir}')
        print(f'  输出目录: {self.output_dir}')
        print(f'  断点续传: {resume}')

        image_files = self._get_image_files(image_dir)
        print(f'\n  找到 {len(image_files)} 张图像')

        if len(image_files) == 0:
            print('[ERROR] 无有效图像文件')
            return pd.DataFrame()

        # 断点：已处理文件
        processed = set()
        if resume and checkpoint_file and os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                processed = set(data.get('processed', []))
                print(f'  从断点恢复: {len(processed)} 个已处理')
            except Exception:
                pass

        pending = [f for f in image_files if f not in processed]
        print(f'  待处理: {len(pending)} 张')
        print()

        # 执行推理
        all_records = []
        total_time = 0
        failed = 0

        try:
            from tqdm import tqdm
            iterator = tqdm(pending, desc='推理中')
        except ImportError:
            iterator = pending

        for img_path in iterator:
            img_hash = hashlib.md5(img_path.encode()).hexdigest()[:8]
            sample_id = Path(img_path).stem[:20]

            for model_key in self.models:
                if model_key not in self._model_instances:
                    continue

                try:
                    result = self.infer_single(img_path, model_key, sample_id)
                    all_records.append({
                        'image_path': img_path,
                        'sample_id': sample_id,
                        'model': result.model_name,
                        'model_key': model_key,
                        'SCR': result.walkability.scr,
                        'GVR': result.walkability.gvr,
                        'VVR': result.walkability.vvr,
                        'CSR': result.walkability.csr,
                        'pedestrian_density': result.walkability.pedestrian_density,
                        'proc_time_ms': result.segmentation.processing_time_ms,
                        'n_classes': len(result.segmentation.class_counts),
                    })
                    total_time += result.segmentation.processing_time_ms

                    # 保存 mask
                    if self.save_masks:
                        mask_name = f"{sample_id}_{model_key}_{img_hash}.png"
                        mask_path = os.path.join(MASKS_DIR, mask_name)
                        cv2.imwrite(mask_path, result.segmentation.mask.astype(np.uint8))

                    # 保存可视化
                    if self.save_vis:
                        vis_name = f"{sample_id}_{model_key}_{img_hash}_vis.png"
                        vis_path = os.path.join(RESULTS_DIR, vis_name)
                        self._visualize_mask(result.segmentation.mask, vis_path)

                    # 保存叠加图
                    if self.save_overlay:
                        overlay_name = f"{sample_id}_{model_key}_{img_hash}_overlay.png"
                        overlay_path = os.path.join(RESULTS_DIR, overlay_name)
                        self._generate_overlay(img_path, result.segmentation.mask, overlay_path)

                except Exception as e:
                    failed += 1
                    if verbose:
                        print(f'  [WARN] {model_key} 推理失败 {img_path}: {e}')

            # 更新断点
            processed.add(img_path)
            if checkpoint_file and len(processed) % 10 == 0:
                with open(checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump({'processed': list(processed), 'date': datetime.now().isoformat()}, f)

        # 保存断点
        if checkpoint_file:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump({'processed': list(processed), 'date': datetime.now().isoformat()}, f)

        # 构建 DataFrame
        df = pd.DataFrame(all_records)

        print()
        print('=' * 60)
        print('推理完成')
        print(f'  总处理: {len(all_records)} 条记录')
        print(f'  成功: {len(all_records) - failed * len(self.models)}')
        print(f'  失败: {failed}')
        print(f'  总耗时: {total_time/1000:.1f}s')
        if len(all_records) > 0:
            print(f'  平均: {total_time/len(all_records):.1f}ms/图')

        if output_csv and len(df) > 0:
            df.to_csv(output_csv, index=False, encoding='utf-8-sig')
            print(f'  CSV已保存: {output_csv}')

        if output_json and len(df) > 0:
            df.to_json(output_json, orient='records', force_ascii=False, indent=2)
            print(f'  JSON已保存: {output_json}')

        return df


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='GPU语义分割批量推理',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 推荐配置 - 3模型并行
  python segment_inference.py --input images/ --models deeplabv3_resnet50 nvidia_mit_b0 intel_deeplabv3

  # 高精度 - 5模型
  python segment_inference.py --input images/ --models deeplabv3_resnet101 segformer_b2 nvidia_mit_b4

  # 最快速 - 单模型
  python segment_inference.py --input images/ --models deeplabv3_mobilenet

  # 列出所有模型
  python segment_inference.py --list-models
'''
    )
    parser.add_argument('--input', '--image-dir', default=IMAGES_DIR,
                        help='图像目录 (默认: dl_pipeline/images/raw)')
    parser.add_argument('--models', '--model', nargs='+', default=None,
                        help='使用的模型列表 (默认: deeplabv3_resnet50 nvidia_mit_b0)')
    parser.add_argument('--output-csv', default=None,
                        help='输出CSV路径')
    parser.add_argument('--output-json', default=None,
                        help='输出JSON路径')
    parser.add_argument('--output-dir', default=RESULTS_DIR,
                        help='可视化输出目录')
    parser.add_argument('--device', default='auto',
                        choices=['auto', 'cuda', 'cpu'],
                        help='计算设备 (默认: auto)')
    parser.add_argument('--no-masks', action='store_true',
                        help='不保存分割mask')
    parser.add_argument('--no-vis', action='store_true',
                        help='不保存可视化')
    parser.add_argument('--no-resume', action='store_true',
                        help='禁用断点续传')
    parser.add_argument('--list-models', action='store_true',
                        help='列出所有可用模型')
    parser.add_argument('--checkpoint', default=None,
                        help='断点文件路径')

    args = parser.parse_args()

    # 列出模型
    if args.list_models:
        print('=' * 60)
        print('可用分割模型')
        print('=' * 60)
        for key, cfg in MODEL_REGISTRY.items():
            src = cfg['source']
            speed = cfg.get('speed', '?')
            ds = cfg.get('pretrained_dataset', '')
            notes = cfg.get('notes', '')
            print(f'  {key:25s} [{src:12s}] {speed:8s} {ds:12s} {notes}')
        return

    # 默认模型
    if args.models is None:
        args.models = ['deeplabv3_resnet50', 'nvidia_mit_b0', 'intel_deeplabv3']

    # 输出路径
    if args.output_csv is None:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output_csv = os.path.join(CHECKPOINT_DIR, f'segmentation_results_{ts}.csv')
    if args.output_json is None:
        args.output_json = args.output_csv.replace('.csv', '.json')
    if args.checkpoint is None:
        args.checkpoint = os.path.join(CHECKPOINT_DIR, 'segmentation_checkpoint.json')

    # 创建引擎
    engine = SegmentationInferenceEngine(
        models=args.models,
        device=args.device,
        output_dir=args.output_dir,
        save_masks=not args.no_masks,
        save_vis=not args.no_vis,
    )

    # 加载模型
    engine.load_models()

    if len(engine._model_instances) == 0:
        print('[ERROR] 没有成功加载任何模型')
        print('请检查 PyTorch / torchvision / transformers 是否正确安装')
        sys.exit(1)

    # 批量推理
    df = engine.infer_batch(
        image_dir=args.input,
        output_csv=args.output_csv,
        output_json=args.output_json,
        checkpoint_file=args.checkpoint,
        resume=not args.no_resume,
    )

    # 打印统计
    if len(df) > 0:
        print('\n统计摘要:')
        print(f'  SCR  均值: {df["SCR"].mean():.3f}')
        print(f'  GVR  均值: {df["GVR"].mean():.3f}')
        print(f'  VVR  均值: {df["VVR"].mean():.3f}')
        print(f'  CSR  均值: {df["CSR"].mean():.3f}')
        print(f'  行人密度均值: {df["pedestrian_density"].mean():.3f}')
        print(f'\n按模型分组:')
        for model, grp in df.groupby('model'):
            print(f'  {model}:')
            print(f'    SCR={grp["SCR"].mean():.3f} GVR={grp["GVR"].mean():.3f} VVR={grp["VVR"].mean():.3f}')


if __name__ == '__main__':
    main()
