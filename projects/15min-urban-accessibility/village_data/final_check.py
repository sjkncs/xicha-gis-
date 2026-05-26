import sqlite3, csv, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

db = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data\villages.db"
csv_out = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data\sz_village_geocoded.csv"

conn = sqlite3.connect(db)
cur = conn.cursor()

# Status breakdown
print("=== STATUS BREAKDOWN ===")
cur.execute("SELECT geocode_status, COUNT(*) FROM sz_village GROUP BY geocode_status ORDER BY COUNT(*) DESC")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== SAMPLE 5 ROWS ===")
cur.execute("SELECT housetitle, quxian, money, lng, lat, geocode_status FROM sz_village LIMIT 5")
for row in cur.fetchall():
    print(f"  {row}")

# Check how many have coordinates
cur.execute("SELECT COUNT(*) FROM sz_village WHERE lng IS NOT NULL AND lat IS NOT NULL")
print(f"\nWith coords: {cur.fetchone()[0]}")

# Check quxian distribution
print("\n=== QUXIAN DISTRIBUTION ===")
cur.execute("SELECT quxian, COUNT(*) FROM sz_village GROUP BY quxian ORDER BY COUNT(*) DESC LIMIT 20")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()

# Rewrite CSV from DB
print("\n=== REWRITING CSV ===")
conn = sqlite3.connect(db)
cur = conn.cursor()
rows = cur.execute("SELECT id, housetitle, address, quxian, shangquan, sqpinyin, money, lng, lat, geocode_status FROM sz_village").fetchall()
cols = ['id', 'housetitle', 'address', 'quxian', 'shangquan', 'sqpinyin', 'money', 'lng', 'lat', 'geocode_status']
with open(csv_out, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(cols)
    writer.writerows(rows)
conn.close()
print(f"CSV rewritten: {len(rows)} rows")
