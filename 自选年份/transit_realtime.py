"""
transit_realtime.py — 深圳地铁/公交实时数据集成模块

功能：
    - 深圳地铁到站预测（模拟真实线路间隔和运行状态）
    - 公交到站预测（模拟GPS位置和到站时间）
    - 异步并发API调用
    - TTL缓存（30-60秒）防止频繁请求
    - 混合真实/模拟数据接口（未来可对接深圳通API）

依赖：
    pip install fastapi pydantic cachetools

导出：
    get_nearest_subway_station(lat, lon)        # 最近地铁站 + 实时信息
    get_nearest_bus_stops(lat, lon, limit=5)   # 最近公交站 + 到站预测
    get_subway_line_status(line_id)             # 线路运行状态
    get_combined_transit_analysis(lat, lon, time_threshold=15)  # 综合出行分析
    ShenzhenMetroAPI                           # 地铁实时API类
    ShenzhenBusAPI                             # 公交实时API类
"""

import asyncio
import hashlib
import logging
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

try:
    from cachetools import TTLCache
    _HAS_CACHETOOLS = True
except ImportError:
    _HAS_CACHETOOLS = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# =============================================================================
# 深圳地铁线路配置（模拟数据）
# =============================================================================
# 深圳地铁运营数据参考：工作日高峰2-4分钟间隔，平峰5-8分钟间隔
# 11号线（机场线）较长，间隔约5-8分钟

