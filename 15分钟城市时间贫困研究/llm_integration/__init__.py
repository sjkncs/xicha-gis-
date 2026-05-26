"""
=======================================================================
GIS 智能定位 - 多模态大模型集成框架
Multimodal LLM Integration Framework
=======================================================================

功能模块：
1. 地图可视化分析 - 分析 Folium 交互地图，识别空间模式
2. 统计结果解读 - 解读 Moran's I、Gini系数、ANOVA 等统计结果
3. POI 数据质量评估 - 自动评估和标注 POI 数据的质量问题
4. 可达性指标解读 - 将量化可达性结果转化为政策建议
5. 科研图表生成 - 辅助生成 SCI 级别的图表和描述文字
6. 代码审查与优化 - 深度学习辅助的 GIS 代码审查
7. 空间自相关分析 - LISA 聚类结果的多模态解读

支持的多模态模型：
- OpenAI GPT-4V / GPT-4o (视觉)
- Claude (视觉) - via Anthropic API
- 通义千问 VL (视觉)
- DeepSeek-VL (视觉)
- SiliconFlow (聚合多种模型)
- 本地部署模型 (如 LLaVA, CogVLM)

快速开始：
>>> from llm_integration import LLMConfig, create_llm_client, quick_analyze
>>> config = LLMConfig.load()  # 从 config.json 加载
>>> config.api_key = "your-api-key"  # 设置 API Key
>>> 
>>> # 快速分析地图
>>> result = quick_analyze(config, "map.png", "分析这张可达性热力图")
>>> print(result.content)

详细用法请参考 example_usage.py 和 README.md

=======================================================================
"""
from .llm_client import (
    BaseLLMClient,
    OpenAIClient,
    DashScopeClient,
    SiliconFlowClient,
    LocalLLMClient,
    LLMProvider,
    AnalysisType,
    AnalysisResult,
    CacheManager,
    ImageProcessor,
    create_llm_client,
    quick_analyze,
    MultimodalLLMClient,  # 保留别名兼容性
)
from .config import (
    LLMConfig,
    PRESETS,
    get_config_from_env,
    create_config_wizard,
    save_api_key,
)
from .prompts import (
    SYSTEM_PROMPTS,
    USER_PROMPTS,
    build_prompt,
    build_stats_table,
)
from .analyzers import (
    MapAnalyzer,
    StatsInterpreter,
    LISAMapAnalyzer,
    AccessibilityInterpreter,
    POIQualityAssessor,
    ChartAssistant,
    CodeReviewer,
)

__all__ = [
    # 核心客户端
    'BaseLLMClient',
    'OpenAIClient',
    'DashScopeClient',
    'SiliconFlowClient',
    'LocalLLMClient',
    'MultimodalLLMClient',
    'create_llm_client',
    'quick_analyze',
    # 配置
    'LLMConfig',
    'PRESETS',
    'get_config_from_env',
    'create_config_wizard',
    'save_api_key',
    # 枚举
    'LLMProvider',
    'AnalysisType',
    # 数据类
    'AnalysisResult',
    'CacheManager',
    'ImageProcessor',
    # 提示词
    'SYSTEM_PROMPTS',
    'USER_PROMPTS',
    'build_prompt',
    'build_stats_table',
    # 分析器
    'MapAnalyzer',
    'StatsInterpreter',
    'LISAMapAnalyzer',
    'AccessibilityInterpreter',
    'POIQualityAssessor',
    'ChartAssistant',
    'CodeReviewer',
]

# 版本信息
__version__ = '1.0.0'
__author__ = 'GIS Research Assistant'
__description__ = '多模态大模型 GIS 研究辅助工具包'
