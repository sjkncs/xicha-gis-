# 深圳市南山区 15 分钟城市时间贫困研究
## 真实数据获取指南

---

## 一、人口数据获取

### 1.1 深圳市统计局分区人口数据（推荐）

**官方数据源**：
- 网站：http://tjj.sz.gov.cn/
- 年鉴下载：https://www.tjnj.net/navipage-n3026031404000101.html
- 电话：0755-88120163

**数据内容**：
| 数据表 | 内容 | 粒度 |
|--------|------|------|
| 1-2 分区国土调查面积、人口及人口密度 | 各区常住人口 | 区级 |
| 3-4 各区年末常住人口数 | 人口趋势 (2018-2024) | 区级 |

**问题**：
- 仅提供 **区级数据**（南山、福田、罗湖等）
- **无街道/社区级数据**
- 需联系统计局申请更细粒度数据

**申请流程**：
1. 访问深圳市统计局：http://tjj.sz.gov.cn/
2. 进入"数据发布"栏目
3. 下载最新统计年鉴（PDF/Excel）
4. 或联系统计局获取原始数据

---

### 1.2 夜间灯光遥感数据估算人口（推荐）

**数据源**：
- **NASA EOSDIS**（免费）：https://eogdata.mines.edu/products/vnl/
- **国家对地观测科学数据中心**（中国）：https://cms.casdc.cn/

**使用方法**：

**Step 1**: 下载 NPP-VIIRS 夜间灯光年度合成数据
```
1. 访问: https://eogdata.mines.edu/products/vnl/
2. 选择: Annual VNL v2.1
3. 选择年份: 2023
4. 下载 GeoTIFF 格式
5. 保存到: data/population/VNL_v2_2023.tif
```

**Step 2**: 运行人口估算脚本
```bash
python scripts/data_collection/p4_population_from_lights.py
```

**技术方法**：
- **比值法**：总人口 × (社区灯光强度 / 区域总灯光强度)
- **回归法**：使用部分已知人口数据进行线性回归校准
- 相关性：灯光强度与人口相关系数可达 ρ=0.971

**优点**：
- 免费
- 时间序列长（2012-2023）
- 空间分辨率 ~500m

**缺点**：
- 精度有限
- 需部分真实数据校准

---

### 1.3 居住小区精细化人口估算

**方法**：基于建筑面积和小区类型估算

```python
# scripts/data_collection/p4b_population_from_census.py
from p4b_population_from_census import estimate_community_population_v2

# 输入：小区数据（含 area_m2, community_type）
communities = estimate_community_population_v2(communities_df, district_pop=1600000)
```

**调整系数**：
| 小区类型 | 调整系数 | 说明 |
|---------|---------|------|
| 城中村 | 1.5 | 人口密度高 |
| 保障房 | 1.2 | 密度较高 |
| 商品房 | 1.0 | 基准 |
| 高端社区 | 0.8 | 密度较低 |

---

## 二、设施营业时间数据

### 2.1 高德地图 Web API（推荐，免费）

**申请地址**：https://lbs.amap.com/

**免费额度**：
- 每日 5000 次请求
- 无需企业资质

**使用方法**：
```python
# scripts/data_collection/p5_meituan_dianping_api.py
from p5_meituan_dianping_api import GaodeWebAPI, collect_night_service_poi

gaode = GaodeWebAPI(api_key='your_api_key')
categories = ['药店', '超市', '便利店', '医院', '餐厅']
collect_night_service_poi(gaode, categories, 'output.csv')
```

**环境变量设置**：
```powershell
set GAODE_API_KEY=your_api_key
```

---

### 2.2 美团开放平台（需企业资质）

**申请地址**：https://open.meituan.com/

**注意**：
- **必须企业资质**才能申请核心 API
- 个人开发者无法获取营业时间等数据

**申请流程**：
1. 注册美团开放平台账号
2. 使用营业执照完成企业认证
3. 创建应用并申请权限：
   - `poi.query` - POI 搜索
   - `poi.detail` - POI 详情（含营业时间）
