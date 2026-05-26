# -*- coding: utf-8 -*-
"""
=============================================================================
步行环境深度学习感知模块 — Walkability Deep Learning Perception
用于南山区街景影像的 YOLO行人检测 + 语义分割分析

=============================================================================

本模块实现四项核心步行环境指标的计算:

  1. SCR (Sidewalk Coverage Ratio) — 人行道覆盖率
     公式: SCR = 人行道像素数 / 总像素数
     来源: 语义分割 (DeepLabV3+)
  
  2. BFD (Barrier-free Facility Density) — 无障碍设施密度
     公式: BFD = 检测到的无障碍设施数 / 影像覆盖面积
     来源: YOLO目标检测 (wheelchair, crutch, blind_stick等)
  
  3. EWW (Effective Walkable Width) — 步行道有效宽度
     公式: EWW = 语义分割估算的人行道可用宽度(米)
     来源: 语义分割 + 透视投影校正
     阈值: <2m = 严重不足, 2-3m = 不足, >3m = 充足
  
  4. SVI (Street Vitality Index) — 街道活力指数
     公式: SVI = 0.4×(行人密度/10) + 0.3×绿化覆盖率 + 0.3×过街设施
     来源: YOLO行人计数 + 语义分割 (树/绿化 + 人行横道)
  
  综合步行环境评分:
  WES = w1×SCR + w2×BFD + w3×min(EWW/4,1) + w4×SVI
  其中 w1=0.30, w2=0.25, w3=0.25, w4=0.20

=============================================================================
依赖:
  pip install ultralytics transformers torch torchvision pillow opencv-python

模型:
  YOLO:   ultralytics/yolov8 (yolov8n.pt 最轻量版)
  Seg:    Intel/deeplabv3-base (HuggingFace, ~160MB)
  Seg alt: segformer-b0 (更轻量 ~14MB)

=============================================================================
"""

import os
import sys
import warnings
warnings.filterwarnings('ignore')

from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
import hashlib

import numpy as np
import pandas as pd

# ==========================
# 模型配置
# ==========================

# YOLO目标检测类别 (COCO预训练 + 自定义)
YOLO_CLASSES = {
    0: 'person',
    1: 'bicycle',
    2: 'car',
    3: 'motorcycle',
    4: 'airplane',
    5: 'bus',
    6: 'train',
    7: 'truck',
    8: 'boat',
    9: 'traffic light',
    10: 'fire hydrant',
    11: 'stop sign',
    12: 'parking meter',
    13: 'bench',
    14: 'bird',
    15: 'cat',
    16: 'dog',
    17: 'horse',
    18: 'sheep',
    19: 'cow',
    20: 'elephant',
    21: 'bear',
    22: 'zebra',
    23: 'giraffe',
    24: 'backpack',
    25: 'umbrella',
    26: 'handbag',
    27: 'tie',
    28: 'suitcase',
    29: 'frisbee',
    30: 'skis',
    31: 'snowboard',
    32: 'sports ball',
    33: 'kite',
    34: 'baseball bat',
    35: 'baseball glove',
    36: 'skateboard',
    37: 'surfboard',
    38: 'tennis racket',
    39: 'bottle',
    40: 'wine glass',
    41: 'cup',
    42: 'fork',
    43: 'knife',
    44: 'spoon',
    45: 'bowl',
    46: 'banana',
    47: 'apple',
    48: 'sandwich',
    49: 'orange',
    50: 'broccoli',
    51: 'carrot',
    52: 'hot dog',
    53: 'pizza',
    54: 'donut',
    55: 'cake',
    56: 'chair',
    57: 'couch',
    58: 'potted plant',
    59: 'bed',
    60: 'dining table',
    61: 'toilet',
    62: 'tv',
    63: 'laptop',
    64: 'mouse',
    65: 'remote',
    66: 'keyboard',
    67: 'cell phone',
    68: 'microwave',
    69: 'oven',
    70: 'toaster',
    71: 'sink',
    72: 'refrigerator',
    73: 'book',
    74: 'clock',
    75: 'vase',
    76: 'scissors',
    77: 'teddy bear',
    78: 'hair drier',
    79: 'toothbrush',
    # --- 自定义无障碍设施类别 (需要微调模型或使用开源数据集) ---
    80: 'wheelchair',
    81: 'crutch',
    82: 'walking_cane',      # 拐杖/盲杖
    83: 'stroller',           # 婴儿车
    84: 'guide_dog',         # 导盲犬
    85: 'blind_stick',       # 导盲杖
    86: 'ramp',              # 轮椅坡道
    87: 'handrail',         # 扶手
    88: 'tactile_paving',    # 盲道
    89: 'elevator_button',   # 电梯按钮
    90: 'access_ramp',       # 无障碍通道
}

