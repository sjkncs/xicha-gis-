import sqlite3, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

db = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data\villages.db"
conn = sqlite3.connect(db)
cur = conn.cursor()

# Table schema
print("=== TABLE SCHEMA ===")
cur.execute("PRAGMA table_info(sz_village)")
for row in cur.fetchall():
    print(row)

print("\n=== TOTAL ROWS ===")
cur.execute("SELECT COUNT(*) FROM sz_village")
print(cur.fetchone())

print("\n=== SAMPLE ROWS ===")
cur.execute("SELECT id, housetitle, quxian, shangquan FROM sz_village LIMIT 5")
for row in cur.fetchall():
    print(row)

print("\n=== DISTINCT QUXIAN ===")
cur.execute("SELECT DISTINCT quxian FROM sz_village LIMIT 20")
for row in cur.fetchall():
    print(row)

conn.close()
