import re
with open(r'e:\xicha gis 智能定位\fang_2017-08-02.sql', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

pos = content.find('INSERT INTO `t_sz_village`')
semi = content.find(';', pos+10)
block = content[pos:semi+1]
lines = block.split('\n')

for i, l in enumerate(lines):
    s = l.strip()
    if s and 'VALUES' not in s.upper() and s.startswith('('):
        print('First data line:', repr(s[:100]))
        print('Digit match:', bool(re.match(r'\([\d]+,', s)))
        break

# Test new regex
print('\nNew regex test:')
test_lines = [
    "(1,'花样年花郡家园','宝安大道',12345)",
    "(123,'中洲·中央一街商铺','深圳',0)",
    "(1541,'万科公园里商铺','罗湖',50000)",
    "	(1234,'test','addr',0)",
]
for t in test_lines:
    m = re.match(r'\([\d]+,', t.strip())
    print(' ', t.strip()[:50], '-> matched:', bool(m))
