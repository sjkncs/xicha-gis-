# -*- coding: utf-8 -*-
"""
GPU 语义分割训练管线

适配场景:
  A. 有标注数据: 真实分割标注训练（Pascal VOC / Cityscapes / ADE20K）
  B. 无标注数据: 伪标签 (Pseudo-labeling) + 预训练模型蒸馏
  C. 混合场景: 少量标注 + 大量伪标签

训练策略:
  1. 多loss支持: CrossEntropy + Dice + Focal
  2. 数据增强: 随机翻转/裁剪/亮度/饱和度/对比度
  3. 断点续训: 从 checkpoint 恢复训练
  4. 多尺度训练: 512x512 / 768x768 / 1024x1024
  5. 学习率调度: Cosine Annealing + Warmup

可用模型架构（U-Net, SegFormer, DeepLabV3+）:
  - U-Net: encoder可选 ResNet34/50, MobileNet, EfficientNet
  - SegFormer: mit_b0/b1/b2/b3
  - DeepLabV3+: ResNet50/101 backbone
  - UPerNet: 通用场景分割

数据集格式:
  images/: *.jpg/*.png
  masks/:  *.png (单通道, 每像素为类别ID)
  或 ADE20K 格式: objectInfo166.txt 类别定义
"""

import os
import sys
import json
import time
import math
import random
import hashlib
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
import copy

import numpy as np
import pandas as pd

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    from torch.optim import AdamW, SGD
    from torch.optim.lr_scheduler import CosineAnnealingLR, LinearLR, SequentialLR
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print('[WARN] PyTorch 未安装')

try:
    import torchvision
    from torchvision import transforms
    TORCHVISION_AVAILABLE = True
except ImportError:
    TORCHVISION_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


# ============================================================
# 路径配置
# ============================================================

BASE_DIR = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility'
DATA_DIR = os.path.join(BASE_DIR, 'data', 'dl_pipeline')
IMAGES_DIR = os.path.join(DATA_DIR, 'images', 'raw')
MASKS_DIR = os.path.join(DATA_DIR, 'images', 'masks')
CKPT_DIR = os.path.join(DATA_DIR, 'checkpoints')
os.makedirs(CKPT_DIR, exist_ok=True)


# ============================================================
# 数据集定义
# ============================================================

@dataclass
class DatasetConfig:
    """数据集配置"""
    name: str
    root: str
    train_split: float = 0.8
    val_split: float = 0.1
    test_split: float = 0.1
    num_classes: int = 20
    image_size: Tuple[int, int] = (512, 512)
    class_names: List[str] = field(default_factory=list)

    # 类别调色板 (R, G, B)
    palette: List[Tuple[int, int, int]] = field(default_factory=lambda: [
        (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128),
        (128, 0, 128), (0, 128, 128), (128, 128, 128), (64, 0, 0),
        (192, 0, 0), (64, 128, 0), (192, 128, 0), (64, 0, 128),
        (192, 0, 128), (64, 128, 128), (192, 128, 128), (0, 64, 0),
        (128, 64, 0), (0, 192, 0), (128, 64, 0), (0, 64, 128),
    ])


