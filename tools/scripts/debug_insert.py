import re, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
with open(r'e:\xicha gis 智能定位\fang_2017-08-02.sql', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 找深圳表的完整 INSERT 块
q = 'INSERT INTO `t_sz_village`'
start = content.find(q)
print('Found at position:', start)

# 找到这个 INSERT 结束（在分号+换行处）
end = content.find(';', start + 10) if start >= 0 else -1
print('Semicolon at:', end)

if start >= 0 and end >= 0:
    block = content[start:end+1]
    print('Block length:', len(block), 'chars')
    
    # 看看是不是多行 VALUES
    lines = block.split('\n')
    print('Total lines in block:', len(lines))
    print('--- First 5 lines ---')
    for l in lines[:5]:
        print(repr(l[:150]))
    print('--- Last 3 lines ---')
    for l in lines[-3:]:
        print(repr(l[:150]))
    
    # 检查格式：是否每行一个VALUES
    print()
    print('Values lines (含 VALUES keyword):', sum(1 for l in lines if 'VALUES' in l.upper() or l.strip().startswith('(')))
    
    # 试试不同的解析方式
    # 方式1: 找所有 (数字开头 的行
    rows = [l.strip() for l in lines if l.strip().startswith('(')]
    print('Data rows found:', len(rows))
    
    # 方式2: 找所有 (id,' 模式的行
    rows2 = [l.strip() for l in lines if re.match(r"\(\d+,'", l.strip())]
    print('Data rows (id comma pattern):', len(rows2))