# 语义分割类别 (ADE20K / 自定义映射)
SEGMENT_CLASSES = {
    0: 'road',
    1: 'sidewalk',
    2: 'building',
    3: 'wall',
    4: 'fence',
    5: 'pole',
    6: 'traffic_light',
    7: 'traffic_sign',
    8: 'vegetation',
    9: 'terrain',
    10: 'person',
    11: 'sky',
    12: 'car',
    13: 'pedestrian',
    14: 'bicycle',
    15: 'motorcycle',
    16: 'bus',
    17: 'truck',
    18: 'train',
    19: 'boat',
    # --- 自定义类别 ---
    20: 'curb',              # 路缘石
    21: 'crosswalk',         # 人行横道
    22: 'tree',              # 树木
    23: 'bench',             # 座椅
    24: 'lamp',              # 路灯
    25: 'barrier',           # 物理障碍物 (施工围挡/地摊)
    26: 'stairs',            # 楼梯
    27: 'ramp',              # 坡道
    28: 'drainage',          # 排水沟
    29: 'parking',           # 停车位
}

# DeepLabV3+ 原始类别数 (ADE20K=150类)
DEEPLABV3_NUM_CLASSES = 150

# 指标权重
WES_WEIGHTS = {
    'scr': 0.30,
    'bfd': 0.25,
    'eww': 0.25,
    'svi': 0.20,
}


# ==========================
# 数据结构
# ==========================

@dataclass
class DetectionResult:
    """YOLO检测结果"""
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2 (像素)
    area_ratio: float = 0.0  # 边界框占影像面积比


@dataclass
class SegmentationResult:
    """语义分割结果"""
    mask: np.ndarray  # 高度×宽度, 每个像素的类别ID
    image_shape: Tuple[int, int]  # (H, W)
    
    def get_coverage(self, class_ids: List[int]) -> float:
        """计算指定类别的像素覆盖率"""
        mask_flat = self.mask.flatten()
        total_pixels = len(mask_flat)
        covered = sum((self.mask == cid).sum() for cid in class_ids)
        return covered / total_pixels


@dataclass
class WalkabilityMetrics:
    """四项步行环境指标"""
    scr: float      # Sidewalk Coverage Ratio [0,1]
    bfd: float       # Barrier-free Facility Density [0,1]
    eww: float       # Effective Walkable Width [0,5] 米
    svi: float       # Street Vitality Index [0,1]
    
    # 辅助信息
    person_count: int = 0
    accessible_objs: int = 0
    sidewalk_pixels: int = 0
    total_pixels: int = 0
    image_path: Optional[str] = None
    lng: Optional[float] = None
    lat: Optional[float] = None
    
    def to_dict(self) -> Dict[str, float]:
        return {
            'SCR': self.scr,
            'BFD': self.bfd,
            'EWW': self.eww,
            'SVI': self.svi,
            'person_count': self.person_count,
            'accessible_objs': self.accessible_objs,
        }


# ==========================
# YOLO 行人检测
# ==========================

