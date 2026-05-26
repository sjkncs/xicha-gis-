import json

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

print(f"Notebook loaded: {len(nb['cells'])} cells")

# Fix cell 25 - the markdown cell with 6b content that has LaTeX escape issues
cell = nb['cells'][25]
src = ''.join(cell.get('source', []))
print(f"\nCell 25 source length: {len(src)}")

# The problem: LaTeX backslashes in markdown cells need proper JSON escaping
# e.g., \frac should be \\frac in JSON
# But we also need to be careful not to double-escape already-escaped things

# Replace single backslashes followed by letters (LaTeX commands) with double backslashes
# Only in the source strings, not already-escaped content
import re

def fix_latex_json(text):
    """Fix LaTeX commands in JSON strings by escaping backslashes."""
    # This handles the case where \cmd appears in a JSON string
    # Strategy: for each line in the source, escape backslashes
    lines = text.split('\n')
    fixed_lines = []
    for line in lines:
        # Only process lines that are JSON string values (start with spaces and quote)
        stripped = line.lstrip()
        if stripped.startswith('"') and stripped.endswith('",'):
            # This is a JSON string value line - escape backslashes properly
            # Count existing backslashes to not double-escape
            # Simple approach: replace \ with \\ only for known LaTeX patterns
            # The safest approach: just escape all backslashes in the string value part
            # Find the content between the quotes
            # JSON format: "    \"content\",  or  "    \"content\\n",
            # The line already has backslash escaping for JSON
            # We need to escape backslashes that are NOT already escaped
            
            # Current issue: the source has \frac which in JSON becomes \\frac 
            # but the \f part is still treated as an escape
            # Solution: escape ALL backslashes in the string value
            # But we need to find where the string value starts
            indent = len(line) - len(line.lstrip())
            content = line.strip()  # e.g. "    content\\n",
            
            # Find if this is a multi-line string continuation
            # These lines in nbformat have form: "    content",
            # We need to add a backslash before each LaTeX command
            # Simpler fix: replace all occurrences of \cmd with \\cmd
            latex_pattern = re.compile(r'(?<!\\)\\(sum|frac|left|right|bar|hat|sigma|alpha|beta|gamma|delta|infty|times|leq|geq|cdot|epsilon|sqrt|int|over|in|geq|leq|bar|hat|vec|hat|bar|dot|ddot|tilde|widehat|widetilde|overrightarrow|overleftarrow|overline|underline|overbrace|underbrace)(?![a-zA-Z])')
            # Just replace all backslashes followed by letters with double backslash
            # But we must not double-escape already escaped ones
            # The safest: replace single \ at the start of LaTeX commands
            # Known LaTeX commands used in the document:
            latex_cmds = ['sum', 'frac', 'left', 'right', 'bar', 'hat', 'sigma', 'alpha',
                         'beta', 'gamma', 'delta', 'infty', 'times', 'leq', 'geq',
                         'cdot', 'epsilon', 'sqrt', 'int', 'over', 'in', 'ge', 'le',
                         'bar', 'vec', 'dot', 'ddot', 'tilde', 'widehat', 'widetilde',
                         'overrightarrow', 'overleftarrow', 'overline', 'underline',
                         'overbrace', 'underbrace', 'partial', 'nabla', 'Omega', 'Phi',
                         'Psi', 'Lambda', 'Delta', 'Theta', 'Pi', 'Sigma', 'text', 'mathbf',
                         'emph', 'item', 'quad', 'qquad', 'space', 'qquad', 'quad',
                         'bmod', 'equiv', 'approx', 'propto', 'partial', 'forall', 'exists',
                         'infty', 'mathrm', 'mathbf', 'mathit', 'mathsf', 'mathrm', 'mathcal',
                         'mathbb', 'begin', 'end', 'label', 'ref', 'sqrt', 'cdot', 'times',
                         'div', 'pm', 'mp', 'oplus', 'otimes', 'leq', 'geq', 'neq', 'approx',
                         'equiv', 'sim', 'simeq', 'cong', 'propto', 'll', 'gg', 'prec', 'succ',
                         'subseteq', 'subset', 'supseteq', 'supset', 'in', 'notin', 'cup', 'cap',
                         'bigcup', 'bigcap', 'sum', 'prod', 'coprod', 'int', 'oint', 'iiint',
                         'iint', 'perp', 'parallel', 'angle', 'triangle', 'square', 'diamond']
            
            result = line
            for cmd in latex_cmds:
                # Replace \cmd (not preceded by backslash) with \\cmd
                result = re.sub(r'(?<!\\)\\(?=' + cmd + r'\b)', r'\\\\' + cmd, result)
            fixed_lines.append(result)
        else:
            fixed_lines.append(line)
    return '\n'.join(fixed_lines)

