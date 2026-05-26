import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def parse_row(s):
    vals, cur, in_str, qc = [], '', False, None
    for i, c in enumerate(s):
        if not in_str:
            if c in ("'", '"'):
                in_str, qc = True, c
            elif c == ',':
                vals.append(cur.strip().strip("'\""))
                cur = ''
            else:
                cur += c
        else:
            if c == qc and i + 1 < len(s) and s[i + 1] == qc:
                cur += qc; i += 1
            elif c == qc:
                in_str = False
            else:
                cur += c
    if cur.strip():
        vals.append(cur.strip().strip("'\""))
    return vals

def clean_text(t):
    if not t: return ''
    return t.strip().replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')

def safe_int(v, d=0):
    try: return int(str(v).strip().strip("'\""))
    except: return d

with open(r'e:\xicha gis 智能定位\fang_2017-08-02.sql', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

table_key = 'INSERT INTO `t_sz_village`'
pos = content.find(table_key)
semi = content.find(';', pos + 10)
block = content[pos:semi+1]
lines = block.split('\n')

records = []
for line in lines:
    s = line.strip()
    if not s or 'VALUES' in s.upper(): continue
    if not re.match(r'\(\d+,', s): continue
    row_text = s.lstrip('\t').rstrip(',;')
    vals = parse_row(row_text)
    if vals and len(vals) >= 7:
        records.append({
            'id': safe_int(vals[0]),
            'housetitle': clean_text(vals[1]),
            'address': clean_text(vals[2]),
            'quxian': clean_text(vals[3]),
        })

print('Total parsed:', len(records))

# Check dedup keys
seen_keys = {}
for r in records:
    key = (r['housetitle'], r['address'], r['quxian'])
    if key in seen_keys:
        if len(seen_keys) < 5:
            print('DUPE KEY:', key, 'prev_id:', seen_keys[key], 'curr_id:', r['id'])
    else:
        seen_keys[key] = r['id']

print('Unique keys:', len(seen_keys))
print('Remaining after dedup:', len(records) - len(seen_keys))

# Check first 3 records
print('\nFirst 3 records:')
for r in records[:3]:
    print('  id=%d title=%s addr=%s quxian=%s' % (r['id'], r['housetitle'][:20], r['address'][:30], r['quxian']))
