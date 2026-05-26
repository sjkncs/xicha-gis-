"""
=======================================================================
GIS 专用分析器 - 基于多模态大模型的空间分析解读
=======================================================================
"""
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


# =======================================================================
# 地图可视化分析器
# =======================================================================

class MapAnalyzer:
    """
    分析 Folium 交互地图截图，识别空间分布模式
    
    功能：
    - 识别热力图高密度区域
    - 标注显著的空间聚集区
    - 描述空间格局（中心-外围、轴向等）
    - 检测异常值和空间 outliers
    
    典型用法：
    >>> from llm_integration import MapAnalyzer, quick_analyze
    >>> 
    >>> analyzer = MapAnalyzer(config)
    >>> 
    >>> # 分析步行可达性热力图
    >>> result = analyzer.analyze_accessibility_map(
    ...     map_screenshot=accessibility_map,
    ...     metric_name="15分钟可达性指数",
    ...     study_area="深圳市南山区"
    ... )
    >>> print(result.content)
    """
    
    def __init__(self, client):
        self.client = client
        from .llm_client import AnalysisType
        self.AnalysisType = AnalysisType
    
    def analyze_accessibility_map(
        self,
        map_screenshot: Any,
        metric_name: str = "可达性指数",
        study_area: str = "",
        threshold_pct: Optional[float] = None,
    ) -> 'AnalysisResult':
        """
        分析步行可达性热力图
        
        Args:
            map_screenshot: 地图截图（图片路径/bytes/plt.Figure）
            metric_name: 指标名称
            study_area: 研究区域
            threshold_pct: 可达性低于该百分位的区域视为"低可达性"
        """
        from .llm_client import AnalysisType
        
        prompt = f"""你是一位城市地理信息系统（GIS）专家。请分析这张{metric_name}的空间分布热力图。

研究区域：{study_area}

请提供以下方面的详细分析：
1. **高值区域（高可达性）**：识别图中颜色最深/最红的区域，描述它们的地理位置特征（如靠近CBD、地铁站附近等）
2. **低值区域（低可达性）**：识别图中颜色最浅/最蓝的区域，描述它们的地理位置特征（如城市边缘、工业区等）
3. **空间格局**：整体分布是否呈现中心-外围模式？还是多核心分布？是否有明显的空间走廊？
4. **公平性问题**：低可达性区域是否与特定人群（如城中村、老旧小区）重合？
5. **政策含义**：基于图中模式，提出具体的空间干预建议

请用中文回答，结构清晰。"""
        
        return self.client.analyze_image(
            map_screenshot, prompt, AnalysisType.ACCESSIBILITY
        )
    
    def analyze_poi_density_map(
        self,
        map_screenshot: Any,
        poi_category: str = "设施",
        study_area: str = "",
    ) -> 'AnalysisResult':
        """分析 POI 密度分布图"""
        from .llm_client import AnalysisType
        
        prompt = f"""你是一位城市地理信息系统（GIS）专家。请分析这张{poi_category}密度分布图。

研究区域：{study_area}

请识别并描述：
1. {poi_category}的密度分布模式（单中心？多中心？轴向？）
2. 密度最高的区域位置
3. 明显的"设施盲区"（密度接近零的区域）
4. 与交通网络（道路、地铁）的空间关系
5. 这些模式对15分钟城市生活的含义

请用中文回答。"""
        
        return self.client.analyze_image(
            map_screenshot, prompt, AnalysisType.MAP_VISUALIZATION
        )
    
    def compare_multiple_maps(
        self,
        map_screenshots: List[Any],
        labels: List[str],
        comparison_focus: str = "可达性",
    ) -> 'AnalysisResult':
        """
        对比分析多张地图（时间对比或情景对比）
        
        Args:
            map_screenshots: 多张地图截图
            labels: 每张地图的标签（如 ["白天模式", "夜间模式"]）
            comparison_focus: 对比重点
        """
        from .llm_client import AnalysisType
        
        label_text = "\n".join([f"- {l}" for l in labels])
        
        prompt = f"""你是一位城市地理信息系统（GIS）专家。请对比分析以下{comparison_focus}地图，找出空间格局的差异。

{comparison_focus}场景：
{label_text}

请提供：
1. **空间格局变化**：{comparison_focus}的空间分布是否存在显著差异？
2. **变化热点区域**：哪些区域的变化最显著？
3. **时间/情景效应**：差异是否呈现规律性（如白天vs夜间、节假日vs工作日）？
4. **公平性影响**：变化是否加剧或缓解了空间不公平？
5. **关键发现**：1-2个最重要的发现

请用中文回答，引用地图编号（如"地图1中..."）进行说明。"""
        
        return self.client.analyze_multiple_images(
            map_screenshots, prompt, AnalysisType.TIME_SERIES
        )