class StreetViewDataset(Dataset):
    """
    街景分割数据集

    支持:
    - 自定义图像/mask 目录
    - 内置 Cityscapes / ADE20K / Pascal VOC 格式
    - 自动数据增强（训练集）
    - 伪标签模式
    """

    def __init__(
        self,
        image_dir: str,
        mask_dir: Optional[str] = None,
        dataset_config: DatasetConfig = None,
        split: str = 'train',
        augment: bool = True,
        image_size: Tuple[int, int] = (512, 512),
    ):
        self.image_dir = image_dir
        self.mask_dir = mask_dir
        self.split = split
        self.augment = augment and (split == 'train')
        self.image_size = image_size

        if dataset_config is None:
            dataset_config = DatasetConfig(
                name='custom', root=image_dir, num_classes=20,
                image_size=image_size
            )
        self.config = dataset_config

        # 加载文件列表
        self.image_files = self._load_image_files()

        # 数据增强
        self._setup_augmentations()

    def _load_image_files(self) -> List[str]:
        """加载图像文件列表"""
        valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        files = []
        if os.path.exists(self.image_dir):
            for f in os.listdir(self.image_dir):
                if Path(f).suffix.lower() in valid_exts:
                    files.append(os.path.join(self.image_dir, f))
        return sorted(files)

    def _setup_augmentations(self):
        """设置数据增强"""
        if not self.augment:
            return

        import torchvision.transforms as T

        self.img_transform = T.Compose([
            T.RandomHorizontalFlip(p=0.5),
            T.RandomVerticalFlip(p=0.2),
            T.RandomResizedCrop(
                self.image_size,
                scale=(0.8, 1.2),
                ratio=(0.9, 1.1),
                interpolation=transforms.InterpolationMode.BILINEAR,
            ),
            T.ColorJitter(
                brightness=0.2,
                contrast=0.2,
                saturation=0.2,
                hue=0.05,
            ),
            T.RandomGrayscale(p=0.1),
        ])

        self.mask_transform = T.Compose([
            T.RandomHorizontalFlip(p=0.5),
            T.RandomVerticalFlip(p=0.2),
            T.RandomResizedCrop(
                self.image_size,
                scale=(0.8, 1.2),
                ratio=(0.9, 1.1),
                interpolation=transforms.InterpolationMode.NEAREST,
            ),
        ])

    def __len__(self) -> int:
        return len(self.image_files)

    def _load_image(self, path: str) -> np.ndarray:
        if CV2_AVAILABLE:
            img = cv2.imread(path)
            if img is not None:
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        from PIL import Image
        return np.array(Image.open(path).convert('RGB'))

    def _load_mask(self, path: str) -> np.ndarray:
        if CV2_AVAILABLE:
            mask = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if mask is not None:
                return mask
        from PIL import Image
        return np.array(Image.open(path).convert('L'))

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        img_path = self.image_files[idx]
        img = self._load_image(img_path)

        # 加载mask
        if self.mask_dir:
            mask_name = Path(img_path).stem + '.png'
            mask_path = os.path.join(self.mask_dir, mask_name)
            if os.path.exists(mask_path):
                mask = self._load_mask(mask_path)
            else:
                mask = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
        else:
            mask = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)

        # 数据增强
        if self.augment:
            # PIL 格式进行增强
            from PIL import Image as PILImage
            img_pil = PILImage.fromarray(img)
            mask_pil = PILImage.fromarray(mask)

            img_pil = self.img_transform(img_pil)
            mask_pil = self.mask_transform(mask_pil)

            img = np.array(img_pil)
            mask = np.array(mask_pil)

        # 缩放到目标尺寸
        if img.shape[:2] != self.image_size:
            if CV2_AVAILABLE:
                img = cv2.resize(img, (self.image_size[1], self.image_size[0]),
                                interpolation=cv2.INTER_LINEAR)
                mask = cv2.resize(mask, (self.image_size[1], self.image_size[0]),
                                interpolation=cv2.INTER_NEAREST)

        # 转为张量
        img_tensor = torch.from_numpy(img).permute(2, 0, 1).float() / 255.0
        mask_tensor = torch.from_numpy(mask).long()

        # ImageNet 标准化
        mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
        img_tensor = (img_tensor - mean) / std

        return img_tensor, mask_tensor


# ============================================================
# 模型定义
# ============================================================

