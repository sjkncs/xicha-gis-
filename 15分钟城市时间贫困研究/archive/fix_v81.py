NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json, traceback
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Custom JSON decoder to find exact error
class PreciseDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def raw_decode(self, s, idx=0):
        try:
            obj, end_index = super().raw_decode(s, idx)
            return obj, end_index
        except json.JSONDecodeError as e:
            # Print detailed error info
            print("=== JSON ERROR DETAILS ===")
            print("Error: %s" % e.msg)
            print("Line: %d, Col: %d, Pos: %d" % (e.lineno, e.colno, e.pos))
            
            # Show context
            lines = s.split('\n')
            print("\nError line %d:" % e.lineno)
            line = lines[e.lineno-1]
            print("  %s" % line)
            print("  %s^" % (' ' * (e.colno-1)))
            
            # Show the exact character
            if e.colno <= len(line):
                ch = line[e.colno-1]
                print("\nCharacter at error: 0x%04X = '%s'" % (ord(ch), repr(ch)))
            
            # Try to find the actual problem by looking backwards
            print("\n=== Looking backwards from error ===")
            pos = e.pos
            
            # Show 100 chars before error
            start = max(0, pos-100)
            print("100 chars before error:")
            print("  %s" % repr(s[start:pos]))
            
            # Show the error position and after
            print("\nError position and after:")
            print("  %s" % repr(s[pos:pos+50]))
            
            raise

try:
    nb = json.loads(content, cls=PreciseDecoder)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nFailed: %s" % e.msg)
except Exception as e:
    print("\nException: %s" % e)
    traceback.print_exc()