# =======================================================================
# 统计结果解读器
# =======================================================================

class StatsInterpreter:
    """
    解读 GIS 统计分析结果（Moran's I、Gini、ANOVA 等）
    转化为学术级别的文字描述
    """
    
    def __init__(self, client):
        self.client = client
        from .llm_client import AnalysisType
        self.AnalysisType = AnalysisType
    
    def interpret_morans_i(
        self,
        stat_fig: Any,
        morans_i_value: float,
        p_value: float,
        z_score: Optional[float] = None,
        variable_name: str = "可达性",
        study_area: str = "",
    ) -> 'AnalysisResult':
        """
        解读 Moran's I 全局空间自相关结果
        
        Args:
            stat_fig: 统计图（Moran's I 散点图/直方图）
            morans_i_value: Moran's I 统计值（如 0.35）
            p_value: p 值（如 0.001）
            z_score: z 分数
            variable_name: 变量名称
            study_area: 研究区域
        """
        from .llm_client import AnalysisType
        
        significance = "显著" if p_value < 0.05 else "不显著"
        pattern = "聚集" if morans_i_value > 0 else "分散"
        
        prompt = f"""作为城市空间统计分析专家，请解读以下 Moran's I 空间自相关分析结果。

**研究变量**：{variable_name}
**研究区域**：{study_area}
**统计结果**：
- Moran's I = {morans_i_value:.4f}
- p-value = {p_value:.4f}（{significance}，α=0.05）
{z_score is not None and f"- z-score = {z_score:.4f}" or ""}

请用学术语言（适合 SCI 期刊）描述以下内容：
1. **空间格局判定**：Moran's I = {morans_i_value:.4f} 且 p = {p_value:.4f} 表明{variable_name}在空间上呈{"显著聚集模式（高值与高值相邻、低值与低值相邻）" if morans_i_value > 0 and p_value < 0.05 else "显著分散模式（高值被低值包围）" if morans_i_value < 0 and p_value < 0.05 else "无显著空间自相关"}
2. **聚集程度解读**：Moran's I 数值的大小表明{"较强的空间依赖性" if abs(morans_i_value) > 0.5 else "中等程度的空间依赖性" if abs(morans_i_value) > 0.2 else "较弱的空间依赖性"}
3. **空间模式含义**：这种空间格局对15分钟城市规划和公平性分析意味着什么？
4. **方法论贡献**：该结果支持了空间建模的必要性

请用英文（适合 SCI 期刊 Methods/Results 部分）描述关键数值，
同时用中文提供详细解读。"""
        
        return self.client.analyze_image(stat_fig, prompt, AnalysisType.SPATIAL_AUTOCORRELATION)
    
    def interpret_gini_coefficient(
        self,
        chart_fig: Any,
        gini_value: float,
        study_area: str = "",
        metric_name: str = "设施可达性",
    ) -> 'AnalysisResult':
        """
        解读 Gini 系数和洛伦兹曲线
        
        Args:
            chart_fig: 洛伦兹曲线图
            gini_value: Gini 系数（如 0.35）
            study_area: 研究区域
            metric_name: 指标名称
        """
        from .llm_client import AnalysisType
        
        inequality_level = (
            "高度不平等" if gini_value > 0.4
            else "中等不平等" if gini_value > 0.25
            else "相对平等"
        )
        
        prompt = f"""作为城市公平性分析专家，请解读以下{metric_name}的 Gini 系数和洛伦兹曲线。

**研究区域**：{study_area}
**指标**：{metric_name}
**Gini 系数**：{gini_value:.4f}

Gini 系数含义解读：
- 0.00 = 完全平等（每个人获得的设施数量相同）
- 1.00 = 完全不平等（所有设施集中在一个人手中）
- 0.20-0.30 = 相对平等
- 0.30-0.40 = 中等不平等
- >0.40 = 高度不平等

你的 Gini = {gini_value:.4f}，属于"{inequality_level}"。

请提供：
1. **不平等程度判定**：结合 Gini 数值和洛伦兹曲线形状，说明不平等程度
2. **受影响的群体**：哪部分人口受到的不平等影响最大？（曲线最弯曲处对应的群体）
3. **空间维度**：这种不平等是否存在空间聚集性？（哪些区域的不平等更严重？）
4. **政策建议**：如何将 Gini 系数的改善纳入15分钟城市政策？
5. **学术价值**：与已有文献对比，该 Gini 水平处于什么位置？

请用中文回答，兼顾学术严谨性和政策可操作性。"""
        
        return self.client.analyze_image(chart_fig, prompt, AnalysisType.EQUITY_ANALYSIS)
    
    def interpret_anova_results(
        self,
        stats_data: Union[Dict, pd.DataFrame],
        group_names: List[str],
        f_statistic: float,
        p_value: float,
        effect_size: Optional[float] = None,
    ) -> 'AnalysisResult':
        """
        解读 ANOVA / Kruskal-Wallis 检验结果
        
        Args:
            stats_data: 分组数据（Dict: {组名: [值列表]} 或 DataFrame）
            group_names: 分组名称
            f_statistic: F 统计量
            p_value: p 值
            effect_size: 效应量（如 eta-squared）
        """
        from .llm_client import AnalysisType
        
        prompt = f"""作为城市统计分析专家，请解读以下 ANOVA / Kruskal-Wallis 检验结果。

**分组**：{', '.join(group_names)}
**F 统计量**：{f_statistic:.4f}
**p 值**：{p_value:.6f}（{"显著" if p_value < 0.05 else "不显著"}，α=0.05）
{effect_size is not None and f"**效应量 (η²)**：{effect_size:.4f}" or ""}

请提供：
1. **组间差异判定**：各组之间是否存在统计显著差异？
2. **效应量解读**：{"实际效应是否具有实质性意义（η² > 0.14 为大效应）" if effect_size else "请结合 F 值和样本量综合判断实际意义"}
3. **组间差异模式**：哪一组显著高于/低于其他组？（如适用）
4. **15分钟城市含义**：组间差异反映了什么社会公平问题？
5. **SCI 写作建议**：如何简洁地在论文 Results 部分描述这一结果？

请用中文回答。"""
        
        return self.client.generate_text(
            prompt=prompt,
            system_prompt="你是一位城市空间分析专家，熟悉 GIS、空间统计和城市公平性研究。请提供严谨的学术解读。",
        )


