import csv, sqlite3, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

csv_path = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data\sz_village_geocoded.csv"
db_path = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data\villages.db"

print("=== CSV HEAD ===")
with open(csv_path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    print(f"Total CSV rows: {len(rows)}")
    print(f"Columns: {reader.fieldnames}")
    print("\nFirst 3 rows:")
    for i, r in enumerate(rows[:3]):
        print(f"  {i}: {dict(r)}")

print("\n=== DB HEAD ===")
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM sz_village")
print(f"Total DB rows: {cur.fetchone()[0]}")
cur.execute("PRAGMA table_info(sz_village)")
print("Schema:")
for row in cur.fetchall():
    print(f"  {row}")
cur.execute("SELECT * FROM sz_village LIMIT 3")
print("\nFirst 3 DB rows:")
for row in cur.fetchall():
    print(f"  {row}")
conn.close()