class YOLOWalkabilityDetector:
    """
    基于YOLOv8的步行环境目标检测器。
    
    功能:
    1. 行人检测 (person)
    2. 无障碍设施检测 (wheelchair, crutch, blind_stick, ramp等)
    3. 步行障碍物检测 (barrier, fence, parked_car等)
    4. 设施完整性评估
    """
    
    def __init__(
        self,
        model_name: str = 'yolov8n.pt',
        device: Optional[str] = None,
        conf_thresh: float = 0.25,
    ):
        """
        初始化YOLO检测器。
        
        参数:
            model_name: YOLO模型名 (yolov8n.pt = nano最轻, yolov8s.pt = small)
            device: 'cuda' | 'cpu' | None (自动选择)
            conf_thresh: 置信度阈值
        """
        self.conf_thresh = conf_thresh
        
        # 自动选择设备
        if device is None:
            try:
                import torch
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
            except ImportError:
                device = 'cpu'
        
        self.device = device
        self.model_name = model_name
        
        # 延迟加载模型
        self._model = None
    
    @property
    def model(self):
        """延迟加载YOLO模型"""
        if self._model is None:
            from ultralytics import YOLO
            self._model = YOLO(self.model_name)
            if self.device == 'cuda':
                self._model.to('cuda')
            print(f"  [YOLO] 模型加载完成: {self.model_name} on {self.device}")
        return self._model
    
    def detect(self, image_path: str) -> List[DetectionResult]:
        """
        对单张影像执行目标检测。
        
        返回:
            DetectionResult列表
        """
        results = self.model(image_path, verbose=False, conf=self.conf_thresh)
        
        detections = []
        if len(results) == 0:
            return detections
        
        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            return detections
        
        H, W = r.orig_shape
        total_area = H * W
        
        for box in r.boxes:
            cls_id = int(box.cls.item())
            conf = float(box.conf.item())
            
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            bbox_area = (x2 - x1) * (y2 - y1)
            area_ratio = bbox_area / total_area
            
            detections.append(DetectionResult(
                class_id=cls_id,
                class_name=YOLO_CLASSES.get(cls_id, f'unknown_{cls_id}'),
                confidence=conf,
                bbox=(float(x1), float(y1), float(x2), float(y2)),
                area_ratio=area_ratio,
            ))
        
        return detections
    
    def compute_accessibility_score(self, detections: List[DetectionResult]) -> Tuple[int, int, float]:
        """
        基于检测结果计算无障碍设施相关指标。
        
        返回:
            (行人数量, 无障碍设施数量, 障碍物评分)
        
        评分逻辑:
        - 检测到wheelchair/crutch/ramp等 → BFD增加
        - 检测到barrier/fence等 → 障碍评分降低
        - 检测到parked_car占据人行道 → EWW减少
        """
        person_count = sum(1 for d in detections if d.class_id == 0)
        
        # 无障碍设施检测 (自定义类别80-90)
        accessible_classes = {80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90}
        accessible_objs = [d for d in detections if d.class_id in accessible_classes]
        
        # 步行障碍物检测
        obstacle_classes = {25, 4, 5}  # barrier, fence, wall
        obstacles = [d for d in detections if d.class_id in obstacle_classes]
        
        # 占据人行道的车辆 (车辆类别的边界框低于图像下半部分)
        # 注: 需结合语义分割的人行道mask综合判断
        parked_vehicle_classes = {2, 3, 7, 12, 16, 17}  # car, motorcycle, truck, bus等
        vehicles = [d for d in detections if d.class_id in parked_vehicle_classes]
        
        return person_count, len(accessible_objs), len(obstacles), len(vehicles)


# ==========================
# 语义分割
# ==========================