# =======================================================================
# POI 数据质量评估器
# =======================================================================

class POIQualityAssessor:
    """
    自动评估 POI 数据的质量和完整性
    """
    
    def __init__(self, client):
        self.client = client
    
    def assess_poi_coverage(
        self,
        map_fig: Any,
        poi_count: int,
        area_sq_km: float,
        category: str = "设施",
        expected_density: Optional[float] = None,
    ) -> 'AnalysisResult':
        """评估 POI 覆盖度"""
        from .llm_client import AnalysisType
        
        density = poi_count / area_sq_km if area_sq_km > 0 else 0
        
        prompt = f"""作为城市数据质量评估专家，请评估以下 {category} POI 数据的覆盖度。

**数据概况**：
- {category} 数量：{poi_count} 个
- 研究区域面积：{area_sq_km:.2f} km²
- 密度：{density:.1f} 个/km²
{"- 参考对比密度（如深圳市平均）：" + str(expected_density) + " 个/km²" if expected_density else ""}

请评估：
1. **密度合理性**：当前密度是否合理？过低可能意味着数据缺失，过高可能存在重复
2. **空间分布**：设施是否覆盖研究区域的各个部分？还是存在明显的"数据空白区"？
3. **潜在问题**：可能存在哪些数据质量问题（缺失、过期、重复、定位偏差）？
4. **数据增强建议**：如何补充或验证数据？（如补充人工采集、高德/百度 API 交叉验证）
5. **研究可靠性**：该数据质量是否足以支持15分钟城市分析？哪些结论应谨慎提出？

请用中文回答。"""
        
        return self.client.analyze_image(map_fig, prompt, AnalysisType.POI_QUALITY)


# =======================================================================
# 可达性指标解读器
# =======================================================================