4. 获取 `app_id` 和 `app_secret`

**环境变量设置**：
```powershell
set MEITUAN_APP_ID=your_app_id
set MEITUAN_APP_SECRET=your_app_secret
```

---

### 2.3 实地调查（补充方法）

对于关键设施，建议实地调查：

**采样策略**：
| 设施类型 | 采样数量 | 调查内容 |
|---------|---------|---------|
| 医院/诊所 | 20 | 24h服务、夜间值班 |
| 药店 | 50 | 24h服务、营业时间 |
| 便利店 | 30 | 24h服务 |
| 餐厅 | 50 | 营业时间 |
| 超市 | 10 | 营业时间 |

**调查表格模板**：
```csv
设施名称,地址,设施类型,营业时间,是否24h,夜间服务,调查日期,备注
xxx药店,xxx路xx号,药店,08:00-22:00,否,是,2024-xx-xx,
xxx便利店,xxx路xx号,便利店,24h,是,是,2024-xx-xx,
```

---

## 三、建筑物 AOI 数据

### 3.1 OSM 建筑数据（当前使用）

**来源**：OpenStreetMap Overpass API
**覆盖率**：南山区 16,588 个建筑，75.1% 为居住类

**优点**：
- 免费
- 数据现势性较好
- 有建筑高度（height）和层数（levels）属性

**缺点**：
- 不完整（部分建筑缺失）
- 无真实居住小区边界

---

### 3.2 深圳市规划和自然资源局数据（推荐）

**申请方式**：

**在线申请**：
- 网址：http://ysqgk.gd.gov.cn/755016
- 广东省政府信息依申请公开系统

**书面申请**：
- 地址：深圳市福田区红荔路8009号规划大厦1楼
- 电话：0755-83514909
- 邮箱：gtwzwgk@pnr.sz.gov.cn

**申请内容**：
```
所需信息描述：建筑物AOI矢量数据（GeoJSON/SHP格式）
用途：学术研究
形式要求：电子数据
```

**处理时限**：7个工作日内告知

---

### 3.3 全国基础地理信息数据（补充）

**来源**：自然资源部

**数据内容**：
- 1:100万 公众版基础地理数据
- 包含"居民地及设施"数据集

**下载地址**：
- 全国地理信息资源目录服务系统
- http://www.webmap.cn/commres.do?method=result25W

**内容**：
- 街区、高层建筑区
- 居民地面层和点层要素

---

## 四、数据获取优先级建议

| 优先级 | 数据项 | 方法 | 难度 | 建议 |
|--------|-------|------|------|------|
| ⭐⭐⭐ | 分区人口 | 统计年鉴 | 低 | 立即获取 |
| ⭐⭐⭐ | 灯光人口估算 | NPP-VIIRS | 中 | 1周内完成 |
| ⭐⭐ | 营业时间 | 高德API | 中 | 申请API后执行 |
| ⭐⭐ | 建筑AOI | 规划局申请 | 高 | 1-2月 |
| ⭐ | 街道人口 | 联系统计局 | 高 | 视情况申请 |

---

## 五、数据更新计划

### 短期（1周内）
1. ✅ 下载深圳统计年鉴获取区级人口
2. ✅ 下载 NPP-VIIRS 灯光数据
3. ✅ 申请高德 API Key

### 中期（1个月内）
4. 完成灯光人口估算
5. 高德 API 批量采集营业时间
6. 补充实地调查

### 长期（1-2月）
7. 向规划局申请建筑AOI数据
8. 联系统计局获取街道级人口

---

## 六、联系信息

| 部门 | 电话 | 网站 | 备注 |
|------|------|------|------|
| 深圳市统计局 | 0755-88120163 | tjj.sz.gov.cn | 分区数据 |
| 规划自然资源局 | 0755-83514909 | pnr.sz.gov.cn | 建筑数据 |
| 高德地图 | - | lbs.amap.com | API申请 |
| 美团开放平台 | - | open.meituan.com | 需企业资质 |
