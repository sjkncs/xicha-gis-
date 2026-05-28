# -*- coding: utf-8 -*-
"""
================================================================
一站式深度学习 Pipeline 入口脚本
15分钟城市可达性 · 街景语义分割 · GPU推理与训练

功能概览:
  Step 1: 采样点准备     → 从现有 CSV 生成采样点列表（分层采样，≤500点）
  Step 2: 静态地图下载   → 高德静态地图批量下载（断点续传，500配额管理）
  Step 3: 图像推理       → 多模型语义分割（DeepLabV3+/SegFormer/U-Net等）
  Step 4: 指标计算       → SCR/GVR/VVR/CSR 等步行可达性指标
  Step 5: 模型训练       → 预训练微调 / 伪标签训练 / 从头训练
  Step 6: 结果可视化     → 分割可视化、指标热力图、地图叠加

使用方式:
  # 一键完整流程
  python run_pipeline.py --mode full

  # 仅下载（快速测试）
  python run_pipeline.py --mode download --limit 10

  # 仅推理（使用已下载图像）
  python run_pipeline.py --mode inference --models deeplabv3_resnet50 nvidia_mit_b0

  # 仅训练（需要标注数据）
  python run_pipeline.py --mode train --epochs 30

  # 伪标签训练（无标注数据时）
  python run_pipeline.py --mode train --use-pseudo --epochs 50

================================================================
"""

import os
import sys
import json
import time
import subprocess
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# ============================================================
# 路径配置
# ============================================================

PROJECT_DIR = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility'
PIPELINE_DIR = os.path.join(PROJECT_DIR, 'algorithms', 'deep_learning', 'dl_pipeline')
DATA_DIR = os.path.join(PROJECT_DIR, 'data', 'dl_pipeline')
IMAGES_DIR = os.path.join(DATA_DIR, 'images', 'raw')
RESULTS_DIR = os.path.join(DATA_DIR, 'images', 'results')
SAMPLES_DIR = os.path.join(DATA_DIR, 'samples')
CHECKPOINT_DIR = os.path.join(DATA_DIR, 'checkpoints')

SCRIPTS = {
    'prepare_samples': os.path.join(PIPELINE_DIR, 'prepare_samples.py'),
    'batch_download':  os.path.join(PIPELINE_DIR, 'batch_download.py'),
    'segment_inference': os.path.join(PIPELINE_DIR, 'segment_inference.py'),
    'segment_train':    os.path.join(PIPELINE_DIR, 'segment_train.py'),
}


# ============================================================
# 工具函数
# ============================================================

def cmd(command: str, description: str = '') -> Tuple[int, str, str]:
    """执行 shell 命令，返回 (exit_code, stdout, stderr)"""
    print(f'\n{"=":*60}')
    print(f'  {description}')
    print(f'{"=":*60}')
    print(f'CMD: {command[:120]}{"..." if len(command) > 120 else ""}\n')

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=PROJECT_DIR,
        encoding='utf-8',
        errors='replace',
    )

    if result.stdout:
        print(result.stdout[:2000])
    if result.stderr and result.returncode != 0:
        print('[STDERR]', result.stderr[:1000])

    return result.returncode, result.stdout, result.stderr


def ensure_dirs():
    """确保所有必要目录存在"""
    for d in [DATA_DIR, IMAGES_DIR, RESULTS_DIR, SAMPLES_DIR, CHECKPOINT_DIR]:
        os.makedirs(d, exist_ok=True)


def print_banner(text: str, width: int = 70):
    """打印横幅"""
    print()
    print('=' * width)
    print(f'  {text}')
    print('=' * width)


def load_samples(limit: Optional[int] = None) -> Optional[list]:
    """加载采样点"""
    csv_path = os.path.join(SAMPLES_DIR, 'dl_sample_points.csv')
    if not os.path.exists(csv_path):
        return None
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        if limit:
            df = df.head(limit)
        return df.to_dict(orient='records')
    except Exception:
        return None


def get_existing_images() -> int:
    """获取已下载图像数"""
    if not os.path.exists(IMAGES_DIR):
        return 0
    return len([f for f in os.listdir(IMAGES_DIR)
                if f.endswith(('.png', '.jpg', '.jpeg', '.bmp'))])


# ============================================================
# Pipeline Step 函数
# ============================================================