class AccessibilityInterpreter:
    """
    将可达性量化指标转化为政策建议和学术描述
    """
    
    def __init__(self, client):
        self.client = client
    
    def interpret_accessibility_metrics(
        self,
        results_fig: Any,
        avg_accessibility: float,
        median_accessibility: float,
        gini: float,
        vulnerable_groups: Dict[str, float],
        study_area: str = "",
    ) -> 'AnalysisResult':
        """解读可达性综合指标"""
        from .llm_client import AnalysisType
        
        vg_text = "\n".join([f"- {k}: 平均可达性 {v:.3f}" for k, v in vulnerable_groups.items()])
        
        prompt = f"""作为城市公平性研究专家，请解读以下可达性分析结果。

**研究区域**：{study_area}
**总体指标**：
- 平均可达性：{avg_accessibility:.3f}
- 中位数可达性：{median_accessibility:.3f}
- Gini 系数：{gini:.3f}

**脆弱群体可达性**：
{vg_text}

请提供：
1. **整体水平判定**：平均可达性处于什么水平？（高/中/低）
2. **不平等分析**：Gini 系数说明了什么问题？哪些群体被"平均"了？
3. **脆弱群体分析**：弱势群体的可达性与平均水平有多大差距？这个差距意味着什么实际影响？
4. **SCI 写作**：如何用学术语言描述这些发现？（适合 Results + Discussion 部分）
5. **政策建议**：基于分析结果，提出3条有针对性的空间政策建议

请用中文回答，同时提供英文 SCI 摘要段落。"""
        
        return self.client.analyze_image(results_fig, prompt, AnalysisType.ACCESSIBILITY)


# =======================================================================
# LISA 聚类分析解读
# =======================================================================

class LISAMapAnalyzer:
    """
    解读 Local Moran's I (LISA) 聚类分析结果
    """
    
    def __init__(self, client):
        self.client = client
    
    def interpret_lisa_cluster_map(
        self,
        lisa_map_fig: Any,
        quadrant_stats: Optional[Dict] = None,
        study_area: str = "",
    ) -> 'AnalysisResult':
        """
        解读 LISA 聚类图
        
        Args:
            lisa_map_fig: LISA 聚类地图（4色：HH/HL/LH/LL）
            quadrant_stats: 各象限统计（Dict: {"HH": n, "HL": n, "LH": n, "LL": n}）
            study_area: 研究区域
        """
        from .llm_client import AnalysisType
        
        quad_text = ""
        if quadrant_stats:
            quad_text = "**聚类统计**：\n" + "\n".join([
                f"- {k}: {v} 个小区"
                for k, v in quadrant_stats.items()
            ])
        
        prompt = f"""作为城市空间分析专家，请解读以下 LISA 聚类分析结果。

**研究区域**：{study_area}
{quad_text}

LISA 聚类图说明：
- **HH (高-高)**：高可达性区域被其他高可达性区域包围（热点）
- **HL (高-低)**：高可达性区域被低可达性区域包围（空间异质性）
- **LH (低-高)**：低可达性区域被高可达性区域包围（空间异质性）
- **LL (低-低)**：低可达性区域被其他低可达性区域包围（冷点）

请识别并描述：
1. **热点区域 (HH)**：识别图中红色/深色区域，它们代表哪些地理位置？
2. **冷点区域 (LL)**：识别图中蓝色/浅色区域，这些区域的居民面临哪些可达性挑战？
3. **空间异常 (HL/LH)**：识别与周围环境显著不同的区域（如被低值包围的高值"孤岛"）
4. **聚类模式**：HH 和 LL 的分布是否呈现特定的空间规律？（如沿交通轴线分布）
5. **公平性含义**：LL 聚集区是否与城中村、老旧小区重合？
6. **政策干预靶区**：基于聚类分析，哪些区域应优先进行设施优化？

请用中文回答，引用地图方位进行描述。"""
        
        return self.client.analyze_image(lisa_map_fig, prompt, AnalysisType.LISA_CLUSTER)


# =======================================================================
# 图表辅助生成器
# =======================================================================

