"""
Delete original untracked files that have been copied to updates_20250605/.
This keeps the GitHub repo clean while the new files are in the updates folder.
"""
import os

WORKSPACE = r"e:\xicha gis 智能定位"
STATUS_FILE = r"C:\Users\Administrator\git_status_output.txt"
UPDATES_DIR = os.path.join(WORKSPACE, "updates_20250605")

# Files/dirs to keep (don't delete these)
KEEP = {
    "updates_20250605",
    "copy_updates.py",
    "clean_originals.py",
    "git_status_output.txt",
}

with open(STATUS_FILE, "r", encoding="utf-8") as f:
    lines = f.readlines()

deleted_files = 0
deleted_dirs = 0
errors = 0

# First pass: collect all untracked files
untracked_files = []
untracked_dirs = set()

for line in lines:
    line = line.strip()
    if not line:
        continue
    
    status = line[:2]
    filepath = line[3:].strip()
    
    # Remove surrounding quotes and decode
    if filepath.startswith('"') and filepath.endswith('"'):
        filepath = filepath[1:-1]
        filepath = filepath.encode('latin-1').decode('unicode_escape').encode('latin-1').decode('utf-8')
    
    # Only handle new/untracked files
    if status[0] == 'A' or status == '??':
        untracked_files.append(filepath)
        # Also collect parent directories for cleanup
        parts = filepath.replace('\\', '/').split('/')
        for i in range(1, len(parts)):
            untracked_dirs.add('/'.join(parts[:i]))

# Delete files first
for filepath in untracked_files:
    # Skip files inside updates_20250605
    if filepath.startswith("updates_20250605"):
        continue
    
    src = os.path.join(WORKSPACE, filepath)
    
    # Safety: only delete if it's inside workspace
    if not src.startswith(WORKSPACE):
        print(f"  SKIP (outside workspace): {filepath}")
        continue
    
    # Skip items in keep list
    basename = os.path.basename(filepath)
    if basename in KEEP:
        continue
    
    if os.path.isfile(src):
        try:
            os.remove(src)
            deleted_files += 1
            if deleted_files % 200 == 0:
                print(f"  Deleted {deleted_files} files...")
        except Exception as e:
            errors += 1
            print(f"  ERROR deleting {filepath}: {e}")
    elif os.path.isdir(src):
        # Will handle dirs later
        pass

print(f"\nDeleted {deleted_files} files, {errors} errors.")

# Now try to clean up empty directories (bottom-up by depth)
sorted_dirs = sorted(untracked_dirs, key=lambda x: -x.count('/'))
for dirpath in sorted_dirs:
    full_dir = os.path.join(WORKSPACE, dirpath)
    if os.path.isdir(full_dir):
        try:
            if not os.listdir(full_dir):
                os.rmdir(full_dir)
                deleted_dirs += 1
        except Exception:
            pass

print(f"Removed {deleted_dirs} empty directories.")
print("Done cleaning originals!")