def step_prepare_samples(args) -> bool:
    """Step 1: 采样点准备"""
    print_banner('Step 1: 采样点准备')

    script = SCRIPTS['prepare_samples']
    if not os.path.exists(script):
        print(f'[ERROR] 脚本不存在: {script}')
        return False

    command = f'python "{script}" --max {args.sample_max} --output-dir "{SAMPLES_DIR}"'
    if args.no_manual:
        command += ' --no-manual'

    code, stdout, stderr = cmd(command, '采样点生成')
    if code != 0:
        print(f'[ERROR] 采样点准备失败 (exit={code})')
        return False

    # 检查输出
    csv_out = os.path.join(SAMPLES_DIR, 'dl_sample_points.csv')
    if os.path.exists(csv_out):
        import pandas as pd
        df = pd.read_csv(csv_out)
        print(f'\n[OK] 采样点生成完成: {len(df)} 个')
        print(f'  城市形态分布:')
        for form, cnt in df['urban_form'].fillna('Open/Other').value_counts().items():
            print(f'    {form}: {cnt}')
    return True


def step_download(args) -> bool:
    """Step 2: 静态地图下载"""
    print_banner('Step 2: 静态地图批量下载')
    print(f'  当前配额: 500次/日')
    print(f'  本次下载上限: {args.sample_max} 张')
    print(f'  缩放级别: zoom={args.zoom}, 尺寸: {args.width}x{args.height}')
    print(f'  输出目录: {IMAGES_DIR}')

    script = SCRIPTS['batch_download']
    if not os.path.exists(script):
        print(f'[ERROR] 脚本不存在: {script}')
        return False

    samples_csv = os.path.join(SAMPLES_DIR, 'dl_sample_points.csv')
    if not os.path.exists(samples_csv):
        print(f'[ERROR] 采样点文件不存在: {samples_csv}')
        print('  请先运行 Step 1: python run_pipeline.py --mode samples')
        return False

    # 下载
    command = (
        f'python "{script}" '
        f'--input "{samples_csv}" '
        f'--zoom {args.zoom} '
        f'--width {args.width} '
        f'--height {args.height} '
        f'--scale {args.scale} '
        f'--delay {args.delay} '
        f'--output "{IMAGES_DIR}" '
        f'--tag amap '
    )
    if args.no_resume:
        command += ' --no-resume'

    code, stdout, stderr = cmd(command, '静态地图下载')
    if code != 0:
        print(f'[WARN] 下载脚本退出码: {code}')

    # 检查结果
    existing = get_existing_images()
    print(f'\n[OK] 现有图像: {existing} 张')
    return existing > 0


def step_inference(args) -> bool:
    """Step 3: 语义分割推理"""
    print_banner('Step 3: 多模型语义分割推理')

    existing = get_existing_images()
    print(f'  待处理图像: {existing} 张')
    print(f'  使用模型: {args.models}')

    if existing == 0:
        print('[ERROR] 无图像可用，请先运行下载步骤')
        return False

    script = SCRIPTS['segment_inference']
    if not os.path.exists(script):
        print(f'[ERROR] 脚本不存在: {script}')
        return False

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_csv = os.path.join(CHECKPOINT_DIR, f'seg_results_{ts}.csv')
    checkpoint = os.path.join(CHECKPOINT_DIR, 'seg_checkpoint.json')

    model_str = ' '.join(args.models)
    command = (
        f'python "{script}" '
        f'--input "{IMAGES_DIR}" '
        f'--models {model_str} '
        f'--output-csv "{output_csv}" '
        f'--checkpoint "{checkpoint}" '
        f'--device {args.device} '
        f'--output-dir "{RESULTS_DIR}" '
    )
    if args.no_resume:
        command += ' --no-resume'
    if args.no_masks:
        command += ' --no-masks'
    if args.no_vis:
        command += ' --no-vis'

    code, stdout, stderr = cmd(command, '语义分割推理')
    if code != 0:
        print(f'[WARN] 推理脚本退出码: {code}')

    # 检查结果
    if os.path.exists(output_csv):
        import pandas as pd
        df = pd.read_csv(output_csv)
        print(f'\n[OK] 推理完成: {len(df)} 条记录')
        if len(df) > 0:
            print(f'  SCR 均值: {df["SCR"].mean():.3f}')
            print(f'  GVR 均值: {df["GVR"].mean():.3f}')
            print(f'  VVR 均值: {df["VVR"].mean():.3f}')
            print(f'  CSR 均值: {df["CSR"].mean():.3f}')
        return True
    return False


