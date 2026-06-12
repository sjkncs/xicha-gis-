"""
Copy all modified and untracked files into updates_20250605/ folder,
preserving directory structure.
"""
import os
import shutil
import re

WORKSPACE = r"e:\xicha gis 智能定位"
STATUS_FILE = r"C:\Users\Administrator\git_status_output.txt"
UPDATES_DIR = os.path.join(WORKSPACE, "updates_20250605")

# Parse git status --porcelain output
# Format: XY filename  (X=index status, Y=worktree status)
# M = modified, A = added, ? = untracked, D = deleted
modified_files = []  # tracked files that were modified
new_files = []       # new untracked files

with open(STATUS_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        
        # Git porcelain format: "XY filename" where XY is 2-char status
        # For renamed: "R  old\0new" - but we use -z for that, not our case
        status = line[:2]
        filepath = line[3:].strip()
        
        # Remove surrounding quotes if present (git adds quotes for paths with special chars)
        if filepath.startswith('"') and filepath.endswith('"'):
            filepath = filepath[1:-1]
            # Unescape octal sequences in quoted strings
            # Git uses octal escapes like \345\210\206 for UTF-8 bytes
            filepath = filepath.encode('latin-1').decode('unicode_escape').encode('latin-1').decode('utf-8')
        
        x_status = status[0]  # index status
        y_status = status[1]  # worktree status
        
        if x_status == 'M' or y_status == 'M':
            # Modified tracked file
            if x_status != 'D' and y_status != 'D':
                modified_files.append(filepath)
        elif x_status == 'A':
            # New file (untracked, staged as added)
            new_files.append(filepath)
        elif status == '??':
            # Untracked
            new_files.append(filepath)

print(f"Found {len(modified_files)} modified files")
print(f"Found {len(new_files)} new/untracked files")
print(f"Total: {len(modified_files) + len(new_files)} files to copy")

# Create updates directory
os.makedirs(UPDATES_DIR, exist_ok=True)

# Copy files
copied = 0
errors = 0

all_files = modified_files + new_files

for filepath in all_files:
    src = os.path.join(WORKSPACE, filepath)
    dst = os.path.join(UPDATES_DIR, filepath)
    
    # Skip directories (they appear as entries in porcelain)
    if not os.path.exists(src):
        # Might be a directory reference, skip
        continue
    if os.path.isdir(src):
        continue
    
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
        if copied % 100 == 0:
            print(f"  Copied {copied} files...")
    except Exception as e:
        errors += 1
        print(f"  ERROR copying {filepath}: {e}")

print(f"\nDone! Copied {copied} files, {errors} errors.")
print(f"Files are in: {UPDATES_DIR}")
