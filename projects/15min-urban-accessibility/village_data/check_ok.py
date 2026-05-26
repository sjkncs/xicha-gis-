# -*- coding: utf-8 -*-
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

db = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data\villages.db"
conn = sqlite3.connect(db)
cur = conn.cursor()

print("=== GEOCODE STATUS ===")
cur.execute("SELECT geocode_status, COUNT(*) FROM sz_village GROUP BY geocode_status")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== OK RECORDS ===")
cur.execute("SELECT housetitle, quxian, money, lng, lat FROM sz_village WHERE geocode_status='OK'")
for row in cur.fetchall():
    print(f"  {row}")

print("\n=== QUXIAN DIST IN OK ===")
cur.execute("SELECT quxian, COUNT(*) FROM sz_village WHERE geocode_status='OK' GROUP BY quxian")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== ALL UNIQUE QUXIAN ===")
cur.execute("SELECT DISTINCT quxian FROM sz_village")
for row in cur.fetchall():
    print(f"  {row[0]}")

conn.close()