def step_train(args) -> bool:
    """Step 4: 模型训练"""
    print_banner('Step 5: 语义分割模型训练')
    print(f'  模型: {args.model}')
    print(f'  编码器: {args.encoder}')
    print(f'  Epochs: {args.epochs}')
    print(f'  Batch Size: {args.batch_size}')
    print(f'  伪标签模式: {args.use_pseudo}')

    script = SCRIPTS['segment_train']
    if not os.path.exists(script):
        print(f'[ERROR] 脚本不存在: {script}')
        return False

    command = (
        f'python "{script}" '
        f'--train-dir "{IMAGES_DIR}" '
        f'--output-dir "{CHECKPOINT_DIR}" '
        f'--model {args.model} '
        f'--encoder {args.encoder} '
        f'--num-classes {args.num_classes} '
        f'--epochs {args.epochs} '
        f'--batch-size {args.batch_size} '
        f'--image-size {args.image_size} '
        f'--lr {args.lr} '
    )
    if args.use_pseudo:
        command += ' --generate-pseudo-labels --pseudo-threshold 0.9'
    if args.resume:
        command += f' --resume "{args.resume}"'

    code, stdout, stderr = cmd(command, '模型训练')
    return code == 0


def step_visualize(args) -> bool:
    """Step 5: 结果可视化"""
    print_banner('Step 6: 结果可视化')
    print('  可视化功能已集成在 segment_inference.py 中')
    print(f'  可视化结果目录: {RESULTS_DIR}')

    result_files = []
    if os.path.exists(RESULTS_DIR):
        for f in os.listdir(RESULTS_DIR):
            if f.endswith('.png'):
                result_files.append(f)

    print(f'  现有可视化文件: {len(result_files)} 个')
    return True


