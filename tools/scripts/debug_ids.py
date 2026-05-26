import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
with open(r'e:\xicha gis 智能定位\fang_2017-08-02.sql', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

table_key = 'INSERT INTO `t_sz_village`'
pos = content.find(table_key)
semi = content.find(';', pos + 10)
block = content[pos:semi+1]
lines = block.split('\n')

ids = []
for line in lines:
    s = line.strip()
    if 'VALUES' in s.upper():
        continue
    if not re.match(r'\(\d+,', s):
        continue
    m = re.match(r'\((\d+),', s)
    if m:
        ids.append(int(m.group(1)))

print('Total rows:', len(ids))
print('Unique ids:', len(set(ids)))
print('First 10:', ids[:10])
print('Last 5:', ids[-5:])
print('Min:', min(ids), 'Max:', max(ids))
print('Zero ids:', sum(1 for x in ids if x == 0))
dupes = [x for x in set(ids) if ids.count(x) > 1]
print('Duplicate count:', len(dupes))
if dupes:
    print('Sample dupes:', dupes[:5])
    print('Dupes appear:', [ids.count(x) for x in dupes[:3]])
