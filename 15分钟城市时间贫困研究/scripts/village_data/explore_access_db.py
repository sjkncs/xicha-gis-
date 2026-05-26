# -*- coding: utf-8 -*-
"""
Access数据库探索脚本 - 分析test.mdb的结构和内容
用于：提取POI扩展字段（运营时间等）
"""

import pypyodbc
import os
import sys

# 强制UTF-8输出
sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

def explore_access_db(db_path):
    """探索Access数据库结构"""
    
    print("="*70)
    print("Access数据库结构分析")
    print("="*70)
    
        # 连接数据库
        # 尝试多种驱动格式
        drivers = [
            r'Driver={Microsoft Access Driver (*.mdb)};DBQ=' + db_path,
            r'Driver={Microsoft Access Driver (*.mdb)};DBQ=' + db_path + ';',
            r'Driver={Driver do Microsoft Access (*.mdb)};DBQ=' + db_path,
            r'Driver={Microsoft Access-Treiber (*.mdb)};DBQ=' + db_path,
        ]
        
        conn = None
        for conn_str in drivers:
            try:
                conn = pypyodbc.connect(conn_str)
                print(f"\n✅ 成功连接到: {os.path.basename(db_path)}")
                print(f"   驱动: {conn_str[:50]}...")
                print(f"   文件大小: {os.path.getsize(db_path) / 1024 / 1024:.2f} MB\n")
                break
            except Exception as e:
                continue
        
        if conn is None:
            print(f"❌ 所有连接方式均失败")
            print("尝试的直接连接方式:")
            for conn_str in drivers:
                print(f"  尝试: {conn_str[:80]}...")
            return
    
    # 获取所有表
    tables = [t[2] for t in cursor.tables(tableType='TABLE')]
    print(f"发现 {len(tables)} 个数据表:\n")
    
    for i, table_name in enumerate(tables, 1):
        print(f"  [{i}] {table_name}")
    
    print("\n" + "-"*70)
    
    # 分析每个表的结构
    table_info = {}
    
    for table_name in tables:
        print(f"\n\n{'='*70}")
        print(f"表名: {table_name}")
        print(f"{'='*70}")
        
        try:
            # 获取列信息
            columns = []
            for row in cursor.columns(table=table_name):
                columns.append({
                    'name': row[3],
                    'type': row[5],
                    'size': row[6],
                    'nullable': row[10]
                })
            
            print(f"\n字段结构 ({len(columns)} 个字段):")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                print(f"  • {col['name']:<30} {col['type']:<20} ({col['size']:<5}) {nullable}")
            
            # 获取记录数
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                count = cursor.fetchone()[0]
                print(f"\n记录数: {count:,}")
            except:
                pass
            
            # 获取样本数据
            try:
                cursor.execute(f"SELECT TOP 3 * FROM [{table_name}]")
                rows = cursor.fetchall()
                
                if rows and columns:
                    print(f"\n前3条记录样本:")
                    for row_idx, row in enumerate(rows):
                        print(f"\n  记录 {row_idx + 1}:")
                        for col_idx, col in enumerate(columns[:10]):  # 只显示前10个字段
                            val = row[col_idx]
                            if val is None:
                                val_str = "NULL"
                            elif isinstance(val, str) and len(val) > 50:
                                val_str = val[:50] + "..."
                            else:
                                val_str = str(val)
                            print(f"    {col['name']}: {val_str}")
                        if len(columns) > 10:
                            print(f"    ... (还有 {len(columns) - 10} 个字段)")
                
                table_info[table_name] = {
                    'columns': columns,
                    'count': count if 'count' in dir() else 'Unknown'
                }
                
            except Exception as e:
                print(f"  ⚠️ 读取样本数据失败: {e}")
        
        except Exception as e:
            print(f"  ❌ 分析表失败: {e}")
    
    cursor.close()
    conn.close()
    
    # 生成摘要
    print("\n\n" + "="*70)
    print("数据摘要")
    print("="*70)
    
    for table_name, info in table_info.items():
        col_count = len(info['columns'])
        record_count = info.get('count', 'Unknown')
        print(f"  {table_name:<30} {col_count:>3} 列, {record_count:>10} 条记录")
    
    # 查找可能包含时间字段的表
    print("\n\n" + "="*70)
    print("时间相关字段检测")
    print("="*70)
    
    time_keywords = ['时间', '时间', 'hour', 'time', 'open', 'close', '营业', '开放', 'operating', 'start', 'end', '开始', '结束', '上午', '下午', '夜间']
    
    found_time_fields = []
    for table_name, info in table_info.items():
        for col in info['columns']:
            col_name_lower = col['name'].lower()
            for kw in time_keywords:
                if kw.lower() in col_name_lower:
                    found_time_fields.append({
                        'table': table_name,
                        'field': col['name'],
                        'type': col['type']
                    })
                    break
    
    if found_time_fields:
        print(f"\n发现 {len(found_time_fields)} 个可能的时间相关字段:\n")
        for f in found_time_fields:
            print(f"  • [{f['table']}] {f['field']} ({f['type']})")
    else:
        print("\n未发现明显的时间相关字段")
    
    # 查找可能包含坐标的表
    print("\n\n" + "="*70)
    print("坐标相关字段检测")
    print("="*70)
    
    coord_keywords = ['lng', 'lon', 'lat', 'x', 'y', '经度', '纬度', 'longitude', 'latitude', 'coord', '坐标', 'lonlat']
    
    found_coord_fields = []
    for table_name, info in table_info.items():
        for col in info['columns']:
            col_name_lower = col['name'].lower()
            for kw in coord_keywords:
                if kw.lower() in col_name_lower:
                    found_coord_fields.append({
                        'table': table_name,
                        'field': col['name'],
                        'type': col['type']
                    })
                    break
    
    if found_coord_fields:
        print(f"\n发现 {len(found_coord_fields)} 个可能的坐标相关字段:\n")
        for f in found_coord_fields:
            print(f"  • [{f['table']}] {f['field']} ({f['type']})")
    else:
        print("\n未发现明显的坐标相关字段")
    
    print("\n\n" + "="*70)
    print("分析完成!")
    print("="*70)

# ==================== 主程序 ====================

if __name__ == "__main__":
    db_path = r"E:\xicha gis 智能定位\GData1\test.mdb"
    
    if os.path.exists(db_path):
        explore_access_db(db_path)
    else:
        print(f"❌ 文件不存在: {db_path}")
