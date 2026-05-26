"""
重建 SQLite 数据库（修复列数不匹配问题）
使用逐行迭代方法，匹配 pipeline_quick.py 的工作逻辑
"""
import sqlite3, os, io, sys, re, csv, json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

VILLAGE_DIR = Path(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data')
DB_PATH = VILLAGE_DIR / 'villages.db'

SZ_QUXIANS = ['宝安', '龙岗', '南山', '福田', '罗湖', '盐田', '龙华', '光明', '坪山', '大鹏']


def parse_row(line):
    """SQL 行解析器（引用感知），与 pipeline_quick.py 相同"""
    result = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch in " \t":
            i += 1
        elif ch == ',':
            result.append('')
            i += 1
        elif ch == "'":
            j = i + 1
            chars = []
            while j < n:
                if line[j] == "'":
                    if j + 1 < n and line[j + 1] == "'":
                        chars.append("'")
                        j += 2
                    else:
                        break
                elif line[j] == '\\':
                    j += 1
                    if j < n:
                        c = line[j]
                        m = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', "'": "'"}
                        chars.append(m.get(c, c))
                        j += 1
                else:
                    chars.append(line[j])
                    j += 1
            result.append(''.join(chars))
            i = j + 1
            while i < n and line[i] in ' \t':
                i += 1
            if i < n and line[i] == ',':
                i += 1
        elif ch == '(':
            j = i + 1
            buf = []
            depth = 1
            while j < n and depth > 0:
                cj = line[j]
                if cj == '(':
                    depth += 1
                elif cj == ')':
                    depth -= 1
                    if depth == 0:
                        break
                buf.append(cj)
                j += 1
            val = ''.join(buf).strip()
            result.append(val)
            i = j + 1
        else:
            j = i
            while j < n and line[j] not in ',)':
                j += 1
            result.append(line[i:j].strip())
            i = j
    return result


def find_sql_file():
    """找到 SQL 文件"""
    for base in [Path(r'e:\xicha gis 智能定位'),
                 Path(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究'),
                 Path(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\village_data')]:
        for f in base.glob('fang_2017-08-02.sql'):
            return f
    return None


def parse_and_filter(sql_file):
    """
    逐行解析 SQL 文件，与 pipeline_quick.py 逻辑完全一致
    """
    with open(sql_file, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # 找 INSERT INTO t_sz_village VALUES 块
    # 先找到 VALUES 关键词位置
    content_lower = content.lower()
    idx = content_lower.find('insert into `t_sz_village`')
    if idx == -1:
        idx = content_lower.find('insert into t_sz_village')
    if idx == -1:
        idx = content_lower.find('insert into')
    if idx == -1:
        print("ERROR: No INSERT found")
        return []

    # 提取从 INSERT 到文件末尾
    insert_block = content[idx:]

    # 找 VALUES 开始
    values_idx = insert_block.lower().find('values')
    if values_idx == -1:
        print("ERROR: No VALUES found")
        return []

    values_block = insert_block[values_idx + 6:]

    records = []
    seen = set()
    row_pattern = re.compile(r'\(\s*[\d]+\s*,')
    line_pattern = re.compile(r'\(\s*([\d]+)\s*,')

    for line in values_block.split('\n'):
        s = line.strip()
        if not s:
            continue
        if not row_pattern.match(s):
            continue

        m = line_pattern.match(s.lstrip())
        if not m:
            continue

        row_id_str = m.group(1)
        row_id = int(row_id_str)

        row_text = s.lstrip('\t(').rstrip(',;')
        vals = parse_row(row_text)

        if len(vals) < 7:
            continue

        housetitle = vals[1]
        address = vals[2] if len(vals) > 2 else ''
        quxian = vals[3] if len(vals) > 3 else ''
        shangquan = vals[4] if len(vals) > 4 else ''
        sqpinyin = vals[5] if len(vals) > 5 else ''
        money_str = vals[6] if len(vals) > 6 else '0'
        try:
            money = int(''.join(c for c in money_str if c.isdigit()))
        except:
            money = 0

        key = (housetitle, address, quxian)
        if key in seen:
            continue
        seen.add(key)

        is_sz = any(q in quxian for q in SZ_QUXIANS)
        is_sz = is_sz or any(q in address for q in SZ_QUXIANS)
        is_sz = is_sz or any(q in shangquan for q in SZ_QUXIANS)

        if is_sz:
            records.append({
                'id': row_id,
                'housetitle': housetitle,
                'address': address,
                'quxian': quxian,
                'shangquan': shangquan,
                'sqpinyin': sqpinyin,
                'money': money,
            })

    return records


def main():
    print("=" * 60)
    print("Rebuilding SQLite (line-by-line parse)")
    print("=" * 60)

    sql_file = find_sql_file()
    if not sql_file:
        print("ERROR: fang_2017-08-02.sql not found")
        return
    print(f"SQL file: {sql_file}")

    records = parse_and_filter(sql_file)
    print(f"Parsed records: {len(records)}")

    if not records:
        print("ERROR: No records parsed")
        return

    from collections import Counter
    quxians = Counter(r['quxian'] for r in records)
    print(f"\nDistrict distribution:")
    for q, cnt in quxians.most_common(15):
        print(f"  {q}: {cnt}")

    # 重建 SQLite
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE sz_village (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            housetitle TEXT NOT NULL,
            address TEXT,
            quxian TEXT,
            shangquan TEXT,
            sqpinyin TEXT,
            money INTEGER,
            lng REAL,
            lat REAL,
            geocode_status TEXT DEFAULT 'pending'
        )
    """)

    for r in records:
        cur.execute("""
            INSERT INTO sz_village
                (housetitle, address, quxian, shangquan, sqpinyin, money, geocode_status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (r['housetitle'], r['address'], r['quxian'],
              r['shangquan'], r['sqpinyin'], r['money']))

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM sz_village").fetchone()[0]
    conn.close()

    print(f"\nSQLite: {DB_PATH}")
    print(f"Records inserted: {total}")

    # CSV
    csv_path = VILLAGE_DIR / 'sz_village_geocoded.csv'
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'id', 'housetitle', 'address', 'quxian', 'shangquan',
            'sqpinyin', 'money', 'lng', 'lat', 'geocode_status'
        ])
        writer.writeheader()
        for r in records:
            writer.writerow({
                'id': '', 'housetitle': r['housetitle'],
                'address': r['address'], 'quxian': r['quxian'],
                'shangquan': r['shangquan'], 'sqpinyin': r.get('sqpinyin', ''),
                'money': r['money'], 'lng': '', 'lat': '', 'geocode_status': 'pending'
            })
    print(f"CSV: {csv_path}")

    print("\n[DONE]")
    print("Next: python geocode_district.py")


if __name__ == '__main__':
    main()
