"""
彻底修复 Notebook 双重编码问题
==============================
从备份文件重新修复所有残留乱码
"""
import json, os, sys, io, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究'
FILENAME = '15min_urban_accessibility_SCI.ipynb'
BACKUP = os.path.join(BASE_DIR, FILENAME + '.backup_before_encoding_fix')
FIXED_BACKUP = os.path.join(BASE_DIR, FILENAME + '.backup_before_fix2')

filepath = os.path.join(BASE_DIR, FILENAME)


def fix_text(text):
    """Fix garbled text using latin-1 double-decode"""
    if not text or not isinstance(text, str):
        return text
    try:
        fixed = text.encode('latin-1').decode('utf-8')
        if any(0x4e00 <= ord(c) <= 0x9fff for c in fixed):
            return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return text


def fix_notebook(input_path, output_path):
    """Fix all cells in notebook and save to output_path"""
    with open(input_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    report = []
    total_fixed = 0
    
    for cell_idx, cell in enumerate(nb['cells']):
        if 'source' not in cell:
            continue
        
        src_list = cell['source']
        if isinstance(src_list, str):
            src_list = [src_list]
        
        new_list = []
        cell_fixed = False
        
        for part in src_list:
            if isinstance(part, str):
                # Try fixing each line individually
                lines = part.split('\n')
                fixed_lines = []
                for line in lines:
                    fixed_line = fix_text(line)
                    if fixed_line != line:
                        cell_fixed = True
                    fixed_lines.append(fixed_line)
                new_list.append('\n'.join(fixed_lines))
            else:
                new_list.append(part)
        
        cell['source'] = new_list
        src_full = ''.join(new_list)
        cjk = sum(1 for c in src_full if 0x4e00 <= ord(c) <= 0x9fff)
        garbled = sum(1 for c in src_full if 0x80 <= ord(c) <= 0xFF)
        
        ct = cell.get('cell_type', '?')
        first = src_full.split('\n')[0][:50] if src_full else '(empty)'
        report.append(f'Cell {cell_idx:2d} | {ct:8s} | garbled:{garbled:5d} | cjk:{cjk:5d} | {first}')
        
        if cell_fixed:
            total_fixed += 1
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    
    return total_fixed, report


def main():
    print("=" * 60)
    print("FULL NOTEBOOK ENCODING FIX - Round 2")
    print("=" * 60)
    
    # Verify backup exists
    if not os.path.exists(BACKUP):
        print(f"ERROR: Backup not found: {BACKUP}")
        return
    
    # Backup current file first (in case fix script ran before)
    shutil.copy2(filepath, FIXED_BACKUP)
    print(f"[1] Current file backed up to: {FIXED_BACKUP}")
    
    # Fix from backup
    print(f"\n[2] Running full fix from backup: {BACKUP}")
    total_fixed, report = fix_notebook(BACKUP, filepath)
    
    print(f"\n[3] Fix results ({total_fixed} cells modified):")
    for line in report:
        print(line)
    
    # Verify result
    print(f"\n[4] Verification:")
    with open(filepath, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    total_garbled = 0
    total_cjk = 0
    for cell in nb['cells']:
        src = ''.join(cell.get('source', ['']))
        total_garbled += sum(1 for c in src if 0x80 <= ord(c) <= 0xFF)
        total_cjk += sum(1 for c in src if 0x4e00 <= ord(c) <= 0x9fff)
    
    print(f"  Total garbled chars remaining: {total_garbled}")
    print(f"  Total CJK chars: {total_cjk}")
    
    # Show cell 0 preview
    cell0 = nb['cells'][0]
    src0 = ''.join(cell0['source'])
    print(f"\n  Cell 0 preview:\n  {src0[:150]}")
    
    print(f"\n[5] Saved: {filepath}")
    print("=" * 60)


if __name__ == '__main__':
    main()