# Alternative approach: simply rebuild the source with proper escaping
# For cell 25, let's just replace the entire source with a clean version

# The cell has LaTeX formulas that are causing issues
# Let's fix by replacing backslash+letter with double-backslash+letter in source strings

def fix_source_safely(source_list):
    """Fix LaTeX escapes in a notebook cell source list."""
    fixed = []
    for line in source_list:
        # Check if this line is a string value in JSON (starts with whitespace + quote)
        stripped = line.strip()
        if not stripped.startswith('"'):
            fixed.append(line)
            continue
        
        # This is a JSON string value line
        # Find the string content - it's between the first " and the last " before ,
        # We need to escape all backslashes in the string value
        # The line format: "    content",
        # Find the opening quote (after indentation)
        indent_end = len(line) - len(line.lstrip())
        
        # Find where the string starts (first " after indent)
        quote_start = line.index('"') + 1
        # Find where string ends (last " before ,)
        if line.rstrip().endswith(','):
            quote_end = line.rindex('"')
        else:
            quote_end = len(line) - 1
        
        if quote_end <= quote_start:
            fixed.append(line)
            continue
        
        # Extract and fix the string content
        content = line[quote_start:quote_end]
        # Escape backslashes for JSON
        fixed_content = content.replace('\\', '\\\\')
        # Build the fixed line
        fixed_line = line[:quote_start] + fixed_content + line[quote_end:]
        fixed.append(fixed_line)
    
    return fixed

# Apply fix to cell 25
cell = nb['cells'][25]
old_source = cell['source']
print(f"Old source type: {type(old_source)}")
print(f"Old source length: {sum(len(s) for s in old_source)}")
print(f"First 200 chars: {repr(''.join(old_source)[:200])}")

# Actually the simplest fix: rebuild the source with proper escaping
# Get the raw text
raw_text = ''.join(old_source)

# Apply the safe fix
fixed_source = fix_source_safely(old_source)

# Check if it's now valid JSON
test_nb = nb.copy()
test_nb['cells'][25]['source'] = fixed_source

try:
    json.dumps(test_nb)
    print("Fixed JSON is valid!")
    nb['cells'][25]['source'] = fixed_source
except Exception as e:
    print(f"Still invalid: {e}")
    # Try even more conservative fix - just escape ALL backslashes in ALL source strings
    print("Trying conservative fix...")
    for ci, cell in enumerate(nb['cells']):
        if 'source' in cell:
            new_source = fix_source_safely(cell['source'])
            cell['source'] = new_source
    
    try:
        json.dumps(nb)
        print("Conservative fix worked!")
    except Exception as e2:
        print(f"Conservative fix failed: {e2}")
        # Last resort: escape ALL backslashes in source
        for ci, cell in enumerate(nb['cells']):
            if 'source' in cell and isinstance(cell['source'], list):
                new_source = []
                for line in cell['source']:
                    if isinstance(line, str) and '\\' in line:
                        # Escape all backslashes
                        new_source.append(line.replace('\\', '\\\\'))
                    else:
                        new_source.append(line)
                cell['source'] = new_source
        
        try:
            json.dumps(nb)
            print("Last resort fix worked!")
        except Exception as e3:
            print(f"All fixes failed: {e3}")
            sys.exit(1)

# Save
with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("Notebook saved successfully!")