SHENZHEN_METRO_LINES = {
    "1": {
        "name": "1号线",
        "name_en": "Line 1",
        "color": "#FF0000",
        "stations": [
            {"name": "罗湖", "lon": 114.1124, "lat": 22.5433},
            {"name": "国贸", "lon": 114.1194, "lat": 22.5453},
            {"name": "老街", "lon": 114.1295, "lat": 22.5463},
            {"name": "大剧院", "lon": 114.1375, "lat": 22.5458},
            {"name": "科学馆", "lon": 114.1445, "lat": 22.5468},
            {"name": "华强路", "lon": 114.1500, "lat": 22.5478},
            {"name": "香蜜湖", "lon": 114.1570, "lat": 22.5493},
            {"name": "车公庙", "lon": 114.1630, "lat": 22.5483},
            {"name": "竹子林", "lon": 114.1710, "lat": 22.5458},
            {"name": "侨城东", "lon": 114.1790, "lat": 22.5423},
            {"name": "华侨城", "lon": 114.1870, "lat": 22.5398},
            {"name": "世界之窗", "lon": 114.1950, "lat": 22.5373},
            {"name": "白石洲", "lon": 114.2030, "lat": 22.5343},
            {"name": "高新园", "lon": 114.2110, "lat": 22.5313},
            {"name": "深大", "lon": 114.2190, "lat": 22.5283},
            {"name": "桃园", "lon": 114.2270, "lat": 22.5253},
            {"name": "大新", "lon": 114.2350, "lat": 22.5223},
            {"name": "鲤鱼门", "lon": 114.2430, "lat": 22.5193},
            {"name": "前海湾", "lon": 114.2510, "lat": 22.5163},
            {"name": "新安", "lon": 114.2590, "lat": 22.5133},
            {"name": "宝安中心", "lon": 114.2670, "lat": 22.5103},
            {"name": "宝体", "lon": 114.2750, "lat": 22.5073},
            {"name": "坪洲", "lon": 114.2830, "lat": 22.5043},
            {"name": "西乡", "lon": 114.2910, "lat": 22.5013},
            {"name": "固戍", "lon": 114.2990, "lat": 22.4983},
            {"name": "后瑞", "lon": 114.3070, "lat": 22.4953},
            {"name": "机场东", "lon": 114.3150, "lat": 22.4923},
        ],
        "interval_peak": 180,      # 高峰间隔（秒）
        "interval_offpeak": 360,   # 平峰间隔（秒）
        "status": "正常",          # 正常/延误/暂停服务
    },
    "2": {
        "name": "2号线",
        "name_en": "Line 2",
        "color": "#00FF00",
        "stations": [
            {"name": "赤湾", "lon": 113.8950, "lat": 22.4833},
            {"name": "蛇口港", "lon": 113.9030, "lat": 22.4863},
            {"name": "海上世界", "lon": 113.9110, "lat": 22.4893},
            {"name": "水湾", "lon": 113.9190, "lat": 22.4923},
            {"name": "东角头", "lon": 113.9270, "lat": 22.4953},
            {"name": "湾厦", "lon": 113.9350, "lat": 22.4983},
            {"name": "海月", "lon": 113.9430, "lat": 22.5013},
            {"name": "登良", "lon": 113.9510, "lat": 22.5043},
            {"name": "后海", "lon": 113.9590, "lat": 22.5073},
            {"name": "科苑", "lon": 113.9670, "lat": 22.5043},
            {"name": "红树湾", "lon": 113.9750, "lat": 22.5013},
            {"name": "华侨城北", "lon": 113.9830, "lat": 22.4983},
            {"name": "侨城北", "lon": 113.9910, "lat": 22.4953},
            {"name": "深康", "lon": 113.9990, "lat": 22.4923},
            {"name": "安托山", "lon": 114.0070, "lat": 22.4893},
            {"name": "农林", "lon": 114.0150, "lat": 22.4863},
            {"name": "车公庙", "lon": 114.0230, "lat": 22.4833},
            {"name": "香梅北", "lon": 114.0310, "lat": 22.4803},
            {"name": "景田", "lon": 114.0390, "lat": 22.4773},
            {"name": "莲花西", "lon": 114.0470, "lat": 22.4743},
            {"name": "市民中心", "lon": 114.0550, "lat": 22.4773},
            {"name": "岗厦北", "lon": 114.0630, "lat": 22.4803},
            {"name": "华强北", "lon": 114.0710, "lat": 22.4833},
            {"name": "燕南", "lon": 114.0790, "lat": 22.4863},
            {"name": "大剧院", "lon": 114.0870, "lat": 22.4893},
            {"name": "湖贝", "lon": 114.0950, "lat": 22.4923},
            {"name": "黄贝岭", "lon": 114.1030, "lat": 22.4953},
            {"name": "新秀", "lon": 114.1110, "lat": 22.4983},
        ],
        "interval_peak": 210,
        "interval_offpeak": 420,
        "status": "正常",
    },
    "5": {
        "name": "5号线",
        "name_en": "Line 5",
        "color": "#6B8E23",
        "stations": [
            {"name": "赤湾", "lon": 113.8850, "lat": 22.4733},
            {"name": "荔湾", "lon": 113.8930, "lat": 22.4763},
            {"name": "铁路公园", "lon": 113.9010, "lat": 22.4793},
            {"name": "妈湾", "lon": 113.9090, "lat": 22.4823},
            {"name": "前湾公园", "lon": 113.9170, "lat": 22.4853},
            {"name": "前湾", "lon": 113.9250, "lat": 22.4883},
            {"name": "桂湾", "lon": 113.9330, "lat": 22.4913},
            {"name": "前海", "lon": 113.9410, "lat": 22.4943},
            {"name": "临海", "lon": 113.9490, "lat": 22.4973},
            {"name": "宝华", "lon": 113.9570, "lat": 22.5003},
            {"name": "宝安中心", "lon": 113.9650, "lat": 22.5033},
            {"name": "翻身", "lon": 113.9730, "lat": 22.5063},
            {"name": "灵芝", "lon": 113.9810, "lat": 22.5093},
            {"name": "洪浪北", "lon": 113.9890, "lat": 22.5123},
            {"name": "兴东", "lon": 113.9970, "lat": 22.5153},
            {"name": "留仙洞", "lon": 114.0050, "lat": 22.5183},
            {"name": "西丽", "lon": 114.0130, "lat": 22.5213},
            {"name": "大学城", "lon": 114.0210, "lat": 22.5243},
            {"name": "塘朗", "lon": 114.0290, "lat": 22.5273},
            {"name": "长岭坡", "lon": 114.0370, "lat": 22.5303},
            {"name": "深圳北站", "lon": 114.0450, "lat": 22.5333},
            {"name": "民治", "lon": 114.0530, "lat": 22.5363},
            {"name": "五和", "lon": 114.0610, "lat": 22.5393},
            {"name": "坂田", "lon": 114.0690, "lat": 22.5423},
            {"name": "杨美", "lon": 114.0770, "lat": 22.5453},
            {"name": "上水径", "lon": 114.0850, "lat": 22.5483},
            {"name": "下水径", "lon": 114.0930, "lat": 22.5513},
            {"name": "长龙", "lon": 114.1010, "lat": 22.5543},
            {"name": "布吉", "lon": 114.1090, "lat": 22.5573},
            {"name": "百鸽笼", "lon": 114.1170, "lat": 22.5603},
            {"name": "布心", "lon": 114.1250, "lat": 22.5633},
            {"name": "太安", "lon": 114.1330, "lat": 22.5663},
            {"name": "怡景", "lon": 114.1410, "lat": 22.5693},
            {"name": "黄贝岭", "lon": 114.1490, "lat": 22.5723},
        ],
        "interval_peak": 240,
        "interval_offpeak": 480,
        "status": "正常",
    },
    "11": {
        "name": "11号线",
        "name_en": "Line 11 (Airport)",
        "color": "#800080",
        "stations": [
            {"name": "福田", "lon": 114.0550, "lat": 22.5433},
            {"name": "车公庙", "lon": 114.0630, "lat": 22.5483},
            {"name": "红树湾南", "lon": 114.0710, "lat": 22.5013},
            {"name": "后海", "lon": 114.0790, "lat": 22.5073},
            {"name": "南山", "lon": 114.0870, "lat": 22.5133},
            {"name": "前海湾", "lon": 114.0950, "lat": 22.5163},
            {"name": "宝安", "lon": 114.1030, "lat": 22.5093},
            {"name": "碧海湾", "lon": 114.1110, "lat": 22.5023},
            {"name": "机场", "lon": 114.1190, "lat": 22.4953},
            {"name": "机场北", "lon": 114.1270, "lat": 22.4883},
            {"name": "福永", "lon": 114.1350, "lat": 22.4813},
            {"name": "桥头", "lon": 114.1430, "lat": 22.4743},
            {"name": "塘尾", "lon": 114.1510, "lat": 22.4673},
            {"name": "马安山", "lon": 114.1590, "lat": 22.4603},
            {"name": "沙后", "lon": 114.1670, "lat": 22.4533},
            {"name": "松岗", "lon": 114.1750, "lat": 22.4463},
        ],
        "interval_peak": 300,
        "interval_offpeak": 480,
        "status": "正常",
    },
}

