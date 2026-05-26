import sys
lines = sys.stdin.read().strip().split('\n')
print('Total:', len(lines))
staged = [l for l in lines if l.startswith('A ') or l.startswith('M ')]
print('Staged (added/modified):', len(staged))
unstaged = [l for l in lines if l.startswith(' D')]
print('Deleted from index (old paths):', len(unstaged))
untracked = [l for l in lines if l.startswith('??')]
print('Untracked:', len(untracked))
if untracked:
    print('Sample untracked:')
    for l in untracked[:5]:
        print(' ', l)
if unstaged:
    print('Sample deleted (old paths - will be fixed on commit):')
    for l in unstaged[:3]:
        print(' ', l)
