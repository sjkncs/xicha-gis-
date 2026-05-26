import sqlite3
db = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data\villages.db"
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT geocode_status, COUNT(*) FROM sz_village GROUP BY geocode_status")
for row in cur.fetchall():
    print(row)
cur.execute("SELECT COUNT(*) FROM sz_village WHERE lng IS NOT NULL AND lat IS NOT NULL")
print("With coords:", cur.fetchone()[0])
conn.close()