# 南山区主要地铁站索引（用于快速查找）
NANSHAN_METRO_STATIONS = []
for line_id, line_info in SHENZHEN_METRO_LINES.items():
    for idx, station in enumerate(line_info["stations"]):
        NANSHAN_METRO_STATIONS.append({
            "name": station["name"],
            "line_id": line_id,
            "line_name": line_info["name"],
            "color": line_info["color"],
            "lon": station["lon"],
            "lat": station["lat"],
            "station_index": idx,
        })


# =============================================================================
# 深圳公交站点配置（模拟数据 - 南山区重点线路）
# =============================================================================
# 模拟南山区主要公交线路和站点

NANSHAN_BUS_ROUTES = [
    {
        "route_id": "B001",
        "route_name": "42路",
        "direction": "赤湾-福田",
        "stops": [
            {"name": "赤湾站", "lon": 113.8850, "lat": 22.4733},
            {"name": "南山花园", "lon": 113.8930, "lat": 22.4793},
            {"name": "蛇口沃尔玛", "lon": 113.9010, "lat": 22.4853},
            {"name": "海上世界南", "lon": 113.9090, "lat": 22.4913},
            {"name": "南海玫瑰园", "lon": 113.9170, "lat": 22.4973},
            {"name": "半岛花园", "lon": 113.9250, "lat": 22.5033},
            {"name": "海月花园", "lon": 113.9330, "lat": 22.5093},
            {"name": "登良站", "lon": 113.9410, "lat": 22.5153},
            {"name": "后海立交", "lon": 113.9490, "lat": 22.5213},
            {"name": "南山书城", "lon": 113.9570, "lat": 22.5273},
            {"name": "海雅百货", "lon": 113.9650, "lat": 22.5333},
            {"name": "南山地铁站", "lon": 113.9730, "lat": 22.5393},
            {"name": "桂庙新村", "lon": 113.9810, "lat": 22.5453},
            {"name": "深大北门", "lon": 113.9890, "lat": 22.5513},
            {"name": "科技园", "lon": 113.9970, "lat": 22.5573},
            {"name": "大冲", "lon": 114.0050, "lat": 22.5633},
            {"name": "白石洲", "lon": 114.0130, "lat": 22.5693},
            {"name": "世界之窗", "lon": 114.0210, "lat": 22.5753},
            {"name": "何香凝美术馆", "lon": 114.0290, "lat": 22.5813},
            {"name": "锦绣中华", "lon": 114.0370, "lat": 22.5873},
        ],
        "interval_peak": 300,
        "interval_offpeak": 480,
    },
    {
        "route_id": "B002",
        "route_name": "M475路",
        "direction": "科技园-深圳北站",
        "stops": [
            {"name": "科技园停车场", "lon": 113.9870, "lat": 22.5573},
            {"name": "深港产学研基地", "lon": 113.9950, "lat": 22.5513},
            {"name": "百度国际大厦", "lon": 114.0030, "lat": 22.5453},
            {"name": "腾讯大厦", "lon": 114.0110, "lat": 22.5393},
            {"name": "软件产业基地", "lon": 114.0190, "lat": 22.5333},
            {"name": "深圳湾体育中心", "lon": 114.0270, "lat": 22.5273},
            {"name": "华润深圳湾", "lon": 114.0350, "lat": 22.5213},
            {"name": "海岸城", "lon": 114.0430, "lat": 22.5273},
            {"name": "南山茂业", "lon": 114.0510, "lat": 22.5333},
            {"name": "南头古城", "lon": 114.0590, "lat": 22.5393},
            {"name": "新安古城", "lon": 114.0670, "lat": 22.5453},
        ],
        "interval_peak": 360,
        "interval_offpeak": 600,
    },
    {
        "route_id": "B003",
        "route_name": "N27路",
        "direction": "南山区环线",
        "stops": [
            {"name": "南山区政府", "lon": 114.0550, "lat": 22.5253},
            {"name": "南山图书馆", "lon": 114.0470, "lat": 22.5213},
            {"name": "荔香公园", "lon": 114.0390, "lat": 22.5173},
            {"name": "南山医院", "lon": 114.0310, "lat": 22.5133},
            {"name": "南航明珠", "lon": 114.0230, "lat": 22.5093},
            {"name": "阳光华艺", "lon": 114.0150, "lat": 22.5133},
            {"name": "南贸中心", "lon": 114.0070, "lat": 22.5173},
            {"name": "海王大厦", "lon": 113.9990, "lat": 22.5213},
            {"name": "亿利达", "lon": 113.9910, "lat": 22.5253},
            {"name": "明华国际", "lon": 113.9830, "lat": 22.5293},
            {"name": "海王大厦", "lon": 113.9750, "lat": 22.5333},
            {"name": "南海大道", "lon": 113.9670, "lat": 22.5373},
            {"name": "创业路", "lon": 113.9590, "lat": 22.5333},
            {"name": "文心五路", "lon": 113.9510, "lat": 22.5293},
            {"name": "保利剧院", "lon": 113.9430, "lat": 22.5253},
        ],
        "interval_peak": 420,
        "interval_offpeak": 600,
    },
]

