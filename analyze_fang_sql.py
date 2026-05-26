"""
分析 fang_2017-08-02.sql 数据库结构
"""
import re
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

path = r'e:\xicha gis 智能定位\fang_2017-08-02.sql'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 查找所有表名
tables = re.findall(r'# Dump of table (t_\w+)', content)
print('=== All Tables ===')
for t in tables:
    print(' ', t)

# 深圳相关表
print()
print('=== Shenzhen Table (t_sz_village) ===')
# 直接搜索 CREATE TABLE 语句
for table in ['t_sz_village', 't_bj_village', 't_gz_village', 't_sh_village']:
    create_match = re.search(
        rf'(CREATE TABLE `{re.escape(table)}`\s*\([\s\S]*?\)\s*\;)',
        content
    )
    if create_match:
        print(f'\n--- {table} ---')
        schema = create_match.group(1)
        print(schema[:1500])
        break

# 统计各表数据量
print()
print('=== Record Counts ===')
for table in tables:
    # 查找 INSERT INTO 语句数量（每个INSERT可能含多行）
    pattern = rf'INSERT INTO `{table}`'
    count = len(re.findall(pattern, content))
    print(f'  {table}: {count} INSERT statements')

# 提取一条深圳小区数据样本
print()
print('=== Shenzhen Sample Records ===')
# 找深圳表的INSERT数据
insert_pattern = r'INSERT INTO `t_sz_village`[\s\S]*?;'
inserts = re.findall(insert_pattern, content[:200000])
for i, ins in enumerate(inserts[:2]):
    print(f'\n--- INSERT {i+1} (first 800 chars) ---')
    print(ins[:800])
