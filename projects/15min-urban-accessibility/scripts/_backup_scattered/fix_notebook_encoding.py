"""
修复 Notebook 双重编码问题
=============================
问题根源：UTF-8 中文文本被错误地用 latin-1 方式存储在 JSON 中
修复方法：对每个 cell 的 source 字符串执行 latin-1 -> UTF-8 双重解码

运行方法：
    python fix_notebook_encoding.py
"""
import json
import os
import sys
import shutil
import io

# 强制 UTF-8 输出（解决 Windows GBK 控制台乱码）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================
# 配置
# ============================================================
BASE_DIR = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究'
FILENAME = '15min_urban_accessibility_SCI.ipynb'
BACKUP_SUFFIX = '.backup_before_encoding_fix'

filepath = os.path.join(BASE_DIR, FILENAME)
backup_path = filepath + BACKUP_SUFFIX
report_path = os.path.join(BASE_DIR, 'encoding_fix_report.txt')


# ============================================================
# 核心修复函数
# ============================================================

def try_fix_garbled(text):
    """
    尝试修复乱码文本。
    原理：乱码文本是 UTF-8 字节被 latin-1 解码后的结果。
    修复：先编码回 latin-1 字节，再以 UTF-8 解码。
    Returns: (fixed_text, was_fixed, was_already_ok)
    """
    if not text or not isinstance(text, str):
        return text, False, False

    # 检查是否有需要修复的字符（0x80-0xFF 范围内的 latin-1 字符）
    has_garbled = any(0x80 <= ord(c) <= 0xFF for c in text)
    
    if not has_garbled:
        has_cjk = any(0x4e00 <= ord(c) <= 0x9fff for c in text)
        return text, False, has_cjk

    # 尝试双重解码修复
    try:
        fixed = text.encode('latin-1').decode('utf-8')
        has_cjk = any(0x4e00 <= ord(c) <= 0x9fff for c in fixed)
        if has_cjk:
            return fixed, True, False
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    return text, False, False


def scan_cell_for_syntax_issues(cell_src, cell_idx):
    """检查 cell 源代码是否有语法问题"""
    issues = []
    stripped = cell_src.strip()
    if not stripped or stripped.startswith('#') or stripped.startswith('*'):
        return issues
    if stripped.startswith('!'):
        return issues
    
    lines = cell_src.split('\n')
    
    # 1. 检查双重括号问题
    for lineno, line in enumerate(lines, 1):
        if '))))' in line:
            issues.append(f"  Line {lineno}: 双重括号 '))))' - {line.strip()[:60]}")
    
    # 2. 检查 LaTeX 反斜杠（在 JSON 字符串中需要转义）
    for lineno, line in enumerate(lines, 1):
        stripped_line = line.strip()
        if stripped_line.startswith('"') and '\\' in stripped_line:
            latex_cmds = [r'\sum', r'\frac', r'\left', r'\right', r'\bar',
                          r'\hat', r'\sigma', r'\alpha', r'\beta', r'\gamma',
                          r'\delta', r'\infty', r'\times', r'\leq', r'\geq',
                          r'\cdot', r'\epsilon', r'\sqrt', r'\int', r'\log']
            for cmd in latex_cmds:
                if cmd in stripped_line and '\\\\' not in stripped_line:
                    issues.append(f"  Line {lineno}: LaTeX 命令 '{cmd}' 在 JSON 中需要双反斜杠")
                    break
    
    return issues


# ============================================================
# 主修复流程
# ============================================================

def log(msg):
    print(msg)

def main():
    log("=" * 60)
    log("Notebook Double-Encoding Fix Tool")
    log("=" * 60)
    log(f"\nTarget: {filepath}")
    
    # Step 1: 创建备份
    if os.path.exists(backup_path):
        log(f"[SKIP] Backup already exists: {backup_path}")
    else:
        shutil.copy2(filepath, backup_path)
        log(f"[OK] Backup created: {backup_path}")
    
    # Step 2: 读取文件
    log(f"\n[READ] Loading notebook...")
    with open(filepath, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    total_cells = len(nb['cells'])
    log(f"[OK] Loaded {total_cells} cells")
    
    # Step 3: 修复乱码
    log(f"\n[FIX] Scanning and fixing garbled text...")
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("Notebook Encoding Fix Report")
    report_lines.append("=" * 60)
    report_lines.append(f"File: {FILENAME}")
    report_lines.append(f"Total cells: {total_cells}")
    report_lines.append("")

    total_fixed = 0
    total_ok = 0
    total_unchanged = 0
    
    for cell_idx, cell in enumerate(nb['cells']):
        if 'source' not in cell:
            continue
        
        cell_type = cell.get('cell_type', 'unknown')
        src_list = cell['source']
        if isinstance(src_list, str):
            src_list = [src_list]
        
        new_source = []
        cell_was_fixed = False
        
        for part in src_list:
            if isinstance(part, str):
                fixed, was_fixed, was_ok = try_fix_garbled(part)
                new_source.append(fixed)
                if was_fixed:
                    cell_was_fixed = True
            else:
                new_source.append(part)
        
        cell['source'] = new_source
        src_full = ''.join(new_source)
        
        if cell_was_fixed:
            total_fixed += 1
            status = "FIXED"
        elif any(0x4e00 <= ord(c) <= 0x9fff for c in src_full):
            total_ok += 1
            status = "OK_CJK"
        else:
            total_unchanged += 1
            status = "OK"
        
        first_line = src_full.split('\n')[0][:50] if src_full else '(empty)'
        report_lines.append(f"Cell {cell_idx:2d} | {cell_type:8s} | {status:10s} | {first_line}")
    
    report_lines.append("")
    report_lines.append(f"Cells fixed: {total_fixed}")
    report_lines.append(f"Cells with CJK: {total_ok}")
    report_lines.append(f"Cells unchanged: {total_unchanged}")
    
    # Step 4: 保存
    log(f"\n[SAVE] Saving fixed notebook...")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    log(f"[OK] Saved: {filepath}")
    
    # Step 5: 验证
    log(f"\n[VERIFY] Verifying fix...")
    with open(filepath, 'r', encoding='utf-8') as f:
        nb_verify = json.load(f)
    
    cell0_src = ''.join(nb_verify['cells'][0]['source'])
    has_cjk = any(0x4e00 <= ord(c) <= 0x9fff for c in cell0_src[:200])
    log(f"  Cell 0 has correct CJK: {'YES' if has_cjk else 'NO'}")
    log(f"  Cell 0 preview: {cell0_src[:80]}")
    
    # Step 6: 语法检查
    log(f"\n[SYNTAX] Checking code cell syntax...")
    syntax_report = []
    syntax_report.append("\nSyntax Check Report:")
    syntax_report.append("=" * 60)
    
    for cell_idx, cell in enumerate(nb_verify['cells']):
        if cell.get('cell_type') != 'code':
            continue
        src = ''.join(cell.get('source', ['']))
        issues = scan_cell_for_syntax_issues(src, cell_idx)
        if issues:
            syntax_report.append(f"\nCell {cell_idx} issues:")
            for issue in issues:
                syntax_report.append(issue)
                log(issue)
    
    if not any(syntax_report):
        log("  No syntax issues found")
    
    # 写入报告
    report_lines.extend(syntax_report)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    log(f"\n[REPORT] Full report: {report_path}")
    
    log("")
    log("=" * 60)
    log(f"Done! Fixed {total_fixed} cells. Backup: {backup_path}")
    log("=" * 60)
    
    return nb_verify


if __name__ == '__main__':
    main()
