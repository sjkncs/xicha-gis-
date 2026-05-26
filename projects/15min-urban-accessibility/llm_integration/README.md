# 多模态大模型 GIS 研究辅助工具包

## 功能概述

本工具包为 15 分钟城市研究提供大模型辅助分析功能，主要包括：

### 1. 地图可视化分析 (`MapAnalyzer`)
- 分析可达性热力图，识别高/低值区域
- 对比分析多张地图（时间/情景对比）
- 识别空间格局（中心-外围、多核心等）

### 2. 空间统计解读 (`StatsInterpreter`)
- Moran's I 全局空间自相关结果解读
- Gini 系数和洛伦兹曲线分析
- ANOVA/Kruskal-Wallis 检验结果解读
- 生成 SCI 级别的统计学描述

### 3. LISA 聚类分析 (`LISAMapAnalyzer`)
- 解读 HH/HL/LH/LL 四象限聚类结果
- 识别热点和冷点区域
- 定位空间异常（孤岛效应）

### 4. 可达性综合分析 (`AccessibilityInterpreter`)
- 解读可达性量化指标
- 分析脆弱群体差异
- 生成政策建议

### 5. POI 质量评估 (`POIQualityAssessor`)
- 自动评估 POI 覆盖度
- 识别数据缺失区域
- 提供数据增强建议

### 6. 图表生成辅助 (`ChartAssistant`)
- 生成 SCI 期刊级别的图注和描述
- 审阅图表可视化质量
- 提出改进建议

### 7. 代码审查 (`CodeReviewer`)
- 审查 GIS 空间分析代码
- 发现潜在 bug
- 提供优化建议

---

## 安装依赖

```bash
pip install openai dashscope Pillow matplotlib pandas geopandas
```

---

## 快速开始

### 方法 1：环境变量配置

```bash
# 设置 API Key
set SILICONFLOW_API_KEY=your-api-key-here

# 或设置其他服务商
set DASHSCOPE_API_KEY=your-api-key-here
set OPENAI_API_KEY=your-api-key-here
```

### 方法 2：配置文件

创建 `llm_integration/config.json`:

```json
{
  "provider": "siliconflow",
  "api_key": "your-api-key-here",
  "model": "Qwen/Qwen2.5-VL-7B-Instruct",
  "base_url": "https://api.siliconflow.cn/v1",
  "temperature": 0.3,
  "max_tokens": 2000
}
```

---

## 使用示例

### 示例 1：快速分析地图

```python
from llm_integration import LLMConfig, quick_analyze

# 加载配置
config = LLMConfig.load()
config.api_key = "your-api-key"

# 快速分析
result = quick_analyze(
    config=config,
    image_path="accessibility_map.png",
    prompt="分析这张可达性热力图，找出高值和低值区域",
    analysis_type="accessibility"
)

print(result.content)
```

### 示例 2：解读 Moran's I 统计结果

```python
from llm_integration import LLMConfig, create_llm_client, StatsInterpreter

config = LLMConfig.load()
client = create_llm_client(config)

interpreter = StatsInterpreter(client)

# 解读 Moran's I
result = interpreter.interpret_morans_i(
    stat_fig="morans_scatter.png",
    morans_i_value=0.35,
    p_value=0.001,
    variable_name="步行可达性",
    study_area="深圳市南山区"
)

print(result.content)
```

### 示例 3：分析 LISA 聚类图

```python
from llm_integration import LLMConfig, create_llm_client, LISAMapAnalyzer

config = LLMConfig.load()
client = create_llm_client(config)

lisa = LISAMapAnalyzer(client)

result = lisa.interpret_lisa_cluster_map(
    lisa_map_fig="lisa_cluster_map.png",
    quadrant_stats={"HH": 45, "LL": 38, "HL": 12, "LH": 8},
    study_area="深圳市"
)

print(result.content)
```

### 示例 4：集成到研究流程

```python
from llm_integration import example_usage

# 使用研究助手
assistant = example_usage.GISResearchAssistant()

# 分析可达性结果
result = assistant.analyze_accessibility_results(
    accessibility_map="accessibility_heatmap.png",
    metrics_summary={
        "步行可达性": accessibility_values,
        "公交可达性": transit_values
    },
    study_area="深圳市南山区"
)

# 导出报告
assistant.export_analysis_report("llm_analysis_report.md")
```

---

## 支持的模型服务商

| 服务商 | API Key 获取 | 多模态模型 |
|--------|-------------|-----------|
| **SiliconFlow** (推荐) | https://siliconflow.cn | Qwen2.5-VL-7B |
| 通义千问 | https://dashscope.console.aliyun.com | qwen-vl-plus |
| OpenAI | https://platform.openai.com | GPT-4o, GPT-4V |
| DeepSeek | https://platform.deepseek.com | DeepSeek-VL |
| 本地 Ollama | 自行部署 | LLaVA, CogVLM |

---

## API Key 获取

### SiliconFlow（推荐，免费额度）
1. 访问 https://siliconflow.cn
2. 注册并登录
3. 进入「API Key」页面
4. 创建新 Key 并复制

### 通义千问
1. 访问 https://dashscope.console.aliyun.com
2. 开通服务并获取 API Key
3. 注意：需要充值或使用免费额度

### OpenAI
1. 访问 https://platform.openai.com
2. 充值或使用免费额度
3. 注意：需要 VPN 访问

---

## 提示词模板

工具包内置了丰富的 GIS 专用提示词模板：

```python
from llm_integration import build_prompt

# 构建可达性分析提示词
prompt = build_prompt(
    "accessibility_analysis",
    metric_name="15分钟步行可达性",
    study_area="深圳市",
    mean=0.65,
    std=0.15,
    cv=0.23
)
```

---

## 注意事项

1. **图片大小**：图片会被自动压缩到 1024x1024 以节省 tokens
2. **缓存机制**：相同内容的分析结果会被缓存，默认 7 天
3. **并发限制**：请遵守各 API 服务商的 rate limit
4. **费用控制**：建议设置 `max_tokens` 限制单次响应长度

---

## 故障排除

### ImportError: No module named 'openai'
```bash
pip install openai dashscope
```

### API Error: Invalid API Key
- 检查 API Key 是否正确
- 检查是否设置了正确的环境变量
- 确认 API Key 有足够的调用额度

### 编码错误
- 确保 Python 文件使用 UTF-8 编码
- Windows 下可添加 `chcp 65001` 切换编码

---

## 扩展开发

如需添加新的分析器或集成新的模型服务商：

1. 在 `llm_client.py` 中添加新的客户端类
2. 在 `analyzers.py` 中添加新的分析器
3. 更新 `__init__.py` 的导出列表
4. 在 `prompts.py` 中添加专用提示词

---

## 许可

本工具包仅供研究使用。