# 生成所有公交站点
ALL_BUS_STOPS = []
for route in NANSHAN_BUS_ROUTES:
    for idx, stop in enumerate(route["stops"]):
        ALL_BUS_STOPS.append({
            "name": stop["name"],
            "route_id": route["route_id"],
            "route_name": route["route_name"],
            "lon": stop["lon"],
            "lat": stop["lat"],
            "stop_index": idx,
        })


# =============================================================================
# Pydantic 数据模型
# =============================================================================

class MetroArrival(BaseModel):
    """地铁列车到站信息"""
    station_name: str
    line_id: str
    line_name: str
    direction: str
    platform: str = Field(default="1", description="站台号")
    arrival_time: str = Field(description="预计到站时间 HH:MM:SS")
    wait_seconds: int = Field(description="等待秒数")
    status: str = Field(default="正常", description="正常/延误")


class SubwayStation(BaseModel):
    """地铁站点实时信息"""
    name: str
    line_id: str
    line_name: str
    color: str
    lon: float
    lat: float
    distance_m: float
    arrivals: List[MetroArrival] = Field(default_factory=list)
    station_status: str = Field(default="正常", description="站点状态")


class SubwayLineStatus(BaseModel):
    """地铁线路状态"""
    line_id: str
    line_name: str
    color: str
    status: str
    status_message: str
    delay_minutes: int = 0
    affected_stations: List[str] = Field(default_factory=list)


class BusArrival(BaseModel):
    """公交到站信息"""
    route_id: str
    route_name: str
    direction: str
    stop_name: str
    arrival_time: str
    wait_minutes: int
    distance_km: float = Field(description="距离站点的公里数")


class BusStop(BaseModel):
    """公交站点实时信息"""
    name: str
    route_id: str
    route_name: str
    lon: float
    lat: float
    distance_m: float
    arrivals: List[BusArrival] = Field(default_factory=list)
    stop_status: str = Field(default="正常", description="站点状态")


class NearbyBusStops(BaseModel):
    """附近公交站点列表"""
    origin_lon: float
    origin_lat: float
    count: int
    stops: List[BusStop]


class NearbySubwayStation(BaseModel):
    """最近地铁站及实时信息"""
    origin_lon: float
    origin_lat: float
    station: SubwayStation
    walking_time_min: float = Field(description="步行时间（分钟）")


class SubwayLineStatusResponse(BaseModel):
    """地铁线路状态响应"""
    line_id: str
    line: SubwayLineStatus
    stations: List[SubwayStation]


class CombinedTransitAnalysis(BaseModel):
    """综合出行分析结果"""
    origin_lon: float
    origin_lat: float
    time_threshold_min: int
    nearest_subway: Optional[SubwayStation] = None
    nearest_bus_stops: List[BusStop] = Field(default_factory=list)
    subway_arrivals: List[MetroArrival] = Field(default_factory=list)
    bus_arrivals: List[BusArrival] = Field(default_factory=list)
    recommendations: List[str] = Field(
        default_factory=list,
        description="出行建议"
    )
    optimal_transport: Optional[Dict[str, Any]] = Field(
        default=None,
        description="最优交通方式建议"
    )


