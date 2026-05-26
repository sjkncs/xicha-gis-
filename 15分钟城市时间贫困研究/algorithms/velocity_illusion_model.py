# -*- coding: utf-8 -*-
"""
=============================================================================
群体差异化步行速度模型 + 综合可达性幻觉指数
Group-Differentiated Walkability Velocity Model & Comprehensive Accessibility Illusion Index

=============================================================================

本模块实现两个核心公式:

【群体差异化速度模型】
    v_i = v_base × ∏_k α_k

    基准速度 v_base = 1.2 m/s (健康成年人)
    
    环境障碍系数:
        α_BFD (无障碍设施缺失, SCR<0.5时)     = 0.82
        α_EWW (有效宽度不足, EWW<2m时)       = 0.75
        α_elderly (老年人, 65岁以上)          = 0.60
        α_wheelchair (轮椅使用者)              = 0.40
        α_loading (临街装卸货占道)             = 0.70
        α_rain (雨天, 南方雨季影响)             = 0.85
    
    多系数连乘使环境缺陷和群体脆弱性产生叠加效应,
    更准确刻画时间贫困人群的实际通行困境。

【综合可达性幻觉指数 (AI*_i)】
    AI*_i = [T_network(i)/v_i - T_promised] / T_promised × 100%

    T_network(i)/v_i  : 基于步行环境感知的加权网络通行时间(秒)
    T_promised        : 承诺可达时间(15分钟=900秒)

    AI*_i > 0  : 幻觉效应(承诺15分钟可达，但实际需要更长时间)
    AI*_i = 0  : 准确预测
    AI*_i < 0  : 超预期(实际比承诺更快)
    
    阈值含义:
        AI*_i > 20%  : 显著幻觉区
        AI*_i > 40%  : 严重幻觉区(急需干预)

=============================================================================
"""

import os
import sys
import warnings
warnings.filterwarnings('ignore')

from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

# ==========================
# 常量定义
# ==========================

# 基准步行速度 (m/s)
V_BASE = 1.2  # 健康成年人

# 承诺可达时间 (秒)
T_PROMISED = 15 * 60  # 15分钟 = 900秒

# 环境障碍减速系数
OBSTACLE_COEFFICIENTS = {
    'alpha_BFD': {
        'name': '无障碍设施缺失 (Barrier-free Deficiency)',
        'condition': lambda m: m.get('BFD', 1) < 0.5,  # BFD低于0.5时触发
        'value': 0.82,
    },
    'alpha_EWW': {
        'name': '有效宽度不足 (Effective Walkable Width Deficiency)',
        'condition': lambda m: m.get('EWW', 5) < 2.0,  # EWW低于2m时触发
        'value': 0.75,
    },
    'alpha_severe_EWW': {
        'name': '有效宽度严重不足',
        'condition': lambda m: m.get('EWW', 5) < 1.0,  # EWW低于1m
        'value': 0.60,
    },
    'alpha_sidewalk_absent': {
        'name': '人行道缺失 (Sidewalk Absence)',
        'condition': lambda m: m.get('SCR', 1) < 0.3,  # SCR低于0.3
        'value': 0.65,
    },
    'alpha_low_SVI': {
        'name': '街道活力低 (Low Street Vitality)',
        'condition': lambda m: m.get('SVI', 1) < 0.3,  # SVI低于0.3(夜间/偏僻)
        'value': 0.88,
    },
}

# 群体特征减速系数
GROUP_COEFFICIENTS = {
    'elderly': {
        'name': '老年人 (65岁以上)',
        'value': 0.60,
    },
    'child': {
        'name': '儿童 (12岁以下)',
        'value': 0.65,
    },
    'wheelchair': {
        'name': '轮椅使用者',
        'value': 0.40,
    },
    'pregnant': {
        'name': '孕妇',
        'value': 0.70,
    },
    'heavy_load': {
        'name': '携带重物(购物/行李)',
        'value': 0.75,
    },
    'stroller': {
        'name': '推婴儿车',
        'value': 0.50,
    },
}


# ==========================
# 数据结构
# ==========================

