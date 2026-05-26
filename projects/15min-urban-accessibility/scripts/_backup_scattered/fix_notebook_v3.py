"""
彻底修复 Notebook 双重编码 - 第三版
==========================================
核心问题：
1. 双重编码的中文 -> latin-1 -> UTF-8 双重解码修复
2. 孤立 UTF-8 续字节（如 ·=0xB7）-> 需要用 regex 匹配完整 UTF-8 序列
3. latin-1 特殊字符（如 ×=0xD7）-> 这些是 LaTeX 符号，需保留

策略：遍历原始字节，用 regex 匹配 UTF-8 序列，跳过孤立字节
"""
import json, os, sys, io, re, shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'
backup = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb.backup_before_encoding_fix'


# UTF-8 正则：匹配完整的 UTF-8 序列，跳过孤立字节
UTF8_RE = re.compile(
    b'('
    b'[\xf0-\xf7][\x80-\xbf]{2}[\x80-\xbf]'   # 4-byte
    b'|[\xe0-\xef][\x80-\xbf]{2}'              # 3-byte
    b'|[\xc0-\xdf][\x80-\xbf]'                  # 2-byte
    b'|[\x00-\x7f]'                              # ASCII
    b')+'
)


def fix_text_by_bytes(text):
    """
    通过原始字节修复双重编码文本。
    1. 将字符串编码为 latin-1 字节（保留每个字符的字节值）
    2. 用 regex 匹配有效的 UTF-8 序列
    3. 跳过孤立的续字节和无效字节
    4. 将有效字节解码为 UTF-8
    """
    if not text:
        return text

    # Step 1: 编码为 latin-1 获取原始字节
    try:
        raw_bytes = text.encode('latin-1')
    except (UnicodeEncodeError, AttributeError):
        return text

    # Step 2: 用 regex 匹配 UTF-8 序列
    matches = UTF8_RE.findall(raw_bytes)
    valid_bytes = b''.join(matches)

    # Step 3: 解码为 UTF-8
    try:
        return valid_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return text


def safe_decode(text):
    """安全的双重解码，失败时返回原文本"""
    if not text:
        return text
    # 尝试简单双重解码
    try:
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    # 尝试字节级修复
    return fix_text_by_bytes(text)


def fix_json_all_strings(obj):
    """递归修复 JSON 中所有字符串"""
    if isinstance(obj, str):
        return safe_decode(obj)
    elif isinstance(obj, list):
        return [fix_json_all_strings(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: fix_json_all_strings(v) for k, v in obj.items()}
    return obj


def main():
    print("=" * 60)
    print("Ultra-Fix v3: Byte-level UTF-8 Reconstruction")
    print("=" * 60)

    # Backup current file
    current_backup = filepath + '.backup_v3_src'
    shutil.copy2(filepath, current_backup)
    print(f"[1] Current file backed up to: {current_backup}")

    # Load from backup (original garbled version)
    with open(backup, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    print(f"[2] Loaded {len(nb['cells'])} cells from backup")

    # Apply fix to all cells
    print("\n[3] Applying byte-level UTF-8 fix...")
    report = []
    report.append("=" * 60)
    report.append("ENCODING FIX REPORT - Byte-Level UTF-8 Reconstruction")
    report.append("=" * 60)

    for cell_idx, cell in enumerate(nb['cells']):
        if 'source' not in cell:
            continue

        old = cell['source']

        # Apply fix recursively
        new = fix_json_all_strings(old)
        cell['source'] = new

        src = new if isinstance(new, str) else ''.join(new)
        cjk = sum(1 for c in src if 0x4e00 <= ord(c) <= 0x9fff)
        garbled = sum(1 for c in src if 0x80 <= ord(c) < 0x100)

        ct = cell.get('cell_type', '?')
        first = src.split('\n')[0][:50] if src else '(empty)'

        if garbled == 0 and cjk > 0:
            status = "[FIXED]"
        elif garbled > 0 and cjk > 0:
            status = "[PARTIAL g:" + str(garbled) + "]"
        elif cjk > 0:
            status = "[OK]"
        else:
            status = "[OK]"

        report.append("Cell " + str(cell_idx).rjust(2) + " | " + ct.rjust(8) + " | " + status.rjust(18) + " | cjk:" + str(cjk).rjust(5) + " | " + first)

    # Save
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    # Write report
    rep_path = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\encoding_fix_report.txt'
    with open(rep_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    # Verify
    print("\n[4] Verification:")
    with open(filepath, 'r', encoding='utf-8') as f:
        nb2 = json.load(f)

    total_cjk = 0
    total_garbled = 0
    for cell in nb2['cells']:
        src = ''.join(cell.get('source', ''))
        total_cjk += sum(1 for c in src if 0x4e00 <= ord(c) <= 0x9fff)
    total_garbled += sum(1 for c in src if 0x80 <= ord(c) < 0x100)

    print("  Total CJK chars: " + str(total_cjk))
    print("  Total garbled: " + str(total_garbled))

    src0 = ''.join(nb2['cells'][0]['source'])
    print("\n  Cell 0 preview:")
    print("  " + src0[:200])

    print("\n[5] Report: " + rep_path)
    print("[6] Saved: " + filepath)
    print("=" * 60)
    print("DONE!")


if __name__ == '__main__':
    main()