# =============================================================================
# 工具函数
# =============================================================================

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """计算两点间距离（米）"""
    R = 6371000
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def is_peak_hour() -> bool:
    """判断是否高峰时段"""
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    # 工作日早高峰 7:00-9:00, 晚高峰 17:30-19:30
    if weekday < 5:
        if 7 <= hour <= 9 or 17 <= hour <= 19:
            return True
    return False


def get_current_time_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def simulate_delay() -> Tuple[str, int]:
    """模拟随机延误"""
    now = datetime.now()
    hour = now.hour
    if 9 <= hour <= 10 or 18 <= hour <= 19:
        # 偶发延误
        if random.random() < 0.15:
            delay_mins = random.choice([2, 3, 5, 8])
            return f"延误{delay_mins}分钟", delay_mins
    return "正常", 0


# =============================================================================
# 缓存实现（简单TTL缓存，兼容无cachetools环境）
# =============================================================================

class SimpleTTLCache:
    """简单的TTL缓存实现"""
    def __init__(self, maxsize: int, ttl: int):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: Dict[str, Tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        if len(self._cache) >= self.maxsize:
            # 删除最老的
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        self._cache[key] = (value, time.time())

    def clear(self) -> None:
        self._cache.clear()


# 全局缓存实例
_cache: Optional[SimpleTTLCache] = None

def get_cache(maxsize: int = 1000, ttl: int = 60) -> SimpleTTLCache:
    global _cache
    if _cache is None:
        _cache = SimpleTTLCache(maxsize, ttl)
    return _cache


# =============================================================================
# 深圳地铁API
# =============================================================================

class ShenzhenMetroAPI:
    """
    深圳地铁实时数据API
    目前使用模拟数据，未来可对接深圳地铁集团API或深圳通API
    """
    def __init__(self, cache_ttl: int = 60):
        self.cache_ttl = cache_ttl
        self._cache = get_cache(maxsize=500, ttl=cache_ttl)

    def _generate_cache_key(self, *args) -> str:
        args_str = "_".join(str(a) for a in args)
        return hashlib.md5(args_str.encode()).hexdigest()

    def get_stations(self, line_id: str) -> List[Dict]:
        """获取线路所有站点"""
        line = SHENZHEN_METRO_LINES.get(line_id)
        if not line:
            return []
        return line["stations"]

    def find_nearest_station(self, lat: float, lon: float) -> Optional[Dict]:
        """查找最近的地铁站"""
        min_dist = float("inf")
        nearest = None
        for station in NANSHAN_METRO_STATIONS:
            dist = haversine_m(lat, lon, station["lat"], station["lon"])
            if dist < min_dist:
                min_dist = dist
                nearest = station
        if nearest:
            nearest["distance_m"] = round(min_dist, 0)
        return nearest

    def get_station_arrivals(
        self, station_name: str, line_id: str, limit: int = 3
    ) -> List[MetroArrival]:
        """获取站点列车到站信息"""
        arrivals = []
        line = SHENZHEN_METRO_LINES.get(line_id, {})
        interval = (line.get("interval_peak", 300) if is_peak_hour()
                   else line.get("interval_offpeak", 480))

        status, delay = simulate_delay()
        now = datetime.now()

        # 模拟两个方向的到站
        for direction_idx in range(2):
            direction = "往罗湖/赤湾方向" if direction_idx == 0 else "往机场/世界之窗方向"
            platform = str(direction_idx + 1)

            for i in range(limit):
                wait_s = interval * (i + 1) + random.randint(-30, 60)
                wait_s = max(30, wait_s)  # 至少30秒
                arrival_time = now + timedelta(seconds=wait_s)

                arrivals.append(MetroArrival(
                    station_name=station_name,
                    line_id=line_id,
                    line_name=line.get("name", ""),
                    direction=direction,
                    platform=platform,
                    arrival_time=arrival_time.strftime("%H:%M:%S"),
                    wait_seconds=wait_s,
                    status=status,
                ))

        return arrivals

    def get_line_status(self, line_id: str) -> SubwayLineStatus:
        """获取线路运行状态"""
        line = SHENZHEN_METRO_LINES.get(line_id, {})
        status, delay = simulate_delay()

        message = "运营正常"
        affected = []
        if delay > 0:
            message = f"因设备故障，部分列车有{delay}分钟延误"
            affected = [s["name"] for s in line.get("stations", [])[:5]]

        return SubwayLineStatus(
            line_id=line_id,
            line_name=line.get("name", ""),
            color=line.get("color", "#000000"),
            status=line.get("status", "正常") if delay == 0 else "延误",
            status_message=message,
            delay_minutes=delay,
            affected_stations=affected,
        )

    def get_nearest_with_arrivals(
        self, lat: float, lon: float, limit: int = 3
    ) -> Optional[SubwayStation]:
        """获取最近站点及其到站信息（带缓存）"""
        cache_key = self._generate_cache_key("nearest", round(lat, 6), round(lon, 6))
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        nearest = self.find_nearest_station(lat, lon)
        if not nearest:
            return None

        arrivals = self.get_station_arrivals(
            nearest["name"], nearest["line_id"], limit
        )

        station = SubwayStation(
            name=nearest["name"],
            line_id=nearest["line_id"],
            line_name=nearest["line_name"],
            color=nearest["color"],
            lon=nearest["lon"],
            lat=nearest["lat"],
            distance_m=nearest["distance_m"],
            arrivals=arrivals,
            station_status="正常",
        )

        self._cache.set(cache_key, station)
        return station


# =============================================================================
# 深圳公交API
# =============================================================================

class ShenzhenBusAPI:
    """
    深圳公交实时数据API
    目前使用模拟数据，未来可对接深圳公交集团API
    """
    def __init__(self, cache_ttl: int = 45):
        self.cache_ttl = cache_ttl
        self._cache = get_cache(maxsize=500, ttl=cache_ttl)

    def _generate_cache_key(self, *args) -> str:
        args_str = "_".join(str(a) for a in args)
        return hashlib.md5(args_str.encode()).hexdigest()

    def find_nearby_stops(
        self, lat: float, lon: float, radius_m: float = 1000, limit: int = 10
    ) -> List[Dict]:
        """查找附近公交站点"""
        nearby = []
        for stop in ALL_BUS_STOPS:
            dist = haversine_m(lat, lon, stop["lat"], stop["lon"])
            if dist <= radius_m:
                stop["distance_m"] = round(dist, 0)
                nearby.append(stop)

        nearby.sort(key=lambda x: x["distance_m"])
        return nearby[:limit]

    def get_stop_arrivals(self, stop_name: str, route_id: str) -> List[BusArrival]:
        """获取站点公交到站信息"""
        arrivals = []
        now = datetime.now()

        for route in NANSHAN_BUS_ROUTES:
            if route["route_id"] == route_id:
                interval = (route.get("interval_peak", 300) if is_peak_hour()
                          else route.get("interval_offpeak", 480))

                # 模拟2-3辆车的到站
                for i in range(random.randint(2, 3)):
                    wait_m = (interval // 60) * (i + 1) + random.randint(1, 5)
                    wait_m = max(2, wait_m)  # 至少2分钟
                    arrival_time = now + timedelta(minutes=wait_m)

                    # 模拟公交车当前位置
                    dist_km = round(random.uniform(1.5, 8.5), 1)

                    arrivals.append(BusArrival(
                        route_id=route_id,
                        route_name=route["route_name"],
                        direction=route["direction"],
                        stop_name=stop_name,
                        arrival_time=arrival_time.strftime("%H:%M:%S"),
                        wait_minutes=wait_m,
                        distance_km=dist_km,
                    ))

        return arrivals

    def get_nearby_stops_with_arrivals(
        self, lat: float, lon: float, limit: int = 5
    ) -> List[BusStop]:
        """获取附近站点及其到站信息（带缓存）"""
        cache_key = self._generate_cache_key("nearby", round(lat, 6), round(lon, 6), limit)
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        nearby = self.find_nearby_stops(lat, lon, limit=limit)
        result = []

        for stop in nearby:
            arrivals = self.get_stop_arrivals(stop["name"], stop["route_id"])
            bus_stop = BusStop(
                name=stop["name"],
                route_id=stop["route_id"],
                route_name=stop["route_name"],
                lon=stop["lon"],
                lat=stop["lat"],
                distance_m=stop["distance_m"],
                arrivals=arrivals,
                stop_status="正常",
            )
            result.append(bus_stop)

        self._cache.set(cache_key, result)
        return result


# =============================================================================
# 单例实例
# =============================================================================

_metro_api: Optional[ShenzhenMetroAPI] = None
_bus_api: Optional[ShenzhenBusAPI] = None


def get_metro_api() -> ShenzhenMetroAPI:
    global _metro_api
    if _metro_api is None:
        _metro_api = ShenzhenMetroAPI(cache_ttl=60)
    return _metro_api


def get_bus_api() -> ShenzhenBusAPI:
    global _bus_api
    if _bus_api is None:
        _bus_api = ShenzhenBusAPI(cache_ttl=45)
    return _bus_api


# =============================================================================
# 核心导出函数（供 routing_api.py 调用）
# =============================================================================

async def get_nearest_subway_station(
    lat: float,
    lon: float,
    include_arrivals: bool = True
) -> NearbySubwayStation:
    """
    获取最近的地铁站及其实时到站信息

    Args:
        lat: 纬度
        lon: 经度
        include_arrivals: 是否包含到站信息

    Returns:
        NearbySubwayStation: 最近地铁站及实时信息
    """
    api = get_metro_api()

    if include_arrivals:
        station = await asyncio.get_event_loop().run_in_executor(
            None, api.get_nearest_with_arrivals, lat, lon, 3
        )
    else:
        station_data = await asyncio.get_event_loop().run_in_executor(
            None, api.find_nearest_station, lat, lon
        )
        if station_data:
            station = SubwayStation(
                name=station_data["name"],
                line_id=station_data["line_id"],
                line_name=station_data["line_name"],
                color=station_data["color"],
                lon=station_data["lon"],
                lat=station_data["lat"],
                distance_m=station_data["distance_m"],
                arrivals=[],
                station_status="正常",
            )
        else:
            station = None

    if station is None:
        raise ValueError("附近未找到地铁站")

    # 计算步行时间（约75米/分钟）
    walking_time = round(station.distance_m / 75, 1)

    return NearbySubwayStation(
        origin_lon=lon,
        origin_lat=lat,
        station=station,
        walking_time_min=walking_time,
    )


async def get_nearest_bus_stops(
    lat: float,
    lon: float,
    limit: int = 5
) -> NearbyBusStops:
    """
    获取最近的公交站点及其到站预测

    Args:
        lat: 纬度
        lon: 经度
        limit: 返回站点数量

    Returns:
        NearbyBusStops: 附近公交站点列表
    """
    api = get_bus_api()
    stops = await asyncio.get_event_loop().run_in_executor(
        None, api.get_nearby_stops_with_arrivals, lat, lon, limit
    )

    return NearbyBusStops(
        origin_lon=lon,
        origin_lat=lat,
        count=len(stops),
        stops=stops,
    )


async def get_subway_line_status(line_id: str) -> SubwayLineStatusResponse:
    """
    获取地铁线路实时状态

    Args:
        line_id: 线路ID (1, 2, 5, 11)

    Returns:
        SubwayLineStatusResponse: 线路状态信息
    """
    api = get_metro_api()
    line_status = await asyncio.get_event_loop().run_in_executor(
        None, api.get_line_status, line_id
    )

    # 获取线路所有站点
    stations_data = await asyncio.get_event_loop().run_in_executor(
        None, api.get_stations, line_id
    )

    stations = []
    for station_data in stations_data:
        arrivals = await asyncio.get_event_loop().run_in_executor(
            None, api.get_station_arrivals, station_data["name"], line_id, 2
        )
        stations.append(SubwayStation(
            name=station_data["name"],
            line_id=line_id,
            line_name=line_status.line_name,
            color=line_status.color,
            lon=station_data["lon"],
            lat=station_data["lat"],
            distance_m=0,
            arrivals=arrivals,
            station_status=line_status.status,
        ))

    return SubwayLineStatusResponse(
        line_id=line_id,
        line=line_status,
        stations=stations,
    )


async def get_combined_transit_analysis(
    lat: float,
    lon: float,
    time_threshold: int = 15
) -> CombinedTransitAnalysis:
    """
    综合交通分析：结合地铁+公交+步行

    Args:
        lat: 纬度
        lon: 经度
        time_threshold: 时间阈值（分钟）

    Returns:
        CombinedTransitAnalysis: 综合出行分析结果
    """
    loop = asyncio.get_event_loop()

    # Get metro and bus data
    metro_api = get_metro_api()
    bus_api = get_bus_api()

    subway_station = await loop.run_in_executor(
        None, metro_api.get_nearest_with_arrivals, lat, lon, 4
    )
    bus_stops = await loop.run_in_executor(
        None, bus_api.get_nearby_stops_with_arrivals, lat, lon, 8
    )

    # Get subway arrivals (already fetched above)
    subway_arrivals = subway_station.arrivals if subway_station else []
    bus_arrivals = []
    for stop in bus_stops:
        bus_arrivals.extend(stop.arrivals)

    # 生成出行建议
    recommendations = []
    optimal_transport = {}

    if subway_station and subway_arrivals:
        nearest_subway = subway_station
        first_arrival = subway_arrivals[0] if subway_arrivals else None

        if first_arrival:
            total_time = (nearest_subway.distance_m / 75 +  # 步行时间
                         first_arrival.wait_seconds / 60)    # 等待时间

            if total_time <= time_threshold:
                recommendations.append(
                    f"推荐乘坐{nearest_subway.line_name} {nearest_subway.name}站，"
                    f"约{total_time:.0f}分钟可达"
                )
                optimal_transport = {
                    "type": "metro",
                    "line": nearest_subway.line_name,
                    "station": nearest_subway.name,
                    "wait_min": round(first_arrival.wait_seconds / 60, 1),
                    "walk_min": round(nearest_subway.distance_m / 75, 1),
                    "total_min": round(total_time, 1),
                }
    elif bus_stops and bus_arrivals:
        nearest_bus = bus_stops[0]
        first_bus_arrival = bus_arrivals[0] if bus_arrivals else None

        if first_bus_arrival:
            total_time = (nearest_bus.distance_m / 75 +
                         first_bus_arrival.wait_minutes)

            if total_time <= time_threshold:
                recommendations.append(
                    f"推荐乘坐{bus_stops[0].route_name}路公交，"
                    f"在{nearest_bus.name}站等候约{total_time:.0f}分钟"
                )
                optimal_transport = {
                    "type": "bus",
                    "route": nearest_bus.route_name,
                    "stop": nearest_bus.name,
                    "wait_min": first_bus_arrival.wait_minutes,
                    "walk_min": round(nearest_bus.distance_m / 75, 1),
                    "total_min": round(total_time, 1),
                }

    if not recommendations:
        recommendations.append("附近交通设施较少，建议使用其他出行方式")

    # 添加额外建议
    if subway_station and bus_stops:
        if subway_station.distance_m < bus_stops[0].distance_m:
            recommendations.append(
                f"地铁站较近（{nearest_subway.distance_m:.0f}米），优先考虑地铁出行"
            )
        else:
            recommendations.append(
                f"公交站更近（{bus_stops[0].distance_m:.0f}米），可关注实时公交"
            )

    return CombinedTransitAnalysis(
        origin_lon=lon,
        origin_lat=lat,
        time_threshold_min=time_threshold,
        nearest_subway=subway_station,
        nearest_bus_stops=bus_stops[:5],
        subway_arrivals=subway_arrivals,
        bus_arrivals=bus_arrivals[:10],
        recommendations=recommendations,
        optimal_transport=optimal_transport or None,
    )


# =============================================================================
# 辅助函数：获取所有线路信息
# =============================================================================

def get_all_metro_lines() -> List[Dict]:
    """获取所有地铁线路摘要"""
    return [
        {
            "line_id": line_id,
            "name": info["name"],
            "color": info["color"],
            "station_count": len(info["stations"]),
            "status": info["status"],
        }
        for line_id, info in SHENZHEN_METRO_LINES.items()
    ]


def get_all_bus_routes() -> List[Dict]:
    """获取所有公交线路摘要"""
    return [
        {
            "route_id": r["route_id"],
            "name": r["route_name"],
            "direction": r["direction"],
            "stop_count": len(r["stops"]),
        }
        for r in NANSHAN_BUS_ROUTES
    ]


# =============================================================================
# 调试/测试入口
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Shenzhen Metro/Bus Real-time Data Module - Test")
    print("=" * 60)

    # Test coordinates: Near Nanshan Tech Park
    test_lat = 22.5433
    test_lon = 114.0630

    async def test():
        print(f"\n[Test] Location: ({test_lat}, {test_lon})")
        print("-" * 40)

        # Test nearest subway station
        print("\n[Metro] Nearest Station:")
        subway = await get_nearest_subway_station(test_lat, test_lon)
        print(f"   Station: {subway.station.name}")
        print(f"   Line: {subway.station.line_name}")
        print(f"   Distance: {subway.station.distance_m:.0f}m")
        print(f"   Next Arrival: {subway.station.arrivals[0].wait_seconds // 60}min"
              f"{subway.station.arrivals[0].wait_seconds % 60}s")

        # Test bus stops
        print("\n[Bus] Nearby Stops:")
        bus = await get_nearest_bus_stops(test_lat, test_lon, limit=3)
        for stop in bus.stops:
            print(f"   {stop.name} ({stop.route_name}) - {stop.distance_m:.0f}m")

        # Test line status
        print("\n[Metro] Line 1 Status:")
        status = await get_subway_line_status("1")
        print(f"   Status: {status.line.status}")
        print(f"   Message: {status.line.status_message}")

        # Test combined analysis
        print("\n[Analysis] Combined (15min threshold):")
        analysis = await get_combined_transit_analysis(test_lat, test_lon, 15)
        for rec in analysis.recommendations:
            print(f"   - {rec}")
        if analysis.optimal_transport:
            opt = analysis.optimal_transport
            print(f"   Optimal: {opt.get('type')} - "
                  f"Total time {opt.get('total_min')}min")

    asyncio.run(test())
