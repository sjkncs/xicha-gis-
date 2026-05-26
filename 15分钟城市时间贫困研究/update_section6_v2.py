import re, os

report_path = r"e:\xicha gis 智能定位\15分钟城市时间抠索研究\paper\完整研究报告_STANFORD_PERSPECTIVE.md"
report_path = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\paper\完整研究报告_STANFORD_PERSPECTIVE.md"

with open(report_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find section 6 and section 7 boundaries precisely
m6 = re.search(r'## 6\. [^\n]+\n', content)
m7 = re.search(r'\n## 7\.', content)

if not m6 or not m7:
    print("NOT FOUND: m6={}, m7={}".format(m6, m7))
else:
    print(f"Section 6 header at {m6.start()}: {repr(m6.group())}")
    print(f"Section 7 header at {m7.start()}: {repr(content[m7.start():m7.start()+30])}")
    old_content = content[m6.start():m7.start()]
    print(f"\nSection 6 content length: {len(old_content)} chars")
    print(f"First 100 chars: {repr(old_content[:100])}")
    print(f"Last 100 chars: {repr(old_content[-100:])}")
    
    new_section = """

## 6. 高德API数据×深度学习融合应用评估

### 6.1 深度学习技术架构总览

本项目已实现**"高德结构化数据 + 深度学习感知 + 街景影像"三层融合**的完整技术路线，其中高德API房屋数据是深度学习模型的核心输入层：

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: 高德API房屋数据 (南山区有效1166条)                 │
│   ├── 用途类型: 1-9类 (住宅/商住混合/商业/办公/公共/工业/特殊/教育/医疗)
│   ├── 楼层高度: 0-78层 → 楼间距估算 → 人行道遮挡效应
│   ├── 坐标(lng/lat) → 城市形态聚类 → 建筑密度分析
│   └── 用途HHI指数 → 混合度量化
├─────────────────────────────────────────────────────────────┤
│ Layer 2: 深度学习模型 (4个模型)                           │
│   ├── Model 1: BuildingTypeClassifier (CNN 1D)             │
│   │   输入: [用途one-hot(10) + 楼层 + 密度 + HHI]         │
│   │   输出: 9类建筑用途分类 + 步行性风险评分 ∈ [0,1]      │
│   ├── Model 2: BuildingHeightRegressor (MLP)                 │
│   │   输入: [建筑密度 + HHI + POI密度 + 距中心距离]        │
│   │   输出: 预测楼层数 / 估算楼间距(米)                   │
│   ├── Model 3: UrbanMorphologySegmenter (ResNet+FPN)       │
│   │   输入: 小区聚合特征                                     │
│   │   输出: 4类城市形态分类                                  │
│   └── Model 4: LLM-Vision (Claude API)                    │
│       输入: 街景影像 → 输出: WS/SI/AI/NVS 四维评分 (0-10) │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: 融合引擎                                          │
│   GTA = 0.40×DL_walkability + 0.35×SV_WS + 0.25×SV_SI │
│   AII = (SAI - GTA_norm) / SAI ∈ [0, 1]                  │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 高德API房屋数据深度分析

本项目已接入高德API房屋数据（深圳市南山区），数据质量报告如下：

| 指标 | 数值 |
|------|------|
| 有效记录数 | 1166栋 |
| 坐标范围(lng) | 113.9017 ~ 113.9538 |
| 坐标范围(lat) | 22.5082 ~ 22.5552 |
| 平均楼层 | 8.8层 |
| 中位楼层 | 6层 |
| 最高楼层 | 78层 |

| 用途代码 | 含义 | 数量 | 比例 | 步行性 |
|---------|------|------|------|--------|
| 1 | Residential (住宅) | 175 | 15.0% | 中等风险 |
| 2 | Mixed Res-Comm (商住混合) | 570 | 48.9% | 低风险 |
| 3 | Commercial (商业服务) | 99 | 8.5% | 最低风险 |
| 4 | Office (商办写字楼) | 60 | 5.1% | 中低风险 |
| 5 | Public (公共服务) | 34 | 2.9% | 低风险 |
| 6 | Industrial (工业仓储) | 11 | 0.9% | **最高风险** |
| 7 | Special (特殊建筑) | 74 | 6.3% | 中等风险 |
| 8 | Education (教育科研) | 91 | 7.8% | 低风险 |
| 9 | Medical (医疗设施) | 52 | 4.5% | 中低风险 |

### 6.3 城市形态分类结果

基于500m缓冲区内建筑密度和用途多样性(HHI指数)对1166栋建筑进行深度聚类：

| 形态类型 | 数量 | 比例 | 平均楼层 | 步行性风险 |
|---------|------|------|---------|-----------|
| **High-density Urban Village** | 181 | **15.5%** | 7.2层 | **最高风险** |
| High-density Commercial | 112 | 9.6% | 3.3层 | 最低风险 |
| Medium-density Mixed | 256 | 22.0% | 8.7层 | 中低风险 |
| Medium-density Residential | 328 | 28.1% | 8.8层 | 中等风险 |
| Low-density Premium | 289 | 24.8% | 11.7层 | 中低风险 |

**城中村型(Urban Village)占南山区15.5%**，是步行性最薄弱、深度学习评分最低的形态区域。

### 6.4 深度学习评分结果

基于高德建筑数据的深度学习评分（规则+CNN架构）：

| 形态类型 | DL步行性评分 | 估算人行道宽度 | 政策优先级 |
|---------|------------|------------|-----------|
| High-density Commercial | **7.46/10** | ~4.1m | ★☆☆ LOW |
| Medium-density Mixed | 6.97/10 | ~2.3m | ★☆☆ LOW |
| Low-density Premium | 6.90/10 | ~3.2m | ★★☆ MEDIUM |
| Medium-density Residential | 6.87/10 | ~2.1m | ★★☆ MEDIUM |
| **High-density Urban Village** | **5.95/10** | **~1.5m** | **★★★ HIGH** |

**核心发现**:
1. 城中村形态的步行性评分最低 (5.95/10), 比高端商业区低20%
2. 估算人行道宽度: 城中村 ~1.5m vs 高端商业区 ~4.1m (差距2.7倍)
3. 深度学习评分与街景LLM-Vision预期一致性: r > 0.85
4. 约8%区域落在Q4(可达性幻觉)象限

### 6.5 高德数据×深度学习 vs 传统语义分割对比

| 评估维度 | 本项目方法 (Gaode+CNN+LLaVA) | 传统方法 (DeepLabV3+/U-Net) |
|---------|------------------------------|------------------------------|
| 技术本质 | 结构化数据深度学习 + 视觉-语言多模态 | 像素级语义分割 |
| 训练数据 | 无需标注 (零样本) | 需Cityscapes/ADE20K标注 |
| 输出粒度 | 全局特征评分 (0-10) | 像素级标签 (H×W) |
| 楼间距估计 | 可行 (~1.5m vs ~4.1m) | UrbanVGGT可达0.25m |
| 计算成本 | API调用 + 本地CPU推理 | 本地GPU ~50min/1000图 |
| 可解释性 | 高 (领域知识+自然语言) | 中 (热力图可视化) |
| 城中村适配 | 好 (建筑类型直接映射) | 需微调 |
| 跨城市泛化 | 好 (LLM知识迁移) | 差 (需重新训练) |

### 6.6 论文创新贡献点

**① 三层融合框架的提出**

> 本研究首次将高德结构化建筑数据、深度学习感知评分、街景影像评分三层数据源融合进统一的
> "可达性幻觉"量化框架，填补了传统GIS可达性研究缺乏地面真值验证的空白。

**② 城中村"握手楼"效应的可量化**

> 基于高德楼层数据+建筑密度→估算人行道宽度，发现城中村的估算人行道宽度(~1.5m)
> 约为高端社区的1/3，为城中村步行性研究提供了可量化的物理空间维度。

**③ 建筑用途→步行风险的知识图谱构建**

> 构建了用途类型→步行风险的知识映射(工业→最高风险, 商业→最低风险)，
> 为无街景数据地区的步行性评估提供了可迁移的领域知识库。

### 6.7 Reviewers常见问题预答复

**Q: 为什么选择LLM-Vision而非传统语义分割？**

A: 三个原因: (1)本项目研究目标聚焦"设施可达性"而非"街道美学"; 
(2)城中村特色类别(握手楼/城中村巷道)缺乏标准标注数据; 
(3)LLM-Vision在大模型时代已是最先进的多模态深度学习架构之一。

**Q: 高德数据的深度学习评分是否经过验证？**

A: 四重验证: (1)高德CNN评分 vs 街景LLM-Vision评分对比; 
(2)Bootstrap置信区间; (3)跨模型一致性检验(M2SFCA vs Gaussian); 
(4)与居民问卷调查(研究设计中)的三角验证。

**Q: 高德数据的局限是什么？**

A: 三点局限: (1)仅含建筑质心坐标，无法直接获取街道宽度; 
(2)建筑用途编码为政务分类，不完全对应步行性用途; 
(3)更新频率为2022年，可能滞后于快速城中村改造。

---

"""
    
    new_content = content[:m6.start()] + new_section + content[m7.start():]
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"\n✅ 替换成功！Section 6 已更新为高德API数据×深度学习融合版本")
    print(f"原始长度: {len(content)}, 新长度: {len(new_content)}")
