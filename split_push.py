"""Split the large commit into smaller batches and push each.

Uses --pathspec-from-file to avoid Windows command-line length limits.
"""
import subprocess
import os
import sys

os.chdir(r"e:\xicha gis 智能定位")
os.environ["GIT_TERMINAL_PROMPT"] = "0"

ENC = {"encoding": "utf-8", "errors": "replace"}

# ── Get remaining files not yet on origin/master ───────────────
result = subprocess.run(
    ["git", "diff", "--name-only", "origin/master..saved-batch-commit", "--", "updates_20250605/"],
    capture_output=True, text=True, **ENC
)
files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
print(f"Remaining files to push: {len(files)}")

if len(files) == 0:
    print("Nothing to push!")
    subprocess.run(["git", "tag", "-d", "saved-batch-commit"], check=True)
    sys.exit(0)

BATCH_SIZE = 200
total_batches = (len(files) + BATCH_SIZE - 1) // BATCH_SIZE

for i in range(0, len(files), BATCH_SIZE):
    batch = files[i:i+BATCH_SIZE]
    batch_num = i // BATCH_SIZE + 1
    print(f"\n{'='*60}")
    print(f"Batch {batch_num}/{total_batches}: {len(batch)} files")
    print(f"{'='*60}")

    # Sync with remote (fetch only, no reset to avoid interactive prompts)
    if batch_num > 1:
        print("Syncing with remote...")
        subprocess.run(["git", "fetch", "origin", "master"], check=True,
                       capture_output=True, **ENC)

    # Write file list to temp file
    list_file = "batch_files.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        f.write("\n".join(batch))

    # Restore files from the saved commit into working tree ONLY
    # (NOT --staged, so that git add runs LFS clean filter below)
    print("Restoring files from saved commit...")
    subprocess.run([
        "git", "restore",
        "--source=saved-batch-commit",
        "--pathspec-from-file=" + list_file,
        "--worktree"
    ], check=True)

    # Stage files via git add (triggers LFS clean filter to convert large
    # binaries to LFS pointers, avoiding GitHub 100 MB limit rejection)
    print("Staging files (LFS clean filter will convert large binaries)...")
    subprocess.run([
        "git", "add",
        "--pathspec-from-file=" + list_file
    ], check=True)

    os.remove(list_file)

    # Commit
    msg = f"updates_20250605 batch {batch_num}/{total_batches}"
    subprocess.run(["git", "commit", "-m", msg], check=True)

    # Push
    print(f"Pushing batch {batch_num}...")
    result = subprocess.run(
        ["git", "push", "origin", "master"],
        capture_output=True, text=True, **ENC
    )
    if result.returncode != 0:
        print(f"ERROR: Push failed!")
        print(f"STDERR: {result.stderr}")
        print(f"STDOUT: {result.stdout}")
        sys.exit(1)
    print(f"Batch {batch_num} pushed successfully!")

# ── Cleanup ────────────────────────────────────────────────────
subprocess.run(["git", "tag", "-d", "saved-batch-commit"], check=True)
print("\n" + "="*60)
print("ALL BATCHES PUSHED SUCCESSFULLY!")
print("="*60)
