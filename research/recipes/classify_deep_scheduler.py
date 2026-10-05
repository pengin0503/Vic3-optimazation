import argparse,json,sys,hashlib,collections
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'tools'))
ap=argparse.ArgumentParser();ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();OUT=args.output
from analyze_vic3 import read_input,PE
from map_ticktask_rtti import runtime_functions
from runtime_function_groups import RuntimeFunctionIndex,backed_bytes
from map_hotspot_calls import analyze_function,verify_hash
import capstone as cs
from capstone import x86_const as x86
src=json.loads((OUT/'scheduler-synchronization-evidence.json').read_text())
b,_=read_input(args.archive,'victoria3.exe');verify_hash(b,src['executable_sha256'])
pe=PE(b);index=RuntimeFunctionIndex(b,pe,runtime_functions(b,pe));md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_64);md.detail=True
windows={0x7db150:[(0x7db18b,0x7db1be),(0x7db98b,0x7db9fc)],0x7e20c0:[(0x7e21f1,0x7e222b),(0x7e2bb6,0x7e2bc8),(0x7e2cd6,0x7e2d07)],
 0x4234408:[(0x4234408,0x4234483)],0x423439c:[(0x423439c,0x4234405)],
 0x7e1910:[(0x7e1cc0,0x7e1d0c),(0x7e1d20,0x7e1d56),(0x7e1d96,0x7e1dca),(0x7e1eb0,0x7e1ec0),(0x7e1fc6,0x7e1fd6)],
 0x7e56b0:[(0x7e5885,0x7e58ae)],0x7e5950:[(0x7e5b23,0x7e5b4c)]}
selected={};strings=[]
for r,ws in windows.items():
    region=analyze_function(b,pe,index,r)
    if not region['fully_decoded']:raise RuntimeError(f'partial selected group {r:x}')
    instructions=[]
    for span in region['ranges']:
        lo=int(span['begin_rva'],16)
        for i in md.disasm(backed_bytes(b,pe,lo,span['size_bytes']),lo):
            if any(a<=i.address<c for a,c in ws):instructions.append({'rva':hex(i.address),'bytes':i.bytes.hex(),'mnemonic':i.mnemonic,'operand':i.op_str})
            if i.mnemonic=='lea':
                for op in i.operands:
                    if op.type==x86.X86_OP_MEM and op.mem.base==x86.X86_REG_RIP:
                        target=i.address+i.size+op.mem.disp
                        try:raw=backed_bytes(b,pe,target,120).split(b'\0')[0]
                        except Exception:continue
                        if len(raw)>3 and all(32<=v<127 for v in raw):strings.append({'group_rva':hex(r),'instruction_rva':hex(i.address),'string_rva':hex(target),'value':raw.decode()})
    selected[hex(r)]={'region':region,'instruction_windows':instructions}
def step(source,site,target):return {'source_group_rva':hex(source),'instruction_rva':hex(site),'target_rva':hex(target),'edge_type':'decoded_direct_call'}
paths=[{'id':'tls_guard_caller','steps':[step(0x7e20c0,0x7e2cdd,0x4234408)],'classification':'initialization_guard_candidate'},
       {'id':'tls_guard_heuristic','steps':[step(0x7db150,0x7db992,0x4234408)],'classification':'initialization_guard_candidate'},
       {'id':'telemetry_lock_a','steps':[step(0x7e20c0,0x7e2bc3,0x7e1910),step(0x7e1910,0x7e1eb8,0x7e56b0)],'classification':'formatted_tick_statistics_update_candidate'},
       {'id':'telemetry_lock_b','steps':[step(0x7e20c0,0x7e2bc3,0x7e1910),step(0x7e1910,0x7e1fce,0x7e5950)],'classification':'formatted_tick_statistics_update_candidate'}]
for p in paths:
    for s in p['steps']:
        edges=selected[s['source_group_rva']]['region']['direct_edges']
        assert any(e['kind']=='call' and e['instruction_rva']==s['instruction_rva'] and e['target_rva']==s['target_rva'] for e in edges)
syn=src['synchronization_iat_scan'];symbols=collections.Counter(x['import']['symbol'] for x in syn['confirmed_sites'])
doc={'format_version':1,'executable_sha256':src['executable_sha256'],'archive_sha256':src['archive_sha256'],'capstone_version':cs.__version__,
 'selected_regions':selected,'string_witnesses':strings,'direct_path_witnesses':paths,
 'global_iat_scan_summary':{'scope':syn['scope'],'confirmed_static_sites':len(syn['confirmed_sites']),'unresolved_sites':len(syn['unresolved_sites']),
    'rejected_raw_matches':syn['rejected_candidates'],'counts_by_api':dict(symbols),'all_confirmed_group_bytes_are_decoded':True,
    'coverage':'normal-import IAT RIP-relative encoded FF15/FF25 including verified prefixes; dynamic imports and other dispatch forms excluded'},
 'bounded_graph_summary':{'seeds':src['seeds'],'budgets':src['budgets'],'edge_kinds':src['graph_edge_kinds'],
    'candidate_edges_are_not_runtime_calls':True,'groups':len(src['nodes']),'fully_decoded_groups':sum(n['fully_decoded'] for n in src['nodes']),
    'partial_groups':[n['entry_rva'] for n in src['nodes'] if not n['fully_decoded']],'function_budget_reached':True,'full_graph_not_committed':True},
 'probe_contracts':[
   {'id':'initialization_guard','target_groups':['0x4234408','0x423439c'],'needed':['call count during warm-up vs measurement','caller stack','blocked duration'],'do_not_infer':'not confirmed worker-completion or game-state lock'},
   {'id':'telemetry_updates','target_groups':['0x7e1910','0x7e56b0','0x7e5950'],'needed':['runtime reachability with built-in timing on/off','CPU and blocked duration per caller','original callable return/data unchanged'],'do_not_infer':'do not count statistic output time as task computation or remove locks'}],
 'source_context':[{'url':'https://learn.microsoft.com/en-us/cpp/build/reference/zc-threadsafeinit-thread-safe-local-static-initialization?view=msvc-170','use':'TLS optimization after local-static initialization; does not resolve exact symbol identity'},
   {'url':'https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-sleepconditionvariablesrw','use':'API sleep releases/reacquires lock; spurious wake needs predicate recheck'}],
 'warning':'Exact-build static operations confirmed; source symbol names, branch runtime reachability, lock ownership, contention and performance benefit remain unverified.'}
out=OUT;blob=(json.dumps(doc,sort_keys=True,indent=2)+'\n').encode()
(out/'scheduler-classified-evidence.json').write_bytes(blob)
print('Selected',len(selected),'fully-decoded groups;',len(paths),'direct path witnesses; bytes',len(blob),'hash',hashlib.sha256(blob).hexdigest())