def step_report(args) -> bool:
    """Step 6: 生成分析报告"""
    print_banner('Step 7: 生成分析报告')

    report_path = os.path.join(CHECKPOINT_DIR, f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')

    # 汇总所有结果
    all_results = []
    if os.path.exists(CHECKPOINT_DIR):
        for f in os.listdir(CHECKPOINT_DIR):
            if f.startswith('seg_results_') and f.endswith('.csv'):
                try:
                    import pandas as pd
                    df = pd.read_csv(os.path.join(CHECKPOINT_DIR, f))
                    all_results.append(df)
                except Exception:
                    pass

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('=' * 60 + '\n')
        f.write('15分钟城市可达性 · 深度学习分析报告\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write('=' * 60 + '\n\n')

        f.write('【1. 数据概况】\n')
        f.write(f'  采样点数: {args.sample_max}\n')
        f.write(f'  下载图像数: {get_existing_images()}\n')
        f.write(f'  推理记录数: {sum(len(r) for r in all_results)}\n\n')

        if all_results:
            combined = pd.concat(all_results, ignore_index=True)
            f.write('【2. 步行可达性指标统计】\n')
            for col in ['SCR', 'GVR', 'VVR', 'CSR']:
                if col in combined.columns:
                    vals = combined[col].dropna()
                    f.write(f'  {col}:\n')
                    f.write(f'    均值: {vals.mean():.4f}\n')
                    f.write(f'    标准差: {vals.std():.4f}\n')
                    f.write(f'    最小值: {vals.min():.4f}\n')
                    f.write(f'    最大值: {vals.max():.4f}\n')
                    f.write(f'    中位数: {vals.median():.4f}\n\n')

            f.write('【3. 按模型分组】\n')
            for model, grp in combined.groupby('model'):
                f.write(f'  {model}:\n')
                f.write(f'    SCR均值: {grp["SCR"].mean():.3f}\n')
                f.write(f'    GVR均值: {grp["GVR"].mean():.3f}\n')
                f.write(f'    样本数: {len(grp)}\n\n')

        f.write('【4. GPU推荐配置】\n')
        f.write('  RTX 5090 (32GB): batch_size=16, image_size=1024\n')
        f.write('  RTX 4090 (24GB): batch_size=8,  image_size=768\n')
        f.write('  RTX 3090 (24GB): batch_size=8,  image_size=768\n')
        f.write('  RTX A6000(48G): batch_size=16, image_size=1024\n')
        f.write('  CPU (无GPU):     batch_size=2,  image_size=512\n\n')

        f.write('【5. 下一步建议】\n')
        f.write('  1. 查看 RESULTS_DIR 中的分割可视化图像\n')
        f.write('  2. 用伪标签进行初步训练: python run_pipeline.py --mode train --use-pseudo\n')
        f.write('  3. 人工标注部分数据微调: 100-500张即有明显提升\n')
        f.write('  4. 模型融合: 多模型平均提升鲁棒性\n')
        f.write('  5. 时序分析: 多时间点对比城市变化\n')

    print(f'\n[OK] 报告已生成: {report_path}')
    return True


# ============================================================
# 全流程编排
# ============================================================

def run_full_pipeline(args) -> bool:
    """一键完整流程"""
    print_banner('一键完整 Pipeline')
    print(f'开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'采样点上限: {args.sample_max}')
    print(f'推理模型: {args.models}')

    steps = [
        ('采样点准备', lambda: step_prepare_samples(args)),
        ('静态地图下载', lambda: step_download(args)),
        ('语义分割推理', lambda: step_inference(args)),
        ('结果可视化', lambda: step_visualize(args)),
        ('生成报告', lambda: step_report(args)),
    ]

    results = []
    for name, fn in steps:
        print(f'\n\n{"#"*60}')
        print(f'  [{name}]')
        print(f'{"#"*60}')
        success = fn()
        results.append((name, success))
        if not success and name in ['采样点准备', '静态地图下载']:
            print(f'[ERROR] 关键步骤失败: {name}')
            # 不退出，继续尝试后续步骤

    print()
    print('=' * 60)
    print('Pipeline 执行汇总')
    print('=' * 60)
    for name, success in results:
        status = '[OK]' if success else '[SKIP]'
        print(f'  {status} {name}')

    all_ok = all(r[1] for r in results)
    print()
    print(f'完成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    return all_ok


# ============================================================
# 快速测试
# ============================================================

def run_quick_test(args) -> bool:
    """快速测试（少量样本）"""
    print_banner('快速测试模式')
    args.sample_max = min(args.sample_max, 5)
    args.epochs = 1
    args.delay = 0.5

    print(f'  测试样本数: {args.sample_max}')
    print(f'  训练epochs: {args.epochs}')

    # 测试下载
    ok1 = step_prepare_samples(args)
    ok2 = step_download(args) if args.mode in ['full', 'download'] else True

    # 测试推理
    if args.mode in ['full', 'inference']:
        ok3 = step_inference(args)
    else:
        ok3 = True

    return ok1 and ok2 and ok3


# ============================================================
# 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='深度学习 Pipeline 入口',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # 完整流程（采样 → 下载 → 推理 → 报告）
  python run_pipeline.py --mode full

  # 仅推理（使用已有图像）
  python run_pipeline.py --mode inference

  # 快速测试（5个样本）
  python run_pipeline.py --mode test --sample-max 5

  # 伪标签训练（无标注数据）
  python run_pipeline.py --mode train --use-pseudo --epochs 30

  # 多模型推理
  python run_pipeline.py --mode inference --models deeplabv3_resnet50 nvidia_mit_b0 segformer_b0

  # 指定样本数
  python run_pipeline.py --mode download --sample-max 50

  # 仅生成采样点
  python run_pipeline.py --mode samples

  硬件配置推荐:
  RTX 5090 (32GB): 推荐配置 --batch-size 16 --image-size 1024
  RTX 4090 (24GB): 标准配置 --batch-size 8 --image-size 768
  RTX 3090 (24GB): 标准配置 --batch-size 8 --image-size 768
  RTX A6000 (48GB): 最大配置 --batch-size 16 --image-size 1024
  无GPU (CPU):     轻量配置 --batch-size 2 --image-size 512
'''
    )

    # 模式
    parser.add_argument('--mode', default='full',
                        choices=['full', 'test', 'samples', 'download',
                                'inference', 'train', 'visualize', 'report'],
                        help='运行模式')

    # 通用参数
    parser.add_argument('--sample-max', type=int, default=300,
                        help='最大采样点数 (默认300，API配额500-余量)')
    parser.add_argument('--zoom', type=int, default=16,
                        help='地图缩放级别 (1-18)')
    parser.add_argument('--width', type=int, default=600,
                        help='图像宽度')
    parser.add_argument('--height', type=int, default=400,
                        help='图像高度')
    parser.add_argument('--scale', type=int, default=1, choices=[1, 2],
                        help='屏幕scale (1=标准, 2=高清)')
    parser.add_argument('--delay', type=float, default=0.5,
                        help='下载请求间隔（秒）')
    parser.add_argument('--no-resume', action='store_true',
                        help='禁用断点续传')
    parser.add_argument('--no-manual', action='store_true',
                        help='不使用手动样本')

    # 推理参数
    parser.add_argument('--models', nargs='+',
                        default=['deeplabv3_resnet50', 'nvidia_mit_b0'],
                        help='推理模型列表')
    parser.add_argument('--device', default='auto',
                        choices=['auto', 'cuda', 'cpu'],
                        help='计算设备')
    parser.add_argument('--no-masks', action='store_true',
                        help='不保存分割mask')
    parser.add_argument('--no-vis', action='store_true',
                        help='不保存可视化')

    # 训练参数
    parser.add_argument('--model', default='unet',
                        choices=['unet', 'deeplabv3'],
                        help='训练模型架构')
    parser.add_argument('--encoder', default='resnet34',
                        help='编码器 (resnet34/resnet50/mobilenet_v2)')
    parser.add_argument('--num-classes', type=int, default=20,
                        help='分割类别数')
    parser.add_argument('--epochs', type=int, default=50,
                        help='训练轮数')
    parser.add_argument('--batch-size', type=int, default=8,
                        help='批大小')
    parser.add_argument('--image-size', type=int, default=512,
                        help='训练图像尺寸')
    parser.add_argument('--lr', type=float, default=1e-3,
                        help='学习率')
    parser.add_argument('--use-pseudo', action='store_true',
                        help='使用伪标签训练')
    parser.add_argument('--resume', default=None,
                        help='恢复训练的检查点')

    # 环境
    parser.add_argument('--check-env', action='store_true',
                        help='仅检查环境')

    args = parser.parse_args()

    # 确保目录
    ensure_dirs()

    # 检查环境
    if args.check_env:
        print_banner('环境检查')
        deps = [
            ('torch', 'PyTorch'),
            ('torchvision', 'torchvision'),
            ('transformers', 'transformers'),
            ('ultralytics', 'ultralytics'),
            ('cv2', 'OpenCV'),
            ('PIL', 'Pillow'),
            ('numpy', 'numpy'),
            ('pandas', 'pandas'),
            ('matplotlib', 'matplotlib'),
            ('requests', 'requests'),
        ]
        print(f'  Python: {sys.version.split()[0]}')
        for module, name in deps:
            try:
                mod = __import__(module)
                version = getattr(mod, '__version__', 'unknown')
                print(f'  [OK] {name}: {version}')
            except ImportError:
                print(f'  [MISSING] {name}')
        try:
            import torch
            if torch.cuda.is_available():
                print(f'  [OK] CUDA: {torch.cuda.get_device_name(0)}')
                print(f'  [OK] GPU Memory: {torch.cuda.get_device_properties(0).total_memory/1024**3:.1f} GB')
            else:
                print('  [WARN] CUDA: 不可用，将使用CPU')
        except Exception as e:
            print(f'  [WARN] PyTorch/CUDA 检查失败: {e}')
        return

    # 执行
    print_banner('深度学习 Pipeline 入口')
    print(f'  工作目录: {PROJECT_DIR}')
    print(f'  Pipeline目录: {PIPELINE_DIR}')
    print(f'  数据目录: {DATA_DIR}')
    print(f'  图像目录: {IMAGES_DIR}')
    print(f'  结果目录: {RESULTS_DIR}')

    t0 = time.time()

    if args.mode == 'full':
        success = run_full_pipeline(args)
    elif args.mode == 'test':
        success = run_quick_test(args)
    elif args.mode == 'samples':
        success = step_prepare_samples(args)
    elif args.mode == 'download':
        success = step_prepare_samples(args)
        if success:
            success = step_download(args)
    elif args.mode == 'inference':
        success = step_inference(args)
    elif args.mode == 'train':
        success = step_train(args)
    elif args.mode == 'visualize':
        success = step_visualize(args)
    elif args.mode == 'report':
        success = step_report(args)
    else:
        print(f'[ERROR] 未知模式: {args.mode}')
        success = False

    elapsed = time.time() - t0

    print()
    if success:
        print(f'=' * 60)
        print(f'  Pipeline 完成 (耗时: {elapsed:.0f}秒 / {elapsed/60:.1f}分钟)')
        print(f'=' * 60)
    else:
        print(f'=' * 60)
        print(f'  Pipeline 部分完成或失败 (耗时: {elapsed:.0f}秒)')
        print(f'  请检查上述日志')
        print(f'=' * 60)
        sys.exit(1)


if __name__ == '__main__':
    main()
