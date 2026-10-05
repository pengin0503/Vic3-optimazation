import argparse,sys,json,hashlib,struct,collections
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'tools'))
ap=argparse.ArgumentParser();ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();OUT=args.output
from analyze_vic3 import read_input,PE,Error
from map_ticktask_rtti import runtime_functions
from runtime_function_groups import RuntimeFunctionIndex,backed_bytes
from map_hotspot_calls import build_graph,verify_hash
import capstone as cs
from capstone import x86_const as x86

EXPECTED='9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'
b,logical=read_input(args.archive,'victoria3.exe');verify_hash(b,EXPECTED)
pe=PE(b);index=RuntimeFunctionIndex(b,pe,runtime_functions(b,pe))
imports={};r,_=pe.directory(1);off=pe.rva(r)
for i in range(4096):
    oft,stamp,forward,name,ft=struct.unpack_from('<5I',b,off+i*20)
    if not any((oft,stamp,forward,name,ft)):break
    dll=pe.cstr(name);to=pe.rva(oft or ft)
    for j in range(200000):
        v=struct.unpack_from('<Q',b,to+j*8)[0]
        if not v:break
        symbol=f'ordinal:{v&0xffff}' if v>>63 else pe.cstr(v+2)
        imports[ft+j*8]={'dll':dll,'symbol':symbol,'iat_rva':hex(ft+j*8)}
seeds={'dispatcher_caller_a':0x7e1820,'dispatcher_caller_b':0x7e20c0,
       'range_runner':0x7dbaa0,'heuristic':0x7db150}
g=build_graph(b,pe,index,seeds,max_depth=3,max_functions=200,max_function_bytes=65536)
decoder=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_64);decoder.detail=True
nodes=[];api_sites=[];atomic_sites=[];backedges=[];leaf_refs=[]
for n in g['nodes']:
    ins=[]
    for span in n['ranges']:
        lo=int(span['begin_rva'],16)
        ins+=list(decoder.disasm(backed_bytes(b,pe,lo,span['size_bytes']),lo))
    loops=[];apis=[];atomics=[]
    for i in ins:
        item={'instruction_rva':hex(i.address),'bytes':i.bytes.hex(),'mnemonic':i.mnemonic,'operand':i.op_str,'group_entry_rva':n['entry_rva'],'fully_decoded_group':n['fully_decoded']}
        if i.mnemonic.startswith('lock ') or i.mnemonic in ('mfence','sfence','lfence','pause','cmpxchg','cmpxchg8b','cmpxchg16b','xadd'):
            atomic_sites.append(item);atomics.append(item)
        if i.mnemonic.startswith('j') and i.operands and i.operands[0].type==x86.X86_OP_IMM and i.operands[0].imm<i.address:
            target=i.operands[0].imm
            if any(int(s['begin_rva'],16)<=target<int(s['end_rva'],16) for s in n['ranges']):
                item={**item,'target_rva':hex(target),'span_bytes':i.address-target};loops.append(item);backedges.append(item)
        if i.mnemonic in ('call','jmp') and i.operands:
            op=i.operands[0]
            if op.type==x86.X86_OP_MEM and op.mem.base==x86.X86_REG_RIP:
                slot=i.address+i.size+op.mem.disp
                if slot in imports:
                    item={**item,'import':imports[slot]};apis.append(item);api_sites.append(item)
    nodes.append({'entry_rva':n['entry_rva'],'depth':n['depth'],'ranges':n['ranges'],'fully_decoded':n['fully_decoded'],
                 'direct_edges':n['direct_edges'],'code_address_references':n['code_address_references'],
                 'vtable_address_references':n['vtable_address_references'],'indirect_sites':n['indirect_sites'],'api_sites':apis,
                 'atomic_or_fence_sites':atomics,'backward_branch_candidates':loops,'instruction_count':len(ins)})

