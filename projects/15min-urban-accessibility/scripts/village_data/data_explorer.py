# -*- coding: utf-8 -*-
"""
数据探索脚本 - 分析现有数据的结构和内容
用于：15分钟城市时间贫困研究
"""

import struct
import os
import sys

# 强制使用UTF-8编码
sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

def read_shapefile_header(filepath):
    """读取shapefile的头部信息"""
    with open(filepath, 'rb') as f:
        # 读取文件码（9994为大端序）
        file_code = struct.unpack('>i', f.read(4))[0]
        # 跳过20字节
        f.read(20)
        # 文件长度（16位字）
        file_length = struct.unpack('>i', f.read(4))[0]
        # 版本（小端序）
        version = struct.unpack('<i', f.read(4))[0]
        # 几何类型
        shape_type = struct.unpack('<i', f.read(4))[0]
        
        # 边界盒
        xmin = struct.unpack('<d', f.read(8))[0]
        ymin = struct.unpack('<d', f.read(8))[0]
        xmax = struct.unpack('<d', f.read(8))[0]
        ymax = struct.unpack('<d', f.read(8))[0]
        zmin = struct.unpack('<d', f.read(8))[0]
        zmax = struct.unpack('<d', f.read(8))[0]
        mmin = struct.unpack('<d', f.read(8))[0]
        mmax = struct.unpack('<d', f.read(8))[0]
        
    shape_types = {
        0: 'Null Shape', 1: 'Point', 3: 'PolyLine', 5: 'Polygon',
        8: 'MultiPoint', 11: 'PointZ', 13: 'PolyLineZ', 15: 'PolygonZ',
        18: 'MultiPointZ', 21: 'PointM', 23: 'PolyLineM', 25: 'PolygonM',
        28: 'MultiPointM', 31: 'MultiPatch'
    }
    
    print(f"\n{'='*60}")
    print(f"Shapefile: {os.path.basename(filepath)}")
    print(f"{'='*60}")
    print(f"文件码: {file_code} (预期: 9994)")
    print(f"文件长度: {file_length} (16位字 = {file_length*2} 字节)")
    print(f"版本: {version}")
    print(f"几何类型: {shape_types.get(shape_type, 'Unknown')} ({shape_type})")
    print(f"边界盒:")
    print(f"  X: {xmin:.6f} ~ {xmax:.6f}")
    print(f"  Y: {ymin:.6f} ~ {ymax:.6f}")
    
    return {
        'file_code': file_code, 'file_length': file_length,
        'version': version, 'shape_type': shape_type,
        'bounds': {'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax}
    }

def read_dbf_header(filepath):
    """读取dbf文件的头部和记录信息"""
    with open(filepath, 'rb') as f:
        version = struct.unpack('B', f.read(1))[0]
        year = struct.unpack('B', f.read(1))[0] + 1900
        month = struct.unpack('B', f.read(1))[0]
        day = struct.unpack('B', f.read(1))[0]
        
        record_count = struct.unpack('<I', f.read(4))[0]
        header_size = struct.unpack('<H', f.read(2))[0]
        record_size = struct.unpack('<H', f.read(2))[0]
        
        print(f"\nDBF: {os.path.basename(filepath)}")
        print(f"  版本: {version}, 日期: {year}-{month:02d}-{day:02d}")
        print(f"  记录数: {record_count}")
        print(f"  头部长度: {header_size} 字节")
        print(f"  记录长度: {record_size} 字节")
        
        # 读取字段定义
        fields = []
        while True:
            data = f.read(32)
            if data[0] == 0x0D:  # 字段定义终止符
                break
            field_name = data[:11].rstrip(b'\x00').decode('latin-1', errors='ignore')
            field_type = chr(data[11])
            field_len = data[16]
            field_dec = data[17]
            fields.append({
                'name': field_name,
                'type': field_type,
                'length': field_len,
                'decimal': field_dec
            })
        
        print(f"\n  字段结构 ({len(fields)} 个字段):")
        for i, field in enumerate(fields):
            print(f"    [{i+1}] {field['name']:<15} {field['type']} ({field['length']},{field['decimal']})")
        
        return fields, record_count

def read_dbf_records(filepath, max_records=5):
    """读取dbf文件的前几条记录"""
    with open(filepath, 'rb') as f:
        # 跳过头部
        f.seek(32)
        while True:
            data = f.read(32)
            if data[0] == 0x0D:
                break
        # 读取记录
        f.read(1)  # 删除标记
        
        records = []
        for i in range(max_records):
            data = f.read(1)  # 删除标记
            if data != b' ':
                continue
            record = {}
            pos = 1
            
            for field in fields[:15]:  # 限制字段数
                raw_data = f.read(field['length'])
                try:
                    if field['type'] == 'N':  # 数值
                        record[field['name']] = raw_data.strip().decode('latin-1', errors='ignore')
                    elif field['type'] == 'C':  # 字符
                        record[field['name']] = raw_data.strip().decode('utf-8', errors='ignore').strip()
                    elif field['type'] == 'D':  # 日期
                        record[field['name']] = raw_data.decode('latin-1', errors='ignore')
                    else:
                        record[field['name']] = raw_data.decode('latin-1', errors='ignore')
                except:
                    record[field['name']] = str(raw_data)
            
            records.append(record)
        
        print(f"\n  前 {len(records)} 条记录示例:")
        for i, rec in enumerate(records):
            print(f"\n    记录 {i+1}:")
            for k, v in list(rec.items())[:8]:
                print(f"      {k}: {v}")
        
        return records

def parse_prj(filepath):
    """解析prj文件内容"""
    if not os.path.exists(filepath):
        print(f"  PRJ文件不存在: {filepath}")
        return None
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read().strip()
    print(f"\nPRJ内容:")
    print(f"  {content[:200]}...")
    return content

# ==================== 主程序 ====================

base_dir = r"E:\xicha gis 智能定位"
workspace_dir = os.path.join(base_dir, "15分钟城市时间贫困研究")
os.makedirs(workspace_dir, exist_ok=True)

print("\n" + "="*70)
print("15分钟城市时间贫困研究 - 数据探索报告")
print("="*70)

# 1. 分析POI数据
print("\n\n" + "#"*70)
print("# 1. POI兴趣点数据 (NSPOI)")
print("#"*70)

poi_dir = os.path.join(base_dir, "GData1")
shp_info = read_shapefile_header(os.path.join(poi_dir, "NSPOI.shp"))
fields, count = read_dbf_header(os.path.join(poi_dir, "NSPOI.dbf"))
prj = parse_prj(os.path.join(poi_dir, "NSPOI.prj"))

# 判断坐标系
if 'UTM' in prj.upper() and '49N' in prj.upper():
    print("\n  ⚠️ 坐标系: WGS 1984 UTM Zone 49N (EPSG:32649)")
    print("  ⚠️ 注意: 需要转换为CGCS2000坐标系")
elif 'CGCS2000' in prj.upper():
    print("\n  ✅ 坐标系: CGCS2000")
    
# 2. 分析道路网络
print("\n\n" + "#"*70)
print("# 2. 道路网络数据 (nsPT)")
print("#"*70)

read_shapefile_header(os.path.join(poi_dir, "nsPT.shp"))
fields_road, count_road = read_dbf_header(os.path.join(poi_dir, "nsPT.dbf"))
parse_prj(os.path.join(poi_dir, "nsPT.prj"))

# 3. 分析建筑轮廓
print("\n\n" + "#"*70)
print("# 3. 建筑轮廓数据 (pdbuilding)")
print("#"*70)

build_dir = os.path.join(base_dir, "气候图基础数据")
read_shapefile_header(os.path.join(build_dir, "pdbuilding.shp"))
fields_build, count_build = read_dbf_header(os.path.join(build_dir, "pdbuilding.dbf"))
parse_prj(os.path.join(build_dir, "pdbuilding.prj"))

# 4. 分析TIN节点
print("\n\n" + "#"*70)
print("# 4. TIN节点数据 (nstinNode)")
print("#"*70)

read_shapefile_header(os.path.join(poi_dir, "nstinNode.shp"))
fields_tin, count_tin = read_dbf_header(os.path.join(poi_dir, "nstinNode.dbf"))

# 5. 分析行政边界
print("\n\n" + "#"*70)
print("# 5. 行政边界数据 (区级边界New)")
print("#"*70)

boundary_dir = os.path.join(base_dir, "GData2")
read_shapefile_header(os.path.join(boundary_dir, "区级边界New.shp"))
fields_bd, count_bd = read_dbf_header(os.path.join(boundary_dir, "区级边界New.dbf"))
parse_prj(os.path.join(boundary_dir, "区级边界New.prj"))

# 6. Access数据库分析
print("\n\n" + "#"*70)
print("# 6. Access数据库 (test.mdb) - 需要ODBC或mdb-tools")
print("#"*70)
mdb_path = os.path.join(poi_dir, "test.mdb")
print(f"  文件大小: {os.path.getsize(mdb_path) / 1024 / 1024:.1f} MB")
print("  注意: 需要使用mdb-tools或Python的pypyodbc读取")
print("  Windows下可尝试: pip install pypyodbc 或使用mdb-export命令行工具")

print("\n\n" + "="*70)
print("数据探索完成!")
print("="*70)

# 生成数据摘要
print("\n\n数据摘要:")
print(f"  POI点: {count:,} 个")
print(f"  道路线: {count_road:,} 条")
print(f"  建筑物: {count_build:,} 栋")
print(f"  TIN节点: {count_tin:,} 个")
print(f"  行政边界: {count_bd} 个")
print(f"  Access数据库: {os.path.getsize(mdb_path) / 1024 / 1024:.1f} MB")

print("\n下一步建议:")
print("  1. 安装geopandas处理矢量数据: pip install geopandas")
print("  2. 尝试读取Access数据库获取POI扩展字段(运营时间等)")
print("  3. 确认坐标系统一为CGCS2000")
print("  4. 准备小区AOI边界数据")