class ChartAssistant:
    """
    辅助生成 SCI 级别的图表和描述文字
    """
    
    def __init__(self, client):
        self.client = client
    
    def describe_figure_for_paper(
        self,
        figure: Any,
        figure_type: str,
        context: str = "",
    ) -> 'AnalysisResult':
        """
        为图表生成学术描述文字
        
        Args:
            figure: 图表
            figure_type: 图表类型（如 "图3a", "洛伦兹曲线", "LISA聚类图"）
            context: 研究背景（如"南山区15分钟城市时间贫困研究"）
        """
        from .llm_client import AnalysisType
        
        prompt = f"""作为地理信息科学（GIS）论文写作专家，请为以下{figure_type}生成学术描述文字。

研究背景：{context}

请生成：
1. **图注 (Caption)**：简洁、准确的英文图注（适合 SCI 期刊）
2. **Results 部分描述**：约 2-3 句的英文 Results 描述
3. **方法说明**：图表中使用的具体方法（如投影系统、分类方法、统计检验）
4. **图例解读**：图表中各颜色/符号的含义
5. **关键发现引用句**：可直接引用的英文发现描述句

请用英文生成主要输出（适合 SCI 写作），中文提供补充说明。"""
        
        return self.client.analyze_image(figure, prompt, AnalysisType.CHART_GENERATION)
    
    def suggest_visualization_improvements(
        self,
        figure: Any,
        target_journal: str = "CEUS",
    ) -> 'AnalysisResult':
        """
        建议图表改进（使图表更符合 SCI 标准）
        
        Args:
            figure: 原始图表
            target_journal: 目标期刊
        """
        from .llm_client import AnalysisType
        
        prompt = f"""作为学术出版专家（熟悉 Computers, Environment and Urban Systems 等地理学期刊），
请审阅以下图表的可视化质量，并提出改进建议。

目标期刊：{target_journal}

请检查并建议改进：
1. **色彩方案**：是否使用色盲友好配色？是否符合期刊风格？
2. **图例设计**：图例是否清晰？是否需要添加更多标注？
3. **字体大小**：坐标轴标签、图例文字大小是否合适？
4. **比例尺/指北针**：是否需要添加？（如为地图）
5. **布局**：图表整体布局是否协调？
6. **信息密度**：是否过于拥挤或过于稀疏？
7. **具体改进建议**：列出 3-5 条具体可操作的改进建议

请用中文回答。"""
        
        return self.client.analyze_image(figure, prompt, AnalysisType.CHART_GENERATION)


# =======================================================================
# 代码审查器
# =======================================================================

class CodeReviewer:
    """
    GIS 代码的深度学习辅助审查
    """
    
    def __init__(self, client):
        self.client = client
    
    def review_spatial_analysis_code(
        self,
        code_snippet: str,
        analysis_goal: str = "",
    ) -> 'AnalysisResult':
        """审查 GIS 空间分析代码"""
        from .llm_client import AnalysisType
        
        prompt = f"""作为 Python GIS 开发专家（熟悉 OSMnx、GeoPandas、NetworkX、libpysal、esda），
请审查以下空间分析代码。

分析目标：{analysis_goal or "未指定"}

请检查：
1. **正确性**：空间分析逻辑是否正确？（CRS 转换、拓扑关系、权重矩阵构建等）
2. **效率**：是否存在性能问题？（大规模网络计算、空间连接等）
3. **可复现性**：代码是否足够清晰，便于复现？
4. **潜在 bug**：是否有边界情况未处理？（空图、缺失值、零除等）
5. **改进建议**：提出具体的代码优化建议

请用中文回答，包含具体代码示例。"""
        
        return self.client.generate_text(
            prompt=f"{prompt}\n\n代码片段：\n```python\n{code_snippet}\n```",
            system_prompt="你是一位专业的 GIS 空间分析专家，专注于 Python 生态（OSMnx, GeoPandas, NetworkX, libpysal, esda）。提供严谨、实用的代码审查意见。",
        )
    
    def suggest_optimization(
        self,
        slow_code_snippet: str,
        bottleneck_description: str = "",
    ) -> 'AnalysisResult':
        """为性能瓶颈提供优化建议"""
        from .llm_client import AnalysisType
        
        prompt = f"""以下 GIS 分析代码存在性能问题，请提供优化建议。

瓶颈描述：{bottleneck_description or "未具体说明"}

代码：
```python
{slow_code_snippet}
```

请提供：
1. **瓶颈分析**：最耗时的操作是什么？
2. **优化策略**：并行化、缓存、向量化、算法改进？
3. **具体实现**：给出优化后的代码
4. **预期收益**：优化后预计提速多少？

请用中文回答，包含优化代码。"""
        
        return self.client.generate_text(
            prompt=prompt,
            system_prompt="你是一位 Python 性能优化专家，专注于 GIS 空间计算。",
        )