# Search only encoded RIP-relative calls/jumps to imported synchronization IAT slots,
# then confirm instruction boundary by decoding the unwind group from its range starts.
sync_terms=('CriticalSection','SRWLock','ConditionVariable','WaitFor','WaitOnAddress','WakeByAddress','ReleaseSemaphore','SetEvent','ResetEvent')
sync_imports={r:v for r,v in imports.items() if any(t in v['symbol'] for t in sync_terms)}
confirmed=[];unresolved=[];rejected=0;cache={}
for sec in pe.sections:
    if not int(sec['characteristics'],16)&0x20000000:continue
    raw=b[sec['raw_pointer']:sec['raw_pointer']+sec['raw_size']]
    for pattern in (b'\xff\x15',b'\xff\x25'):
        pos=0
        while True:
            k=raw.find(pattern,pos)
            if k<0:break
            pos=k+1
            if k+6>len(raw):continue
            site=sec['virtual_address']+k;slot=site+6+struct.unpack_from('<i',raw,k+2)[0]
            if slot not in sync_imports:continue
            group=index.group_for(site)
            if group is None or group['status']!='resolved':
                unresolved.append({'instruction_rva':hex(site),'import':sync_imports[slot],'reason':'no_resolved_unwind'});continue
            root=group['root'][0]
            if root not in cache:
                decoded={};complete=True
                for lo,hi in group['ranges']:
                    groupraw=backed_bytes(b,pe,lo,hi-lo);ilist=list(decoder.disasm(groupraw,lo))
                    complete&=sum(i.size for i in ilist)==len(groupraw)
                    decoded.update({i.address:i for i in ilist})
                cache[root]=(decoded,complete)
            decoded,complete=cache[root];i=decoded.get(site)
            if i is None:
                # A REX or other instruction prefix can precede the FF opcode.
                # Resolve only against an already decoded instruction, never
                # restart a decoder at this raw byte match.
                for prefix in range(1,10):
                    candidate=decoded.get(site-prefix)
                    if candidate is not None and candidate.address+candidate.size==site+6 and candidate.bytes[-6:-4]==pattern:
                        i=candidate;break
            if i is None or i.mnemonic not in ('call','jmp') or len(i.operands)!=1:
                rejected+=1;continue
            op=i.operands[0]
            if op.type!=x86.X86_OP_MEM or op.mem.base!=x86.X86_REG_RIP or i.address+i.size+op.mem.disp!=slot:
                rejected+=1;continue
            row={'instruction_rva':hex(i.address),'opcode_rva':hex(site),'group_root_rva':hex(root),'mnemonic':i.mnemonic,'bytes':i.bytes.hex(),'import':sync_imports[slot],
                 'fully_decoded_group':complete,'in_selected_graph':any(int(n['entry_rva'],16)==root for n in g['nodes'])}
            if complete:confirmed.append(row)
            else:unresolved.append({**row,'reason':'partial_group_decode'})

OUT.mkdir(parents=True,exist_ok=True)
doc={'format_version':1,'executable_sha256':EXPECTED,'archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
     'capstone_version':cs.__version__,'seeds':g['seeds'],'budgets':g['budgets'],
     'graph_edge_kinds':['decoded direct call/tail-jump','code-address reference candidate','referenced-vtable slot candidate'],
     'nodes':nodes,'not_expanded':g['not_expanded'],
     'selected_graph_import_sites':api_sites,'selected_graph_atomic_sites':atomic_sites,
     'synchronization_iat_scan':{'scope':'file-backed executable sections; FF15/FF25 candidates confirmed at unwind-start decode boundaries; normal imports only',
        'imports':list(sync_imports.values()),'confirmed_sites':confirmed,'unresolved_sites':unresolved,'rejected_candidates':rejected},
     'limitations':['linear decode is not CFG/path reachability','direct/static path not runtime use or task dependency','API names identify synchronization operations but not contention or lock owner','atomic op or backward branch does not establish hotness','IAT-only scan misses dynamically resolved APIs and register-indirect wrappers','partial group observations remain unresolved']}
blob=(json.dumps(doc,indent=2,sort_keys=True)+'\n').encode();(OUT/'scheduler-synchronization-evidence.json').write_bytes(blob)
stats={'groups':len(nodes),'fully_decoded_groups':sum(n['fully_decoded'] for n in nodes),'selected_api_counts':dict(collections.Counter(x['import']['symbol'] for x in api_sites)),
       'selected_atomic_count':len(atomic_sites),'backward_branches':len(backedges),'sync_sites_total':len(confirmed),'sync_sites_in_graph':sum(x['in_selected_graph'] for x in confirmed),
       'sync_api_counts':dict(collections.Counter(x['import']['symbol'] for x in confirmed)),
       'artifact_sha256':hashlib.sha256(blob).hexdigest()}
(OUT/'probe-summary.json').write_text(json.dumps(stats,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(stats,indent=2))