class VulnerabilityLevel(Enum):
    """脆弱性等级"""
    ROBUST = 'robust'                    # 健康成年人
    ELDERLY = 'elderly'                 # 老年人
    LIMITED = 'limited_mobility'         # 行动不便
    WHEELCHAIR = 'wheelchair'           # 轮椅使用者
    CAREGIVER = 'caregiver'             # 看护者


@dataclass
class GroupProfile:
    """群体特征配置"""
    elderly_ratio: float = 0.15        # 老年人比例 (15%)
    wheelchair_ratio: float = 0.02    # 轮椅使用者比例 (2%)
    child_ratio: float = 0.08         # 儿童比例 (8%)
    caregiver_ratio: float = 0.05     # 看护者比例 (5%)


# ==========================
# 速度模型
# ==========================

class GroupVelocityModel:
    """
    群体差异化步行速度模型。
    
    v_i = v_base × ∏_k α_k
    
    核心逻辑:
    1. 根据步行环境指标(SCR/BFD/EWW/SVI)计算环境系数
    2. 根据群体特征(老年人/轮椅等)计算群体系数
    3. 多系数连乘得到实际步行速度
    4. 将速度转换为路网边权重
    
    应用场景:
    - 为每个小区/路段计算不同群体的实际通行时间
    - 识别对弱势群体最不友好的步行环境
    - 支持按群体特征的空间分异分析
    """
    
    def __init__(
        self,
        v_base: float = V_BASE,
        obstacle_coefficients: Optional[Dict] = None,
        group_coefficients: Optional[Dict] = None,
    ):
        self.v_base = v_base
        self.obstacle_coefficients = obstacle_coefficients or OBSTACLE_COEFFICIENTS
        self.group_coefficients = group_coefficients or GROUP_COEFFICIENTS
    
    def compute_environment_alpha(
        self,
        metrics: Dict[str, float],
    ) -> Tuple[float, Dict[str, float]]:
        """
        计算环境障碍减速系数的连乘结果。
        
        参数:
            metrics: 步行环境指标字典, 包含 SCR, BFD, EWW, SVI
        
        返回:
            (α_env = ∏_k α_k, 触发的障碍详情字典)
        """
        alpha_env = 1.0
        triggered = {}
        
        for key, config in self.obstacle_coefficients.items():
            if config['condition'](metrics):
                alpha_env *= config['value']
                triggered[key] = config['value']
        
        return alpha_env, triggered
    
    def compute_group_alpha(
        self,
        group_profile: Optional[GroupProfile] = None,
        group_type: Optional[str] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        计算群体脆弱性减速系数。
        
        参数:
            group_profile: 群体特征分布
            group_type: 直接指定群体类型
        
        返回:
            (α_group = ∏_k α_k, 触发的群体详情字典)
        """
        alpha_group = 1.0
        triggered = {}
        
        if group_type and group_type in self.group_coefficients:
            # 直接指定群体
            config = self.group_coefficients[group_type]
            alpha_group *= config['value']
            triggered[group_type] = config['value']
        elif group_profile:
            # 按群体比例计算期望系数
            for key, config in self.group_coefficients.items():
                ratio_attr = f"{key}_ratio"
                if hasattr(group_profile, ratio_attr):
                    ratio = getattr(group_profile, ratio_attr)
                    # 期望值: 加权平均
                    # E[α] = ratio × α_k + (1-ratio) × 1.0
                    contrib = ratio * config['value'] + (1 - ratio) * 1.0
                    alpha_group *= contrib
                    triggered[f"{key}_ratio"] = ratio
        
        return alpha_group, triggered
    
    def compute_velocity(
        self,
        metrics: Dict[str, float],
        group_profile: Optional[GroupProfile] = None,
        group_type: Optional[str] = None,
    ) -> Dict[str, Union[float, Dict]]:
        """
        计算综合步行速度。
        
        公式: v_i = v_base × α_env × α_group
        
        参数:
            metrics: 步行环境指标 {SCR, BFD, EWW, SVI}
            group_profile: 群体特征分布
            group_type: 直接指定群体类型
        
        返回:
            {
                'v_i': 0.60,           # 最终速度 m/s
                'v_base': 1.2,          # 基准速度
                'alpha_env': 0.60,      # 环境系数
                'alpha_group': 0.60,    # 群体系数
                'alpha_total': 0.36,    # 总系数
                'triggered_env': {...},  # 触发的环境障碍
                'triggered_group': {...}, # 触发的群体脆弱性
                'travel_time_15m': 25.0, # 通行15米所需时间(秒)
                'severity': 'severe',   # 严重程度
            }
        """
        alpha_env, triggered_env = self.compute_environment_alpha(metrics)
        alpha_group, triggered_group = self.compute_group_alpha(
            group_profile, group_type
        )
        
        alpha_total = alpha_env * alpha_group
        v_i = self.v_base * alpha_total
        
        # 通行15米所需时间(秒)
        travel_time_15m = 15.0 / v_i if v_i > 0 else float('inf')
        
        # 严重程度评估
        if alpha_total >= 0.85:
            severity = 'excellent'
        elif alpha_total >= 0.70:
            severity = 'good'
        elif alpha_total >= 0.50:
            severity = 'moderate'
        elif alpha_total >= 0.30:
            severity = 'poor'
        else:
            severity = 'severe'
        
        return {
            'v_i': float(v_i),
            'v_base': float(self.v_base),
            'alpha_env': float(alpha_env),
            'alpha_group': float(alpha_group),
            'alpha_total': float(alpha_total),
            'triggered_env': triggered_env,
            'triggered_group': triggered_group,
            'travel_time_15m': float(travel_time_15m),
            'severity': severity,
        }
    
    def compute_population_weighted_velocity(
        self,
        metrics: Dict[str, float],
        population_df: pd.DataFrame,
        group_col: str = 'community_type',
    ) -> pd.DataFrame:
        """
        按社区人口结构计算加权平均步行速度。
        
        对每个小区，考虑人口结构分布，计算:
        - 高端住区: 老年人比例低 → 速度较高
        - 城中村: 老年人+低收入比例高 → 速度较低
        
        参数:
            metrics: 步行环境指标
            population_df: 小区人口数据(包含community_type等)
            group_col: 社区类型列名
        
        返回:
            带速度估算的小区数据
        """
        # 社区类型→群体比例映射
        TYPE_TO_GROUPS = {
            'high_end': {
                'elderly_ratio': 0.10,
                'wheelchair_ratio': 0.01,
                'child_ratio': 0.05,
                'caregiver_ratio': 0.02,
            },
            'commodity_housing': {
                'elderly_ratio': 0.15,
                'wheelchair_ratio': 0.02,
                'child_ratio': 0.08,
                'caregiver_ratio': 0.05,
            },
            'village': {
                'elderly_ratio': 0.22,
                'wheelchair_ratio': 0.04,
                'child_ratio': 0.12,
                'caregiver_ratio': 0.08,
            },
            'dormitory': {
                'elderly_ratio': 0.08,
                'wheelchair_ratio': 0.01,
                'child_ratio': 0.03,
                'caregiver_ratio': 0.03,
            },
            'apartments': {
                'elderly_ratio': 0.18,
                'wheelchair_ratio': 0.03,
                'child_ratio': 0.10,
                'caregiver_ratio': 0.06,
            },
        }
        
        results = []
        for _, row in population_df.iterrows():
            community_type = row.get(group_col, 'commodity_housing')
            group_dict = TYPE_TO_GROUPS.get(community_type, TYPE_TO_GROUPS['commodity_housing'])
            
            profile = GroupProfile(**group_dict)
            velocity_info = self.compute_velocity(metrics, group_profile=profile)
            
            result = {
                'community_id': row.get('id', row.get('community_id', 0)),
                'community_type': community_type,
                **velocity_info,
            }
            results.append(result)
        
        return pd.DataFrame(results)


# ==========================
# 可达性幻觉指数
# ==========================

class AccessibilityIllusionIndex:
    """
    综合可达性幻觉指数 (AI*_i) 计算器。
    
    AI*_i = [T_network(i)/v_i - T_promised] / T_promised × 100%
    
    核心思想:
    传统可达性模型假设匀速步行(v_base=1.2m/s)，忽略:
    1. 建筑密度和城市形态对实际通行速度的影响
    2. 弱势群体(老年人/轮椅)的特殊通行需求
    3. 街景质量对人行道实际可用性的影响
    
    AI*_i 揭示这种"统计可达性良好 vs 弱势群体实际体验差"的
    系统性偏差，即"可达性幻觉"。
    
    四象限分析:
        Q1 (True Accessibility):   SAI高 + GTA高 → 无幻觉
        Q2 (Underestimated):      SAI低 + GTA高 → 被低估
        Q3 (True Deprivation):    SAI低 + GTA低 → 真实剥夺
        Q4 (Accessibility Illusion): SAI高 + GTA低 → 幻觉区 ★
    """
    
    def __init__(
        self,
        velocity_model: Optional[GroupVelocityModel] = None,
        t_promised: float = T_PROMISED,
    ):
        self.velocity_model = velocity_model or GroupVelocityModel()
        self.t_promised = t_promised
    
    def compute_ai_star(
        self,
        network_time_base: float,
        velocity_info: Dict[str, float],
        group_type: Optional[str] = None,
    ) -> Dict[str, Union[float, str]]:
        """
        计算单个路段/小区的AI*_i。
        
        参数:
            network_time_base: 基于v_base=1.2m/s的网络通行时间(秒)
            velocity_info: velocity_model.compute_velocity()的输出
            group_type: 群体类型 (None = 基准群体)
        
        返回:
            {
                'AI_star': 25.0,        # AI*_i (%)
                'T_adjusted': 1125.0,    # 调整后通行时间(秒)
                'T_promised': 900.0,    # 承诺时间(秒)
                'gap_seconds': 225.0,     # 时间缺口(秒)
                'level': 'significant',  # 幻觉等级
                'extra_distance_m': 37.5,# 等效额外距离(米)
            }
        """
        v_i = velocity_info['v_i']
        
        # 调整后的通行时间
        # T_adjusted = T_base × (v_base / v_i)
        if v_i > 0:
            T_adjusted = network_time_base * (self.velocity_model.v_base / v_i)
        else:
            T_adjusted = float('inf')
        
        # AI*_i 计算
        gap_seconds = T_adjusted - self.t_promised
        AI_star = (gap_seconds / self.t_promised) * 100.0
        
        # 等效额外距离(米)
        extra_distance_m = abs(gap_seconds) * self.velocity_model.v_base if gap_seconds > 0 else 0
        
        # 幻觉等级
        if AI_star < -20:
            level = 'superior'       # 超预期
        elif AI_star < 0:
            level = 'accurate'       # 准确
        elif AI_star < 10:
            level = 'minor'          # 轻微
        elif AI_star < 30:
            level = 'significant'     # 显著
        elif AI_star < 50:
            level = 'severe'         # 严重
        else:
            level = 'critical'       # 临界
        
        return {
            'AI_star': float(AI_star),
            'T_adjusted': float(T_adjusted),
            'T_promised': float(self.t_promised),
            'gap_seconds': float(gap_seconds),
            'level': level,
            'v_i': v_i,
            'extra_distance_m': float(extra_distance_m),
        }
    
    def compute_for_network(
        self,
        network_edges_df: pd.DataFrame,
        metrics_df: pd.DataFrame,
        community_df: pd.DataFrame,
        edge_id_col: str = 'edge_id',
        lng_col: str = 'lng',
        lat_col: str = 'lat',
        network_time_col: str = 'travel_time_base',
        group_type_col: Optional[str] = 'community_type',
    ) -> pd.DataFrame:
        """
        对整个路网计算AI*_i。
        
        参数:
            network_edges_df: 路网边数据(包含travel_time_base)
            metrics_df: 步行环境指标(SCR/BFD/EWW/SVI)
            community_df: 小区人口数据
            其他: 列名映射
        
        返回:
            带AI*_i的增强路网DataFrame
        """
        print("=" * 60)
        print("计算综合可达性幻觉指数 AI*_i")
        print("=" * 60)
        
        result = network_edges_df.copy()
        
        # Step 1: 为每个边匹配步行环境指标
        # 基于边的中点坐标匹配最近的metrics
        if 'lng_mid' not in result.columns or 'lat_mid' not in result.columns:
            if 'u_lng' in result.columns and 'v_lng' in result.columns:
                result['lng_mid'] = (result['u_lng'] + result['v_lng']) / 2
                result['lat_mid'] = (result['u_lat'] + result['v_lat']) + result['v_lng']
            else:
                result['lng_mid'] = result.get(lng_col, result.iloc[:, 0])
                result['lat_mid'] = result.get(lat_col, result.iloc[:, 1])
        
        # 匹配: 每个边 → 最近的采样点指标
        if len(metrics_df) > 0:
            print(f"\n  匹配边与步行环境指标...")
            from scipy.spatial import cKDTree
            
            metric_coords = metrics_df[['lng', 'lat']].values
            edge_coords = result[['lng_mid', 'lat_mid']].values
            
            tree = cKDTree(metric_coords)
            distances, indices = tree.query(edge_coords, k=1)
            
            for col in ['SCR', 'BFD', 'EWW', 'SVI', 'WES']:
                if col in metrics_df.columns:
                    matched_values = metrics_df.iloc[indices][col].values
                    result[f'matched_{col}'] = np.where(distances < 0.005, matched_values, np.nan)
            
            result['matched_distance'] = distances
        else:
            for col in ['SCR', 'BFD', 'EWW', 'SVI']:
                result[f'matched_{col}'] = np.nan
        
        # Step 2: 计算各类群体的AI*_i
        print(f"\n  计算各群体AI*_i...")
        
        for group_type in ['robust', 'elderly', 'wheelchair']:
            ai_star_col = f'AI_star_{group_type}'
            ai_star_vals = []
            
            for _, row in result.iterrows():
                metrics = {
                    'SCR': row.get('matched_SCR', 0.5),
                    'BFD': row.get('matched_BFD', 0.5),
                    'EWW': row.get('matched_EWW', 3.0),
                    'SVI': row.get('matched_SVI', 0.5),
                }
                
                # 填充缺失值
                for k in metrics:
                    if pd.isna(metrics[k]):
                        metrics[k] = 0.5 if k in ['SCR', 'BFD', 'SVI'] else 3.0
                
                velocity_info = self.velocity_model.compute_velocity(
                    metrics, group_type=group_type
                )
                
                network_time = row.get(network_time_col, 0)
                if pd.isna(network_time):
                    network_time = 0
                
                ai_info = self.compute_ai_star(
                    network_time, velocity_info, group_type=group_type
                )
                ai_star_vals.append(ai_info['AI_star'])
            
            result[ai_star_col] = ai_star_vals
        
        # Step 3: AI*_i统计
        print(f"\n  AI*_i 统计:")
        for group_type in ['robust', 'elderly', 'wheelchair']:
            col = f'AI_star_{group_type}'
            vals = result[col].dropna()
            if len(vals) > 0:
                sig = (vals > 20).mean() * 100
                sev = (vals > 40).mean() * 100
                print(f"  {group_type:12s}: mean={vals.mean():+.1f}%, "
                      f"幻觉区(>20%)={sig:.1f}%, 严重幻觉(>40%)={sev:.1f}%")
        
        return result
    
    def quadrant_analysis(
        self,
        combined_df: pd.DataFrame,
        sai_col: str = 'SAI',
        gta_col: str = 'GTA',
        aii_col: str = 'AI_star_robust',
    ) -> Dict[str, Any]:
        """
        四象限分析。
        
        结合SAI(统计可达性)和GTA(真实可达性),
        将区域分为四个类型:
            Q1: 高SAI + 高GTA → True Accessibility
            Q2: 低SAI + 高GTA → Underestimated  
            Q3: 低SAI + 低GTA → True Deprivation
            Q4: 高SAI + 低GTA → Accessibility Illusion ★
        """
        print("\n  四象限分析:")
        
        sai_median = combined_df[sai_col].median()
        gta_median = combined_df[gta_col].median()
        
        conditions = [
            (combined_df[sai_col] >= sai_median) & (combined_df[gta_col] >= gta_median),
            (combined_df[sai_col] < sai_median) & (combined_df[gta_col] >= gta_median),
            (combined_df[sai_col] < sai_median) & (combined_df[gta_col] < gta_median),
            (combined_df[sai_col] >= sai_median) & (combined_df[gta_col] < gta_median),
        ]
        labels = ['Q1-TrueAccessibility', 'Q2-Underestimated', 
                  'Q3-TrueDeprivation', 'Q4-AccessibilityIllusion']
        
        combined_df['quadrant'] = np.select(conditions, labels, default='Unknown')
        
        results = {}
        for label in labels:
            subset = combined_df[combined_df['quadrant'] == label]
            results[label] = {
                'count': len(subset),
                'pct': 100 * len(subset) / len(combined_df),
                'mean_SAI': subset[sai_col].mean() if len(subset) > 0 else 0,
                'mean_GTA': subset[gta_col].mean() if len(subset) > 0 else 0,
                'mean_AIi': subset[aii_col].mean() if len(subset) > 0 else 0,
            }
            print(f"  {label:25s}: {len(subset):4d} ({100*len(subset)/len(combined_df):5.1f}%) "
                  f"AI*={results[label]['mean_AIi']:+.1f}%")
        
        return results


# ==========================
# 端到端分析
# ==========================

def run_complete_analysis(
    metrics_csv: Optional[str] = None,
    network_edges_csv: Optional[str] = None,
    community_csv: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """
    端到端运行完整分析流程。
    
    流程:
    1. 加载步行环境指标
    2. 对每类群体计算差异化速度
    3. 计算AI*_i幻觉指数
    4. 按小区汇总
    5. 四象限分析
    """
    print("=" * 60)
    print("步行环境 + 速度模型 + 可达性幻觉指数 完整分析")
    print("=" * 60)
    
    # 初始化模型
    velocity_model = GroupVelocityModel()
    aii_calculator = AccessibilityIllusionIndex(velocity_model)
    
    # Step 1: 加载数据
    metrics_df = None
    if metrics_csv and os.path.exists(metrics_csv):
        print(f"\n加载步行环境指标: {metrics_csv}")
        metrics_df = pd.read_csv(metrics_csv)
        print(f"  {len(metrics_df)} 条记录")
    
    network_df = None
    if network_edges_csv and os.path.exists(network_edges_csv):
        print(f"\n加载路网数据: {network_edges_csv}")
        network_df = pd.read_csv(network_edges_csv)
        print(f"  {len(network_df)} 条边")
    
    community_df = None
    if community_csv and os.path.exists(community_csv):
        print(f"\n加载小区数据: {community_csv}")
        community_df = pd.read_csv(community_csv)
        print(f"  {len(community_df)} 个小区")
    
    # Step 2: 生成模拟指标(无真实数据时)
    if metrics_df is None or len(metrics_df) == 0:
        print("\n[模拟模式] 生成合成步行环境指标...")
        from .streetview_acquisition import SimulatedStreetView, NetworkSampler
        
        # 使用南山区楼栋数据校准
        gaode_csv = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\building_data\南山区-房屋楼栋基础数据_2920004003598.csv'
        if os.path.exists(gaode_csv):
            bdf = pd.read_csv(gaode_csv, dtype=str, keep_default_na=False)
            bdf['lng'] = pd.to_numeric(bdf['中心坐标'], errors='coerce')
            bdf['lat'] = pd.to_numeric(bdf['中心点坐标'], errors='coerce')
            bdf = bdf.dropna(subset=['lng', 'lat'])
        else:
            bdf = None
        
        # 生成随机采样点
        rng = np.random.default_rng(42)
        n_samples = 500
        lng_range = (113.85, 114.45)
        lat_range = (22.40, 22.80)
        points = list(zip(
            rng.uniform(*lng_range, n_samples),
            rng.uniform(*lat_range, n_samples)
        ))
        
        sim = SimulatedStreetView()
        metrics_df = sim.batch_generate(points, building_df=bdf)
        print(f"  生成 {len(metrics_df)} 条模拟指标")
    
    # Step 3: 计算AI*_i
    if network_df is not None:
        print("\n对路网计算AI*_i...")
        enhanced_network = aii_calculator.compute_for_network(
            network_df,
            metrics_df,
            community_df or pd.DataFrame(),
        )
    else:
        enhanced_network = None
    
    # Step 4: 按小区汇总
    if community_df is not None and len(metrics_df) > 0:
        print("\n按小区汇总步行环境指标...")
        community_results = []
        
        for _, comm in community_df.iterrows():
            comm_lng = comm.get('lng', 0)
            comm_lat = comm.get('lat', 0)
            
            if comm_lng == 0 or comm_lat == 0:
                community_results.append({'community_id': comm.get('id', 0), **comm.to_dict()})
                continue
            
            # 找最近的采样点
            distances = np.sqrt(
                (metrics_df['lng'].values - comm_lng) ** 2 +
                (metrics_df['lat'].values - comm_lat) ** 2
            )
            nearest_idx = distances.argmin()
            nearest_metrics = metrics_df.iloc[nearest_idx].to_dict()
            
            # 计算各群体速度
            velocity_robust = velocity_model.compute_velocity(
                nearest_metrics, group_type='robust'
            )
            velocity_elderly = velocity_model.compute_velocity(
                nearest_metrics, group_type='elderly'
            )
            velocity_wheelchair = velocity_model.compute_velocity(
                nearest_metrics, group_type='wheelchair'
            )
            
            # AI*_i (假设15分钟通行圈)
            network_time_base = T_PROMISED  # 基准: 900秒
            
            ai_robust = aii_calculator.compute_ai_star(
                network_time_base, velocity_robust, 'robust'
            )
            ai_elderly = aii_calculator.compute_ai_star(
                network_time_base, velocity_elderly, 'elderly'
            )
            ai_wheelchair = aii_calculator.compute_ai_star(
                network_time_base, velocity_wheelchair, 'wheelchair'
            )
            
            result = {
                'community_id': comm.get('id', comm.get('community_id', 0)),
                'lng': comm_lng,
                'lat': comm_lat,
                'community_type': comm.get('community_type', 'unknown'),
                **nearest_metrics,
                'v_robust': velocity_robust['v_i'],
                'v_elderly': velocity_elderly['v_i'],
                'v_wheelchair': velocity_wheelchair['v_i'],
                'AI_star_robust': ai_robust['AI_star'],
                'AI_star_elderly': ai_elderly['AI_star'],
                'AI_star_wheelchair': ai_wheelchair['AI_star'],
                'severity_robust': velocity_robust['severity'],
                'severity_elderly': velocity_elderly['severity'],
                'severity_wheelchair': velocity_wheelchair['severity'],
            }
            community_results.append(result)
        
        community_results_df = pd.DataFrame(community_results)
        
        # 保存
        if output_dir:
            out_path = os.path.join(output_dir, 'community_accessibility_illusion.csv')
            community_results_df.to_csv(out_path, index=False, encoding='utf-8-sig')
            print(f"  已保存: {out_path}")
        
        # 统计
        print(f"\n  汇总统计:")
        print(f"  有效小区: {len(community_results_df)}")
        
        for group in ['robust', 'elderly', 'wheelchair']:
            ai_col = f'AI_star_{group}'
            if ai_col in community_results_df.columns:
                vals = community_results_df[ai_col].dropna()
                illusion_pct = (vals > 20).mean() * 100
                severe_pct = (vals > 40).mean() * 100
                print(f"  {group:12s}: mean={vals.mean():+.1f}%, "
                      f"illusion={illusion_pct:.1f}%, severe={severe_pct:.1f}%")
        
        return {
            'metrics': metrics_df,
            'network': enhanced_network,
            'community': community_results_df,
        }
    
    return {
        'metrics': metrics_df,
        'network': enhanced_network,
        'community': None,
    }


# ==========================
# CLI
# ==========================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='群体差异化速度模型 + 可达性幻觉指数')
    parser.add_argument('--metrics', default=None, help='步行环境指标CSV')
    parser.add_argument('--network', default=None, help='路网边CSV')
    parser.add_argument('--community', default=None, help='小区数据CSV')
    parser.add_argument('--output', default='.', help='输出目录')
    
    args = parser.parse_args()
    
    results = run_complete_analysis(
        metrics_csv=args.metrics,
        network_edges_csv=args.network,
        community_csv=args.community,
        output_dir=args.output,
    )
