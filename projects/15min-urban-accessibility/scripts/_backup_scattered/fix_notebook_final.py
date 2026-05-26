"""Ultra-thorough fix using raw byte reconstruction"""
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'
backup = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb.backup_before_encoding_fix'
outpath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\encoding_fix_report.txt'


def latin1_to_utf8(text):
    """
    Convert a string where latin-1 characters (U+0080-U+00FF) represent
    the raw bytes of a double-encoded UTF-8 string back to proper UTF-8 text.
    
    For each char c in text:
    - If ord(c) < 0x80: keep as-is (ASCII)
    - If 0x80 <= ord(c) < 0x100: it's a raw byte from the original UTF-8
      string, keep it
    - Then at the end, decode the accumulated bytes as UTF-8
    
    But we can't accumulate bytes easily in Python strings.
    Instead, encode to latin-1 bytes, then decode as UTF-8.
    For chars not in latin-1 range (like U+00E6), we need a workaround.
    """
    if not text:
        return text
    
    # Strategy: rebuild byte sequence
    # For each char in the string:
    #   - ASCII chars (0x00-0x7F): 1 byte
    #   - latin-1 chars (0x80-0xFF): 1 byte representing a UTF-8 byte
    # Collect all bytes, then decode as UTF-8
    
    # But latin-1 chars like U+00E6 ARE in range 0x80-0xFF, so they work
    # The issue might be that ord(c) > 0xFF is not possible since chars are
    # from the latin-1 range in the garbled string
    
    # Actually let's test
    try:
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        # Partial fix: only fix chars that CAN be encoded
        try:
            bytes_out = []
            for c in text:
                code = ord(c)
                if code < 0x80:
                    bytes_out.append(code)
                elif code < 0x100:
                    bytes_out.append(code)
                # else: keep as-is (already Unicode, not a raw byte)
            result = bytes(bytes_out).decode('utf-8')
            return result
        except:
            return text


def fix_json_strings_recursive(obj):
    """
    Recursively fix all string values in a JSON structure.
    """
    if isinstance(obj, str):
        return latin1_to_utf8(obj)
    elif isinstance(obj, list):
        return [fix_json_strings_recursive(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: fix_json_strings_recursive(v) for k, v in obj.items()}
    else:
        return obj


def analyze_garbled_chars(text):
    """Analyze what type of garbled chars we have"""
    if not text:
        return {}
    latin1_chars = [c for c in text if 0x80 <= ord(c) < 0x100]
    other_high = [c for c in text if ord(c) >= 0x100]
    cjk = [c for c in text if 0x4e00 <= ord(c) <= 0x9fff]
    return {
        'latin1_chars': latin1_chars[:10],
        'latin1_count': len(latin1_chars),
        'other_high_count': len(other_high),
        'cjk_count': len(cjk),
    }


def main():
    print("=" * 60)
    print("Ultra-Thorough Encoding Fix")
    print("=" * 60)
    
    # Load backup (original garbled version)
    with open(backup, 'rb') as f:
        raw = f.read()
    
    print(f"Backup size: {len(raw):,} bytes")
    
    # Parse as UTF-8 JSON
    text = raw.decode('utf-8')
    nb = json.loads(text)
    print(f"JSON valid, {len(nb['cells'])} cells")
    
    # Show initial state
    cell0 = nb['cells'][0]
    src0 = ''.join(cell0['source'])
    print(f"\nInitial cell 0: has CJK = {any(0x4e00 <= ord(c) <= 0x9fff for c in src0)}")
    print(f"Sample: {repr(src0[:50])}")
    analysis = analyze_garbled_chars(src0)
    print(f"Analysis: {analysis}")
    
    # Test the fix on cell 0
    print(f"\nTesting latin1_to_utf8 on cell 0...")
    fixed0 = latin1_to_utf8(src0[:200])
    print(f"Result has CJK = {any(0x4e00 <= ord(c) <= 0x9fff for c in fixed0)}")
    print(f"Result: {fixed0[:80]}")
    
    # Apply fix to ALL cells
    print(f"\nApplying fix to all cells...")
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("FIXED NOTEBOOK - ENCODING REPORT")
    report_lines.append("=" * 60)
    
    total_fixed = 0
    
    for cell_idx, cell in enumerate(nb['cells']):
        if 'source' not in cell:
            continue
        
        old_source = cell['source']
        new_source = fix_json_strings_recursive(old_source)
        cell['source'] = new_source
        
        src_full = ''.join(new_source) if isinstance(new_source, list) else new_source
        
        cjk = sum(1 for c in src_full if 0x4e00 <= ord(c) <= 0x9fff)
        garbled = sum(1 for c in src_full if 0x80 <= ord(c) < 0x100)
        
        ct = cell.get('cell_type', '?')
        first = src_full.split('\n')[0][:50] if src_full else '(empty)'
        
        if garbled == 0 and cjk > 0:
            status = "FIXED"
        elif garbled > 0:
            status = f"PARTIAL({garbled})"
        else:
            status = "OK"
        
        report_lines.append(f"Cell {cell_idx:2d} | {ct:8s} | {status:15s} | cjk:{cjk:5d} | {first}")
        
        if garbled > 0:
            total_fixed += 1
    
    # Save fixed notebook
    print(f"\nSaving fixed notebook...")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print(f"Saved: {filepath}")
    
    # Write report
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    print(f"Report: {outpath}")
    
    # Verify
    print(f"\nVerification:")
    with open(filepath, 'r', encoding='utf-8') as f:
        nb2 = json.load(f)
    
    total_cjk = 0
    total_garbled = 0
    for cell in nb2['cells']:
        src = ''.join(cell.get('source', ['']))
        total_cjk += sum(1 for c in src if 0x4e00 <= ord(c) <= 0x9fff)
        total_garbled += sum(1 for c in src if 0x80 <= ord(c) < 0x100)
    
    print(f"  Total CJK chars: {total_cjk}")
    print(f"  Total garbled: {total_garbled}")
    
    src0_new = ''.join(nb2['cells'][0]['source'])
    print(f"\n  Cell 0 (first 150 chars):")
    print(f"  {src0_new[:150]}")
    
    print("\n" + "=" * 60)
    print(f"DONE! {total_fixed} cells may need manual review.")
    print("=" * 60)


if __name__ == '__main__':
    main()
