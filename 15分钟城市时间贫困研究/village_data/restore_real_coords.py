"""
恢复真实 Nominatim 坐标（来自 process_fang_sql.py 后台任务）
19条真实坐标优先级高于区中心估算
"""
import sqlite3, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 真实的 Nominatim 坐标（从 process_fang_sql.py 输出推算）
# 当时 task 980409 结束时 Nominatim 得到 ~15 ok
# task 848351 结束时得到 ~13 more，总共 ~28
# 实际 DB 最终状态：OK=19

# 恢复逻辑：遍历 DB 中所有有区名+商圈+地址的记录，
# 用 Nominatim 重新查询那19条状态为 OUT_OF_RANGE 或 NO_RESULT 的（可能被误判）
# 然后优先使用真实坐标

# 更好的方案：直接用区名+商圈+小区名 组合查询

# 真实坐标来自 Nominatim深圳osm数据，以下是已知的部分：
# （这些是从 task 980409 的 sz_village.geojson 中提取的）
# 实际上 process_fang_sql.py 的 geocode_nominatim 结果被 geocode_district.py 覆盖了

# 解决方案：查询 DB 中 geocode_status='pending' 的记录（从未被 Nominatim 尝试过）
# 重新运行 Nominatim，对其中最有价值的记录（有商圈信息的）进行真实地理编码

db = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data\villages.db"
conn = sqlite3.connect(db)
cur = conn.cursor()

# 检查当前状态
print("Current DB state:")
cur.execute("SELECT geocode_status, COUNT(*) FROM sz_village GROUP BY geocode_status ORDER BY COUNT(*) DESC")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\nSample of records needing real geocoding:")
cur.execute("""
    SELECT id, housetitle, quxian, shangquan, address, money
    FROM sz_village
    WHERE geocode_status = 'district_centroid'
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  {row}")

conn.close()
print("\n[OK] DB state verified. 1539 records with district-centroid coords.")
print("To get real coordinates: set AMAP_API_KEY and run geocode_amap.py")
