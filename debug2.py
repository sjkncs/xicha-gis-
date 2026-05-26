import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open(r'e:\xicha gis 智能定位\fang_2017-08-02.sql', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

pos = content.find('INSERT INTO `t_sz_village`')
semi = content.find(';', pos+10)
block = content[pos:semi+1]
lines = block.split('\n')

records = []
for line in lines:
    s = line.strip()
    if 'VALUES' in s.upper():
        continue
    # Match: (digits,  - handles tab prefix and Chinese chars after
    m = re.match(r'\([\d]+,', s)
    if not m:
        continue
    row_text = s.lstrip('\t').rstrip(',;')
    vals = row_text.split(',')
    print('Row parsed, fields:', len(vals))
    print('  First field:', repr(vals[0][:30]))
    if len(vals) >= 8:
        print('  All good!')
        records.append(vals)
    if len(records) >= 3:
        break

print('Total records with >= 8 fields:', len(records))
