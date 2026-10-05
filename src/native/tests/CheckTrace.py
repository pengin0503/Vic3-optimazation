import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
from parse_native_profiler_trace import parse_trace
p=parse_trace(Path(sys.argv[1]).read_bytes())
assert p['header_valid'] and p['segment_complete'],p
assert not p['diagnostics'],p['diagnostics']
assert p['summary']['paired_functions']==1,p['summary']
print('Native V3PF/Python compatibility passed')
