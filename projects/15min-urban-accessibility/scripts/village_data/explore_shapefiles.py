# -*- coding: utf-8 -*-
"""
Shapefile数据探索脚本 - 分析现有矢量数据的结构
"""

import struct
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

def read_shapefile_header(filepath):
    """读取shapefile的头部信息"""
    with open(filepath, 'rb') as f:
        file_code = struct.unpack('>i', f.read(4))[0]
        f.read(20)
        file_length = struct.unpack('>i', f.read(4))[0]
        version = struct.unpack('<i', f.read(4))[0]
        shape_type = struct.unpack('<i', f.read(4))[0]
        
        xmin = struct.unpack('<d', f.read(8))[0]
        ymin = struct.unpack('<d', f.read(8))[0]
        xmax = struct.unpack('<d', f.read(8))[0]
        ymax = struct.unpack('<d', f.read(8))[0]
        
    shape_types = {
        0: 'Null', 1: 'Point', 3: 'PolyLine', 5: 'Polygon',
        8: 'MultiPoint', 11: 'PointZ', 13: 'PolyLineZ', 15: 'PolygonZ'
    }
    
    print(f"\n{'='*60}")
    print(f"Shapefile: {os.path.basename(filepath)}")
    print(f"{'='*60}")
    print(f"  文件码: {file_code}")
    print(f"  文件长度: {file_length*2} bytes")
    print(f"  几何类型: {shape_types.get(shape_type, 'Unknown')} ({shape_type})")
    print(f"  边界盒 X: {xmin:.2f} ~ {xmax:.2f}")
    print(f"  边界盒 Y: {ymin:.2f} ~ {ymax:.2f}")
    
    return shape_type, {'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax}

def read_dbf_header(filepath):
    """读取dbf文件的头部"""
    with open(filepath, 'rb') as f:
        year = struct.unpack('B', f.read(1))[0] + 1900
        month = struct.unpack('B', f.read(1))[0]
        day = struct.unpack('B', f.read(1))[0]
        record_count = struct.unpack('<I', f.read(4))[0]
        header_size = struct.unpack('<H', f.read(2))[0]
        record_size = struct.unpack('<H', f.read(2))[0]
        
        print(f"\n  DBF信息:")
        print(f"    记录数: {record_count:,}")
        print(f"    日期: {year}-{month:02d}-{day:02d}")
        print(f"    头部长度: {header_size}")
        print(f"    记录长度: {record_size}")
        
        # 读取字段定义 (从第32字节开始)
        fields = []
        field_start = 1
        while True:
            data = f.read(32)
            if len(data) < 32:
                break
            if data[0] == 0x0D:  # 字段定义终止符
                break
            field_name = data[:11].rstrip(b'\x00').decode('latin-1', errors='ignore')
            field_type = chr(data[11])
            field_len = data[16]
            field_dec = data[17]
            fields.append({'name': field_name, 'type': field_type, 'length': field_len, 'start': field_start})
            field_start += field_len
        
        print(f"\n  字段结构 ({len(fields)} 个字段):")
        for i, field in enumerate(fields):
            print(f"    [{i+1:2d}] {field['name']:<20} {field['type']} ({field['length']})")
        
        # 跳到记录开始位置
        f.seek(header_size)
        
        # 读取第一条记录
        first_record = f.read(record_size)
        if len(first_record) >= record_size:
            print(f"\n  记录样本 (第一条):")
            for field in fields:
                start = field['start'] - 1  # 0-indexed
                val = first_record[start:start+field['length']].decode('utf-8', errors='ignore').strip()
                print(f"    {field['name']}: {val[:60]}")
        
        return fields, record_count

def read_prj(filepath):
    """读取prj文件"""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().strip()
        
        # 判断坐标系
        if 'UTM' in content.upper() and '49N' in content.upper():
            print(f"\n  📍 坐标系: WGS 1984 UTM Zone 49N (EPSG:32649)")
        elif 'CGCS2000' in content or 'CGCS_2000' in content:
            print(f"\n  📍 坐标系: CGCS2000")
        elif 'WGS_1984' in content:
            print(f"\n  📍 坐标系: WGS 1984")
        else:
            print(f"\n  📍 坐标系: {content[:80]}...")
        
        return content
    return None

# ==================== 主程序 ====================

base = r"E:\xicha gis 智能定位"

print("\n" + "="*70)
print("15分钟城市时间贫困研究 - 数据探索报告")
print("="*70)

# 1. 道路网络
print("\n\n" + "#"*70)
print("# 1. 道路网络数据 (nsPT.shp)")
print("#"*70)
shape, bounds = read_shapefile_header(os.path.join(base, "GData1", "nsPT.shp"))
fields, count = read_dbf_header(os.path.join(base, "GData1", "nsPT.dbf"))
read_prj(os.path.join(base, "GData1", "nsPT.prj"))

# 2. 建筑轮廓
print("\n\n" + "#"*70)
print("# 2. 建筑轮廓数据 (pdbuilding.shp)")
print("#"*70)
shape, bounds = read_shapefile_header(os.path.join(base, "气候图基础数据", "pdbuilding.shp"))
fields, count = read_dbf_header(os.path.join(base, "气候图基础数据", "pdbuilding.dbf"))
read_prj(os.path.join(base, "气候图基础数据", "pdbuilding.prj"))

# 3. 土地利用
print("\n\n" + "#"*70)
print("# 3. 土地利用数据 (pdlanduse.shp)")
print("#"*70)
shape, bounds = read_shapefile_header(os.path.join(base, "气候图基础数据", "pdlanduse.shp"))
fields, count = read_dbf_header(os.path.join(base, "气候图基础数据", "pdlanduse.dbf"))
read_prj(os.path.join(base, "气候图基础数据", "pdlanduse.prj"))

# 4. 等高线
print("\n\n" + "#"*70)
print("# 4. 等高线数据 (contour.shp)")
print("#"*70)
shape, bounds = read_shapefile_header(os.path.join(base, "GData1", "contour.shp"))
fields, count = read_dbf_header(os.path.join(base, "GData1", "contour.dbf"))
read_prj(os.path.join(base, "GData1", "contour.prj"))

# 5. TIN节点
print("\n\n" + "#"*70)
print("# 5. TIN节点数据 (nstinNode.shp)")
print("#"*70)
shape, bounds = read_shapefile_header(os.path.join(base, "GData1", "nstinNode.shp"))
fields, count = read_dbf_header(os.path.join(base, "GData1", "nstinNode.dbf"))
read_prj(os.path.join(base, "GData1", "nstinNode.prj"))

# 6. 行政边界
print("\n\n" + "#"*70)
print("# 6. 南山区边界数据")
print("#"*70)
read_shapefile_header(os.path.join(base, "气候图基础数据", "边界.shp"))
fields, count = read_dbf_header(os.path.join(base, "气候图基础数据", "边界.dbf"))
read_prj(os.path.join(base, "气候图基础数据", "边界.prj"))

# 7. 南山区数据
print("\n\n" + "#"*70)
print("# 7. 南山区行政边界 (区级边界New.shp)")
print("#"*70)
shape, bounds = read_shapefile_header(os.path.join(base, "GData2", "区级边界New.shp"))
fields, count = read_dbf_header(os.path.join(base, "GData2", "区级边界New.dbf"))
read_prj(os.path.join(base, "GData2", "区级边界New.prj"))

# 总结
print("\n\n" + "="*70)
print("数据探索总结")
print("="*70)

print("""
📊 现有可用数据:
   ✅ 道路网络 (nsPT.shp) - 可用于网络分析
   ✅ 建筑轮廓 (pdbuilding.shp) - 可识别社区类型
   ✅ 土地利用 (pdlanduse.shp) - 可识别功能区
   ✅ 等高线 (contour.shp) - 可计算地形起伏
   ✅ TIN节点 - DEM插值点
   ✅ 行政边界 - 南山区边界
   ⚠️  POI数据 - 在test.mdb中(需特殊方式读取)

📋 Access数据库(test.mdb) 67.29 MB
   包含POI兴趣点数据，但ODBC驱动不可用
   建议解决方案:
   1. 使用Access应用程序打开并导出为CSV
   2. 使用Windows自带的mdb工具(需安装Access Runtime)
   3. 在ArcGIS/QGIS中打开并导出

🔄 坐标系统一需求:
   当前数据坐标系: WGS 1984 UTM Zone 49N (EPSG:32649)
   目标坐标系: CGCS2000 3度带 (EPSG:4527, 中央经线114°E)
   转换方法: 已有的wgs84TOszPro.txt包含转换参数

📱 POI运营时间获取建议:
   - 大众点评API (需申请)
   - 高德地图POI API (有开放接口)
   - 实地调查采样
   - 已有研究数据共享
""")

print("="*70)