class SemanticSegmenter:
    """
    基于DeepLabV3+的语义分割器。
    
    从影像中分割出人行道、建筑物、树木、车辆等类别，
    用于计算SCR(人行道覆盖率)、EWW(有效宽度)等指标。
    
    也支持更轻量的SegFormer模型作为备选。
    """
    
    def __init__(
        self,
        model_name: str = 'Intel/deeplabv3-base',
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        self.model_name = model_name
        
        if device is None:
            try:
                import torch
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
            except ImportError:
                device = 'cpu'
        self.device = device
        self.cache_dir = cache_dir
        
        self._processor = None
        self._model = None
    
    @property
    def processor(self):
        if self._processor is None:
            from transformers import AutoImageProcessor
            self._processor = AutoImageProcessor.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
            )
        return self._processor
    
    @property
    def model(self):
        if self._model is None:
            from transformers import AutoModelForSemanticSegmentation
            self._model = AutoModelForSemanticSegmentation.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
            )
            self._model.to(self.device)
            self._model.eval()
            print(f"  [Seg] 模型加载完成: {self.model_name} on {self.device}")
        return self._model
    
    def segment(self, image_path: str) -> SegmentationResult:
        """
        对单张影像执行语义分割。
        
        返回:
            SegmentationResult
        """
        from PIL import Image
        import torch
        
        image = Image.open(image_path).convert('RGB')
        H, W = image.size[1], image.size[0]  # PIL: (W, H) → numpy: (H, W)
        
        inputs = self.processor(images=image, return_tensors='pt')
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # 解析输出
        logits = outputs.logits  # [1, num_classes, H, W]
        
        # 上采样到原图尺寸
        logits = torch.nn.functional.interpolate(
            logits,
            size=(H, W),
            mode='bilinear',
            align_corners=False,
        )
        
        pred_mask = logits.argmax(dim=1)[0].cpu().numpy()
        
        return SegmentationResult(
            mask=pred_mask,
            image_shape=(H, W),
        )
    
    def estimate_sidewalk_width(self, seg_result: SegmentationResult) -> float:
        """
        估算人行道的有效宽度(米)。
        
        方法:
        1. 识别人行道在图像中的纵向分布
        2. 假设地面视角透视投影，估算实际物理宽度
        3. 典型假设: 图像下半部分对应近处(0-5m),
           上半部分对应远处(5-20m)
        
        返回:
            EWW (米)
        """
        mask = seg_result.mask
        H, W = mask.shape
        
        # 人行道类别ID
        sidewalk_ids = {1}  # sidewalk
        
        # 纵向扫描：找出人行道在垂直方向上的延伸范围
        has_sidewalk = np.isin(mask, list(sidewalk_ids))
        
        if not has_sidewalk.any():
            return 0.0
        
        # 行扫描：每行中人行道像素占比
        row_coverages = has_sidewalk.sum(axis=1) / W
        
        # 透视校正：远处(图像上方)权重低，近处(图像下方)权重高
        # 假设视锥投影，近处约为图像下半部分
        perspective_weights = np.linspace(0.2, 1.0, H)  # 上→下: 0.2→1.0
        
        # 加权平均宽度估计
        weighted_coverage = (row_coverages * perspective_weights).sum()
        total_weight = perspective_weights.sum()
        
        # 像素宽度→物理宽度 (假设影像FOV=90°, 人行道宽度~W像素对应4m)
        # 实际物理宽度 = 人行道像素宽度 × (实际FOV宽度 / 影像像素数)
        pixel_width = row_coverages.mean() * W
        
        # 透视校正后的估算
        # 近处5m范围(图像下半部分)平均宽度
        near_rows = has_sidewalk[H//2:, :]
        if near_rows.any():
            near_pixel_width = near_rows.sum(axis=1).mean()
            # 假设近处5m对应图像下半部分，影像FOV=4m宽
            eww_m = near_pixel_width * (4.0 / W)
            return float(eww_m)
        
        # 备选: 直接估算
        avg_sidewalk_pixels = row_coverages.mean() * W
        eww_approx = avg_sidewalk_pixels * (3.0 / W)  # 假设3m真实宽度对应W像素
        return float(np.clip(eww_approx, 0, 5))


# ==========================
# 综合感知
# ==========================

class WalkabilityPerception:
    """
    综合步行环境感知器。
    
    整合YOLO检测 + 语义分割，计算四项步行环境指标
    并输出综合步行环境评分(WES)。
    
    融合架构:
    
    街景影像
        ↓
    ┌──────────────────────────────────────┐
    │  YOLOv8 行人检测                       │
    │  检测: person, wheelchair, barrier...   │
    └─────────────┬──────────────────────────┘
                  ↓
    ┌──────────────────────────────────────┐
    │  DeepLabV3+ 语义分割                  │
    │  分割: sidewalk, building, tree...    │
    └─────────────┬──────────────────────────┘
                  ↓
    ┌──────────────────────────────────────┐
    │  四项指标计算                          │
    │  SCR + BFD + EWW + SVI               │
    └─────────────┬──────────────────────────┘
                  ↓
    ┌──────────────────────────────────────┐
    │  WES综合评分 (0-10)                   │
    │  WES = 0.30×SCR + 0.25×BFD         │
    │      + 0.25×min(EWW/4,1)            │
    │      + 0.20×SVI                     │
    └──────────────────────────────────────┘
    """
    
    def __init__(
        self,
        yolo_model: str = 'yolov8n.pt',
        seg_model: str = 'Intel/deeplabv3-base',
        device: Optional[str] = None,
    ):
        self.yolo = YOLOWalkabilityDetector(
            model_name=yolo_model,
            device=device,
        )
        self.segmenter = SemanticSegmenter(
            model_name=seg_model,
            device=device,
        )
    
    def perceive(
        self,
        image_path: str,
        lng: Optional[float] = None,
        lat: Optional[float] = None,
        return_details: bool = False,
    ) -> Union[WalkabilityMetrics, Tuple[WalkabilityMetrics, Dict]]:
        """
        对单张街景影像执行完整步行环境感知。
        
        参数:
            image_path: 影像路径
            lng, lat: 位置坐标(可选)
            return_details: 是否返回详细信息
        
        返回:
            WalkabilityMetrics, 或 (WalkabilityMetrics, details_dict)
        """
        H, W = None, None
        
        # Step 1: 语义分割 (先做，因为YOLO也可复用同一影像)
        try:
            seg_result = self.segmenter.segment(image_path)
            H, W = seg_result.image_shape
        except Exception as e:
            print(f"  [WARN] 语义分割失败: {e}")
            # 使用默认空结果
            empty_mask = np.zeros((300, 600), dtype=np.uint8)
            seg_result = SegmentationResult(mask=empty_mask, image_shape=(300, 600))
            H, W = 300, 600
        
        # Step 2: YOLO检测
        try:
            detections = self.yolo.detect(image_path)
        except Exception as e:
            print(f"  [WARN] YOLO检测失败: {e}")
            detections = []
        
        # Step 3: 计算四项指标
        metrics = self._compute_metrics(
            seg_result, detections, H, W, image_path, lng, lat
        )
        
        # Step 4: 综合评分
        wes = self.compute_wes(metrics)
        metrics.wes_score = wes
        
        if return_details:
            details = {
                'detections': detections,
                'seg_result': seg_result,
            }
            return metrics, details
        
        return metrics
    
    def _compute_metrics(
        self,
        seg_result: SegmentationResult,
        detections: List[DetectionResult],
        H: int, W: int,
        image_path: str,
        lng: Optional[float],
        lat: Optional[float],
    ) -> WalkabilityMetrics:
        """内部: 计算四项指标"""
        
        # === SCR ===
        # 人行道像素 / 总像素
        sidewalk_ids = {1, 20}  # sidewalk + curb
        has_sw = np.isin(seg_result.mask, list(sidewalk_ids))
        sw_pixels = has_sw.sum()
        total_pixels = seg_result.mask.size
        SCR = sw_pixels / total_pixels
        
        # === BFD ===
        # 统计无障碍设施
        accessible_classes = {80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90}
        accessible_objs = [d for d in detections if d.class_id in accessible_classes]
        
        # 假设影像覆盖约15m×15m范围
        coverage_area_m2 = 15 * 15
        BFD = len(accessible_objs) / coverage_area_m2
        BFD = np.clip(BFD / 0.2, 0, 1)  # 归一化: 0.2个设施/m² = 满分
        
        # === EWW ===
        # 估算人行道有效宽度
        eww_raw = self.segmenter.estimate_sidewalk_width(seg_result)
        EWW = np.clip(eww_raw, 0, 5)
        
        # === SVI ===
        # 行人数量
        person_count = sum(1 for d in detections if d.class_id == 0)
        
        # 绿化覆盖
        tree_ids = {8, 22}  # vegetation + tree
        tree_coverage = np.isin(seg_result.mask, list(tree_ids)).sum() / total_pixels
        
        # 过街设施
        crosswalk_ids = {21}  # crosswalk
        cw_coverage = np.isin(seg_result.mask, list(crosswalk_ids)).sum() / total_pixels
        
        SVI = 0.4 * min(person_count / 10, 1) + 0.3 * tree_coverage + 0.3 * cw_coverage
        SVI = np.clip(SVI, 0, 1)
        
        return WalkabilityMetrics(
            scr=float(SCR),
            bfd=float(BFD),
            eww=float(EWW),
            svi=float(SVI),
            person_count=person_count,
            accessible_objs=len(accessible_objs),
            sidewalk_pixels=int(sw_pixels),
            total_pixels=int(total_pixels),
            image_path=image_path,
            lng=lng,
            lat=lat,
        )
    
    @staticmethod
    def compute_wes(metrics: WalkabilityMetrics) -> float:
        """
        计算综合步行环境评分 (Walkability Environment Score)。
        
        公式: WES = 0.30×SCR + 0.25×BFD + 0.25×min(EWW/4,1) + 0.20×SVI
        范围: [0, 10]
        """
        scr = np.clip(metrics.scr, 0, 1)
        bfd = np.clip(metrics.bfd, 0, 1)
        eww_norm = np.clip(metrics.eww / 4.0, 0, 1)  # 4m为满分
        svi = np.clip(metrics.svi, 0, 1)
        
        wes = (
            WES_WEIGHTS['scr'] * scr +
            WES_WEIGHTS['bfd'] * bfd +
            WES_WEIGHTS['eww'] * eww_norm +
            WES_WEIGHTS['svi'] * svi
        ) * 10  # 放大到0-10
        
        return float(np.clip(wes, 0, 10))


# ==========================
# 批量处理
# ==========================

def batch_perceive(
    image_dir: str,
    output_csv: str,
    metrics_csv: Optional[str] = None,
    yolo_model: str = 'yolov8n.pt',
    seg_model: str = 'Intel/deeplabv3-base',
    device: Optional[str] = None,
    progress: bool = True,
) -> pd.DataFrame:
    """
    批量处理街景影像目录。
    
    参数:
        image_dir: 影像目录
        output_csv: 结果输出CSV路径
        metrics_csv: 采样点+指标CSV (可选，合并位置信息)
        yolo_model: YOLO模型
        seg_model: 语义分割模型
        device: 'cuda'|'cpu'|None
        progress: 是否显示进度
    
    返回:
        结果DataFrame
    """
    print("=" * 60)
    print("批量步行环境感知")
    print("=" * 60)
    
    # 初始化感知器
    print(f"\n初始化模型...")
    perceiver = WalkabilityPerception(
        yolo_model=yolo_model,
        seg_model=seg_model,
        device=device,
    )
    
    # 收集影像
    valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    image_files = []
    for root, _, files in os.walk(image_dir):
        for f in files:
            if Path(f).suffix.lower() in valid_exts:
                image_files.append(os.path.join(root, f))
    
    print(f"  找到 {len(image_files)} 张影像")
    
    if len(image_files) == 0:
        print("  [ERROR] 目录中无有效影像文件")
        return pd.DataFrame()
    
    # 批量处理
    results = []
    
    if progress:
        try:
            from tqdm import tqdm
            iterator = tqdm(image_files, desc="步行环境感知")
        except ImportError:
            print("请安装 tqdm: pip install tqdm")
            iterator = image_files
    else:
        iterator = image_files
    
    for img_path in iterator:
        try:
            metrics = perceiver.perceive(img_path)
            result = metrics.to_dict()
            result['image_path'] = img_path
            result['filename'] = os.path.basename(img_path)
            results.append(result)
        except Exception as e:
            print(f"  [WARN] 处理失败 {img_path}: {e}")
            results.append({
                'image_path': img_path,
                'filename': os.path.basename(img_path),
                'SCR': np.nan, 'BFD': np.nan, 'EWW': np.nan, 'SVI': np.nan,
                'person_count': 0, 'accessible_objs': 0,
                'wes_score': np.nan,
            })
    
    df = pd.DataFrame(results)
    
    # 保存结果
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"\n  结果已保存: {output_csv}")
    
    # 统计
    print(f"\n  统计摘要:")
    print(f"  WES: mean={df['wes_score'].mean():.2f}, std={df['wes_score'].std():.2f}")
    print(f"  SCR: mean={df['SCR'].mean():.3f}")
    print(f"  BFD: mean={df['BFD'].mean():.3f}")
    print(f"  EWW: mean={df['EWW'].mean():.2f}m")
    print(f"  SVI: mean={df['SVI'].mean():.3f}")
    print(f"  平均行人: {df['person_count'].mean():.1f}人/张")
    
    return df


# ==========================
# 主流程
# ==========================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='步行环境深度学习感知')
    parser.add_argument('--input', required=True, help='影像目录或单张影像')
    parser.add_argument('--output', default='walkability_results.csv', help='输出CSV')
    parser.add_argument('--yolo', default='yolov8n.pt', help='YOLO模型')
    parser.add_argument('--seg', default='Intel/deeplabv3-base', help='语义分割模型')
    parser.add_argument('--device', default=None, help='cuda/cpu')
    
    args = parser.parse_args()
    
    if os.path.isdir(args.input):
        batch_perceive(
            image_dir=args.input,
            output_csv=args.output,
            yolo_model=args.yolo,
            seg_model=args.seg,
            device=args.device,
        )
    else:
        perceiver = WalkabilityPerception(args.yolo, args.seg, args.device)
        metrics = perceiver.perceive(args.input)
        print(f"\n步行环境指标:")
        print(f"  SCR: {metrics.scr:.3f}")
        print(f"  BFD: {metrics.bfd:.3f}")
        print(f"  EWW: {metrics.eww:.2f}m")
        print(f"  SVI: {metrics.svi:.3f}")
        print(f"  WES: {metrics.wes_score:.2f}/10")