class SegmentationModelWrapper(nn.Module):
    """
    统一分割模型包装器
    支持多种分割架构
    """

    supported_models = {
        'unet': 'U-Net (ResNet34 Encoder)',
        'deeplabv3': 'DeepLabV3+ (ResNet50)',
        'unetpp': 'U-Net++',
        'pspnet': 'PSPNet',
        'segformer': 'SegFormer',
        'hrnet': 'HRNet',
    }

    def __init__(
        self,
        model_name: str = 'unet',
        encoder: str = 'resnet34',
        num_classes: int = 20,
        pretrained: bool = True,
        aux_loss: bool = True,
    ):
        super().__init__()
        self.model_name = model_name
        self.num_classes = num_classes
        self.aux_loss = aux_loss

        if model_name == 'unet':
            self._build_unet(encoder, num_classes, pretrained)
        elif model_name == 'deeplabv3':
            self._build_deeplabv3(encoder, num_classes, pretrained)
        else:
            raise ValueError(f'不支持的模型: {model_name}')

    def _build_unet(self, encoder: str, num_classes: int, pretrained: bool):
        """构建 U-Net"""
        try:
            from segmentation_models_pytorch import Unet
            self.model = Unet(
                encoder_name=encoder,
                encoder_weights='imagenet' if pretrained else None,
                in_channels=3,
                classes=num_classes,
            )
        except ImportError:
            print('[WARN] segmentation_models_pytorch 未安装，使用简化 U-Net')
            self.model = self._build_simple_unet(num_classes)

    def _build_deeplabv3(self, encoder: str, num_classes: int, pretrained: bool):
        """构建 DeepLabV3+"""
        if TORCHVISION_AVAILABLE:
            try:
                from torchvision.models.segmentation import deeplabv3_resnet50
                self.model = deeplabv3_resnet50(
                    weights='DEFAULT' if pretrained else None,
                )
                # 修改分类头
                self.model.classifier[4] = nn.Conv2d(256, num_classes, 1)
            except Exception:
                self.model = self._build_simple_unet(num_classes)
        else:
            self.model = self._build_simple_unet(num_classes)

    def _build_simple_unet(self, num_classes: int) -> nn.Module:
        """简化 U-Net（不依赖额外库）"""

        class SimpleUNet(nn.Module):
            def __init__(self, n_classes):
                super().__init__()
                self.enc1 = self._enc_block(3, 64)
                self.enc2 = self._enc_block(64, 128)
                self.enc3 = self._enc_block(128, 256)
                self.enc4 = self._enc_block(256, 512)

                self.pool = nn.MaxPool2d(2)
                self.up4 = nn.ConvTranspose2d(512, 256, 2, stride=2)
                self.dec4 = self._dec_block(512, 256)
                self.up3 = nn.ConvTranspose2d(256, 128, 2, stride=2)
                self.dec3 = self._dec_block(256, 128)
                self.up2 = nn.ConvTranspose2d(128, 64, 2, stride=2)
                self.dec2 = self._dec_block(128, 64)
                self.final = nn.Conv2d(64, n_classes, 1)

            @staticmethod
            def _enc_block(in_ch, out_ch):
                return nn.Sequential(
                    nn.Conv2d(in_ch, out_ch, 3, padding=1),
                    nn.BatchNorm2d(out_ch),
                    nn.ReLU(inplace=True),
                    nn.Conv2d(out_ch, out_ch, 3, padding=1),
                    nn.BatchNorm2d(out_ch),
                    nn.ReLU(inplace=True),
                )

            @staticmethod
            def _dec_block(in_ch, out_ch):
                return nn.Sequential(
                    nn.Conv2d(in_ch, out_ch, 3, padding=1),
                    nn.BatchNorm2d(out_ch),
                    nn.ReLU(inplace=True),
                    nn.Conv2d(out_ch, out_ch, 3, padding=1),
                    nn.BatchNorm2d(out_ch),
                    nn.ReLU(inplace=True),
                )

            def forward(self, x):
                e1 = self.enc1(x)
                e2 = self.enc2(self.pool(e1))
                e3 = self.enc3(self.pool(e2))
                e4 = self.enc4(self.pool(e3))

                d4 = self.dec4(self.up4(e4))
                d3 = self.dec3(self.up3(d4))
                d2 = self.dec2(self.up2(d3))
                return self.final(d2)

        return SimpleUNet(num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if hasattr(self.model, 'forward'):
            out = self.model.forward(x)
            if isinstance(out, dict):
                return out.get('out', out.get('logits', list(out.values())[0]))
            return out
        return self.model(x)


# ============================================================
# Loss 函数
# ============================================================

class CombinedLoss(nn.Module):
    """
    多loss组合
    L = alpha * CE + beta * Dice + gamma * Focal
    """

    def __init__(
        self,
        num_classes: int = 20,
        ce_weight: float = 1.0,
        dice_weight: float = 0.5,
        focal_weight: float = 0.3,
        ignore_index: int = -100,
    ):
        super().__init__()
        self.num_classes = num_classes
        self.ce_weight = ce_weight
        self.dice_weight = dice_weight
        self.focal_weight = focal_weight
        self.ignore_index = ignore_index

        self.ce_loss = nn.CrossEntropyLoss(
            weight=None,
            ignore_index=ignore_index,
            label_smoothing=0.1,
        )
        self.focal_loss = FocalLoss(num_classes=num_classes)

    def forward(
        self,
        pred: torch.Tensor,
        target: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        pred: (B, C, H, W) logits
        target: (B, H, W) 类别ID
        """
        total_loss = 0.0
        loss_dict = {}

        # CrossEntropy
        ce = self.ce_loss(pred, target)
        total_loss += self.ce_weight * ce
        loss_dict['ce'] = ce.item()

        # Dice Loss
        dice = dice_loss(pred, target, self.num_classes)
        total_loss += self.dice_weight * dice
        loss_dict['dice'] = dice.item()

        # Focal Loss
        focal = self.focal_loss(pred, target)
        total_loss += self.focal_weight * focal
        loss_dict['focal'] = focal.item()

        loss_dict['total'] = total_loss.item()
        return total_loss, loss_dict


class FocalLoss(nn.Module):
    """Focal Loss for class imbalance"""

    def __init__(self, alpha=0.25, gamma=2.0, num_classes=20):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.num_classes = num_classes

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        ce = F.cross_entropy(pred, target, reduction='none')
        p_t = torch.exp(-ce)
        focal = self.alpha * (1 - p_t) ** self.gamma * ce
        return focal.mean()


def dice_loss(pred: torch.Tensor, target: torch.Tensor, num_classes: int) -> torch.Tensor:
    """
    Dice Loss（类别平均）
    """
    pred_soft = F.softmax(pred, dim=1)

    # 忽略类别
    mask = (target != -100).float()
    target_one_hot = F.one_hot(target.clamp(0, num_classes - 1), num_classes)
    target_one_hot = target_one_hot.permute(0, 3, 1, 2).float() * mask.unsqueeze(1)

    smooth = 1e-6
    intersection = (pred_soft * target_one_hot).sum(dim=(2, 3))
    union = pred_soft.sum(dim=(2, 3)) + target_one_hot.sum(dim=(2, 3))
    dice = (2 * intersection + smooth) / (union + smooth)
    return 1 - dice.mean()


def iou_score(pred: torch.Tensor, target: torch.Tensor, num_classes: int) -> float:
    """计算 mIoU"""
    pred_cls = pred.argmax(dim=1)
    ious = []
    for cls in range(num_classes):
        pred_mask = (pred_cls == cls)
        target_mask = (target == cls)
        intersection = (pred_mask & target_mask).sum().item()
        union = (pred_mask | target_mask).sum().item()
        if union > 0:
            ious.append(intersection / union)
    return np.mean(ious) if ious else 0.0


def pixel_accuracy(pred: torch.Tensor, target: torch.Tensor) -> float:
    """像素精度"""
    pred_cls = pred.argmax(dim=1)
    mask = (target != -100)
    correct = (pred_cls == target)[mask].sum().item()
    total = mask.sum().item()
    return correct / max(total, 1)


# ============================================================
# 训练器
# ============================================================

@dataclass
class TrainingConfig:
    """训练配置"""
    model: str = 'unet'
    encoder: str = 'resnet34'
    num_classes: int = 20
    image_size: Tuple[int, int] = (512, 512)

    batch_size: int = 8
    num_epochs: int = 50
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4

    optimizer: str = 'adamw'
    scheduler: str = 'cosine'

    loss_weights: Tuple[float, float, float] = (1.0, 0.5, 0.3)

    checkpoint_dir: str = CKPT_DIR
    save_every: int = 5
    log_every: int = 10

    device: str = 'auto'
    num_workers: int = 4
    pin_memory: bool = True

    # 伪标签配置
    use_pseudo_labels: bool = False
    pseudo_label_model: str = 'deeplabv3_resnet50'
    pseudo_threshold: float = 0.9

    # 数据增强
    augment: bool = True


class Trainer:
    """训练器"""

    def __init__(self, config: TrainingConfig):
        self.config = config

        # 设备
        if config.device == 'auto':
            if TORCH_AVAILABLE and torch.cuda.is_available():
                self.device = torch.device('cuda')
                print(f'  GPU: {torch.cuda.get_device_name(0)}')
            else:
                self.device = torch.device('cpu')
                print('  CPU 模式')
        else:
            self.device = torch.device(config.device)

        # 模型
        self.model = None
        self.optimizer = None
        self.scheduler = None
        self.loss_fn = None

        self.start_epoch = 0
        self.best_metric = 0.0

    def build_model(self):
        """构建模型"""
        if not TORCH_AVAILABLE:
            raise RuntimeError('PyTorch 未安装')

        self.model = SegmentationModelWrapper(
            model_name=self.config.model,
            encoder=self.config.encoder,
            num_classes=self.config.num_classes,
            pretrained=True,
        ).to(self.device)

        # 优化器
        if self.config.optimizer == 'adamw':
            self.optimizer = AdamW(
                self.model.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
            )
        elif self.config.optimizer == 'sgd':
            self.optimizer = SGD(
                self.model.parameters(),
                lr=self.config.learning_rate,
                momentum=0.9,
                weight_decay=self.config.weight_decay,
            )
        else:
            raise ValueError(f'未知优化器: {self.config.optimizer}')

        # 学习率调度器
        if self.config.scheduler == 'cosine':
            self.scheduler = CosineAnnealingLR(
                self.optimizer,
                T_max=self.config.num_epochs,
                eta_min=self.config.learning_rate * 0.01,
            )
        else:
            self.scheduler = torch.optim.lr_scheduler.StepLR(
                self.optimizer, step_size=20, gamma=0.5,
            )

        # Loss
        self.loss_fn = CombinedLoss(
            num_classes=self.config.num_classes,
            ce_weight=self.config.loss_weights[0],
            dice_weight=self.config.loss_weights[1],
            focal_weight=self.config.loss_weights[2],
        )

        print(f'  模型: {self.config.model} (encoder={self.config.encoder})')
        print(f'  优化器: {self.config.optimizer}, LR={self.config.learning_rate}')
        print(f'  Loss: CE({self.config.loss_weights[0]}) + '
              f'Dice({self.config.loss_weights[1]}) + '
              f'Focal({self.config.loss_weights[2]})')

    def save_checkpoint(self, epoch: int, metric: float, filename: str = None):
        """保存检查点"""
        if filename is None:
            filename = f"ckpt_{self.config.model}_{self.config.encoder}_e{epoch:03d}_miou{metric:.4f}.pth"

        path = os.path.join(self.config.checkpoint_dir, filename)
        ckpt = {
            'epoch': epoch,
            'model_state': self.model.state_dict(),
            'optimizer_state': self.optimizer.state_dict(),
            'scheduler_state': self.scheduler.state_dict(),
            'best_metric': self.best_metric,
            'config': {
                'model': self.config.model,
                'encoder': self.config.encoder,
                'num_classes': self.config.num_classes,
                'image_size': self.config.image_size,
                'batch_size': self.config.batch_size,
            },
        }
        torch.save(ckpt, path)
        print(f'  [保存] {path}')

    def load_checkpoint(self, path: str):
        """加载检查点"""
        if not os.path.exists(path):
            print(f'  [WARN] 检查点不存在: {path}')
            return

        ckpt = torch.load(path, map_location=self.device)
        self.model.load_state_dict(ckpt['model_state'])
        self.optimizer.load_state_dict(ckpt['optimizer_state'])
        self.scheduler.load_state_dict(ckpt['scheduler_state'])
        self.start_epoch = ckpt['epoch'] + 1
        self.best_metric = ckpt.get('best_metric', 0.0)
        print(f'  [加载] Epoch {self.start_epoch}, best_mIoU: {self.best_metric:.4f}')

    def train_epoch(
        self,
        train_loader: DataLoader,
        epoch: int,
    ) -> Dict[str, float]:
        """训练一个epoch"""
        self.model.train()
        total_loss = 0.0
        total_miou = 0.0
        total_acc = 0.0
        n_batches = len(train_loader)

        for batch_idx, (images, masks) in enumerate(train_loader):
            images = images.to(self.device)
            masks = masks.to(self.device)

            self.optimizer.zero_grad()
            outputs = self.model(images)
            loss, loss_dict = self.loss_fn(outputs, masks)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            # 指标
            miou = iou_score(outputs, masks, self.config.num_classes)
            acc = pixel_accuracy(outputs, masks)

            total_loss += loss.item()
            total_miou += miou
            total_acc += acc

            if batch_idx % self.config.log_every == 0:
                print(f'  Epoch {epoch} [{batch_idx}/{n_batches}] '
                      f'loss={loss.item():.4f} miou={miou:.3f} acc={acc:.3f}')

        avg_loss = total_loss / n_batches
        avg_miou = total_miou / n_batches
        avg_acc = total_acc / n_batches

        return {'loss': avg_loss, 'miou': avg_miou, 'acc': avg_acc}

    @torch.no_grad()
    def validate(self, val_loader: DataLoader) -> Dict[str, float]:
        """验证"""
        self.model.eval()
        total_loss = 0.0
        total_miou = 0.0
        total_acc = 0.0
        n_batches = len(val_loader)

        for images, masks in val_loader:
            images = images.to(self.device)
            masks = masks.to(self.device)

            outputs = self.model(images)
            loss, _ = self.loss_fn(outputs, masks)

            total_loss += loss.item()
            total_miou += iou_score(outputs, masks, self.config.num_classes)
            total_acc += pixel_accuracy(outputs, masks)

        return {
            'val_loss': total_loss / n_batches,
            'val_miou': total_miou / n_batches,
            'val_acc': total_acc / n_batches,
        }

    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader = None,
        resume_path: str = None,
    ):
        """完整训练流程"""
        print('=' * 60)
        print('语义分割训练')
        print('=' * 60)

        self.build_model()

        if resume_path:
            self.load_checkpoint(resume_path)

        best_miou = self.best_metric
        history = []

        for epoch in range(self.start_epoch, self.config.num_epochs):
            print(f'\nEpoch {epoch+1}/{self.config.num_epochs}')
            print('-' * 40)

            # 训练
            train_metrics = self.train_epoch(train_loader, epoch)

            # 验证
            val_metrics = {'val_loss': 0, 'val_miou': 0, 'val_acc': 0}
            if val_loader:
                val_metrics = self.validate(val_loader)

            # 学习率
            self.scheduler.step()
            current_lr = self.optimizer.param_groups[0]['lr']

            record = {
                'epoch': epoch + 1,
                'lr': current_lr,
                **train_metrics,
                **val_metrics,
            }
            history.append(record)

            # 打印
            print(f'  [训练] loss={train_metrics["loss"]:.4f} '
                  f'miou={train_metrics["miou"]:.4f} acc={train_metrics["acc"]:.4f}')
            if val_loader:
                print(f'  [验证] loss={val_metrics["val_loss"]:.4f} '
                      f'miou={val_metrics["val_miou"]:.4f} acc={val_metrics["val_acc"]:.4f}')
            print(f'  [LR] {current_lr:.2e}')

            # 保存最佳模型
            if val_loader and val_metrics['val_miou'] > best_miou:
                best_miou = val_metrics['val_miou']
                self.best_metric = best_miou
                self.save_checkpoint(epoch, best_miou,
                                     f"best_{self.config.model}_{self.config.encoder}.pth")
                print(f'  [最佳] mIoU: {best_miou:.4f}')

            # 定期保存
            if (epoch + 1) % self.config.save_every == 0:
                self.save_checkpoint(epoch, val_metrics.get('val_miou', 0))

        # 保存训练历史
        hist_df = pd.DataFrame(history)
        hist_path = os.path.join(self.config.checkpoint_dir, 'training_history.csv')
        hist_df.to_csv(hist_path, index=False)
        print(f'\n训练历史已保存: {hist_path}')
        print(f'最佳 mIoU: {best_miou:.4f}')

        return history


# ============================================================
# 伪标签生成器
# ============================================================

class PseudoLabelGenerator:
    """
    伪标签生成器

    流程:
    1. 使用预训练模型对未标注数据生成伪标签
    2. 过滤低置信度像素
    3. 生成伪标签mask
    """

    def __init__(
        self,
        teacher_model_key: str = 'deeplabv3_resnet50',
        confidence_threshold: float = 0.9,
        device: str = 'auto',
    ):
        self.teacher_key = teacher_model_key
        self.threshold = confidence_threshold

        if device == 'auto':
            if TORCH_AVAILABLE and torch.cuda.is_available():
                self.device = torch.device('cuda')
            else:
                self.device = torch.device('cpu')
        else:
            self.device = torch.device(device)

        self.model = None

    def _build_teacher_model(self):
        """构建教师模型"""
        if self.teacher_key == 'deeplabv3_resnet50' and TORCHVISION_AVAILABLE:
            from torchvision.models.segmentation import deeplabv3_resnet50
            model = deeplabv3_resnet50(weights='DEFAULT')
            model.to(self.device)
            model.eval()
            return model
        raise NotImplementedError(f'教师模型暂不支持: {self.teacher_key}')

    def generate_pseudo_labels(
        self,
        image_dir: str,
        output_dir: str,
        batch_size: int = 8,
    ) -> Dict[str, float]:
        """
        生成伪标签

        返回:
            统计信息 {total_images, high_conf_count, low_conf_count}
        """
        print('=' * 60)
        print('生成伪标签')
        print('=' * 60)

        if self.model is None:
            self.model = self._build_teacher_model()

        os.makedirs(output_dir, exist_ok=True)

        valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        image_files = []
        for f in os.listdir(image_dir):
            if Path(f).suffix.lower() in valid_exts:
                image_files.append(os.path.join(image_dir, f))

        print(f'  待处理: {len(image_files)} 张图像')
        print(f'  置信度阈值: {self.threshold}')

        high_conf = 0
        low_conf = 0

        for img_path in image_files:
            try:
                img = cv2.imread(img_path)
                if img is None:
                    continue
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                H, W = img_rgb.shape[:2]

                # 预处理
                img_t = torch.from_numpy(img_rgb).permute(2, 0, 1).float() / 255.0
                mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
                std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
                img_t = (img_t - mean) / std
                img_t = img_t.unsqueeze(0).to(self.device)

                with torch.no_grad():
                    output = self.model(img_t)['out']
                    probs = F.softmax(output, dim=1)
                    conf, pred = probs.max(dim=1)

                # 过滤低置信度
                mask_confident = (conf.squeeze() > self.threshold).cpu().numpy()
                mask_pred = pred.squeeze().cpu().numpy()

                pseudo_mask = np.where(mask_confident, mask_pred, 0).astype(np.uint8)

                # 保存
                mask_name = Path(img_path).stem + '.png'
                mask_path = os.path.join(output_dir, mask_name)
                cv2.imwrite(mask_path, pseudo_mask)

                high_conf += mask_confident.sum()
                low_conf += (~mask_confident).sum()

            except Exception as e:
                print(f'  [WARN] 失败 {img_path}: {e}')

        print(f'\n  完成: {len(image_files)} 张')
        print(f'  高置信度像素: {high_conf:,}')
        print(f'  低置信度像素: {low_conf:,}')

        return {
            'total_images': len(image_files),
            'high_confidence_pixels': int(high_conf),
            'low_confidence_pixels': int(low_conf),
        }


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='GPU语义分割训练')
    parser.add_argument('--train-dir', default=IMAGES_DIR,
                        help='训练图像目录')
    parser.add_argument('--mask-dir', default=None,
                        help='标注mask目录 (无则用伪标签)')
    parser.add_argument('--output-dir', default=CKPT_DIR,
                        help='模型输出目录')
    parser.add_argument('--model', default='unet',
                        choices=['unet', 'deeplabv3'],
                        help='模型架构')
    parser.add_argument('--encoder', default='resnet34',
                        help='编码器 (resnet34/resnet50/mobilenet_v2)')
    parser.add_argument('--num-classes', type=int, default=20,
                        help='分割类别数')
    parser.add_argument('--epochs', type=int, default=50,
                        help='训练轮数')
    parser.add_argument('--batch-size', type=int, default=8,
                        help='批大小')
    parser.add_argument('--lr', type=float, default=1e-3,
                        help='学习率')
    parser.add_argument('--image-size', type=int, default=512,
                        help='图像尺寸 (正方形)')
    parser.add_argument('--resume', default=None,
                        help='恢复训练的检查点路径')
    parser.add_argument('--generate-pseudo-labels', action='store_true',
                        help='先生成伪标签')
    parser.add_argument('--pseudo-threshold', type=float, default=0.9,
                        help='伪标签置信度阈值')
    parser.add_argument('--list-models', action='store_true',
                        help='列出支持的模型')

    args = parser.parse_args()

    if args.list_models:
        print('支持的模型:')
        for k, v in SegmentationModelWrapper.supported_models.items():
            print(f'  {k}: {v}')
        return

    config = TrainingConfig(
        model=args.model,
        encoder=args.encoder,
        num_classes=args.num_classes,
        image_size=(args.image_size, args.image_size),
        batch_size=args.batch_size,
        num_epochs=args.epochs,
        learning_rate=args.lr,
        checkpoint_dir=args.output_dir,
    )

    # 伪标签生成
    if args.generate_pseudo_labels:
        generator = PseudoLabelGenerator(
            confidence_threshold=args.pseudo_threshold,
        )
        pseudo_dir = os.path.join(args.mask_dir or MASKS_DIR, 'pseudo')
        stats = generator.generate_pseudo_labels(
            image_dir=args.train_dir,
            output_dir=pseudo_dir,
        )
        # 使用伪标签目录作为 mask 目录
        if args.mask_dir is None:
            args.mask_dir = pseudo_dir
        # 保存统计
        stat_path = os.path.join(args.output_dir, 'pseudo_label_stats.json')
        with open(stat_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f'伪标签统计已保存: {stat_path}')

    # 创建数据集
    print(f'\n加载数据集:')
    print(f'  图像目录: {args.train_dir}')
    print(f'  Mask目录: {args.mask_dir}')

    train_dataset = StreetViewDataset(
        image_dir=args.train_dir,
        mask_dir=args.mask_dir,
        split='train',
        augment=True,
        image_size=config.image_size,
    )

    val_dataset = StreetViewDataset(
        image_dir=args.train_dir,
        mask_dir=args.mask_dir,
        split='val',
        augment=False,
        image_size=config.image_size,
    )

    print(f'  训练集: {len(train_dataset)} 张')
    print(f'  验证集: {len(val_dataset)} 张')

    if len(train_dataset) == 0:
        print('[ERROR] 训练集为空，请检查图像目录')
        sys.exit(1)

    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        pin_memory=config.pin_memory,
        drop_last=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        pin_memory=config.pin_memory,
    ) if len(val_dataset) > 0 else None

    # 训练
    trainer = Trainer(config)
    trainer.train(train_loader, val_loader, resume_path=args.resume)


if __name__ == '__main__':
    main()
