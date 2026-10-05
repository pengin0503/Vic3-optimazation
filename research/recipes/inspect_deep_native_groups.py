"""Bounded read-only inspection of specified unwind groups; no executable output."""
import argparse, hashlib, json, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'tools'))
import capstone
from analyze_vic3 import PE,read_input
from map_ticktask_rtti import runtime_functions
from map_hotspot_calls import analyze_function,verify_hash
from runtime_function_groups import RuntimeFunctionIndex,backed_bytes

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rva',action='append',required=True);ap.add_argument('--name',required=True);ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    archive=a.archive;b,member=read_input(archive,'victoria3.exe')
    sha=verify_hash(b,'9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54')
    pe=PE(b);idx=RuntimeFunctionIndex(b,pe,runtime_functions(b,pe));md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);md.detail=True
    nodes=[];listing=[];excluded=[]
    for r in a.rva:
        entry=int(r,16);group=idx.group_for(entry)
        if group is None or group['status']!='resolved' or group['size_bytes']>8192:
            excluded.append({'rva':hex(entry),'reason':'no resolved metadata or 8192 byte limit','metadata':group});continue
        node=analyze_function(b,pe,idx,entry)
        if not node['fully_decoded']:raise RuntimeError(f'partial decode {r}')
        node['instructions']=[];node['backward_branches']=[]
        listing.append(f'\nENTRY {r} ({node["decoded_bytes"]} bytes)')
        for begin,end in idx.group_for(entry)['ranges']:
            for ins in md.disasm(backed_bytes(b,pe,begin,end-begin),begin):
                row={'rva':hex(ins.address),'bytes':ins.bytes.hex(),'mnemonic':ins.mnemonic,'operand':ins.op_str}
                node['instructions'].append(row);listing.append(f'{ins.address:08x} {ins.bytes.hex():24} {ins.mnemonic:8} {ins.op_str}')
                if ins.mnemonic.startswith('j') and ins.operands[0].type==capstone.x86_const.X86_OP_IMM and ins.operands[0].imm<ins.address:
                    node['backward_branches'].append({'site_rva':hex(ins.address),'target_rva':hex(ins.operands[0].imm),'mnemonic':ins.mnemonic})
        nodes.append(node)
    result={'format_version':1,'archive':str(archive),'archive_size_bytes':archive.stat().st_size,'executable_member':member,'executable_sha256':sha,'capstone_version':capstone.__version__,'selected_groups':nodes,'excluded':excluded,'warning':'Linear static decode only. Backward branch is not proof of executed loop, hotness, semantic role or complete function.'}
    (a.output/(a.name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (a.output/(a.name+'.txt')).write_text('\n'.join(listing)+'\n',encoding='utf8')
    print(json.dumps({'nodes':[{'rva':n['entry_rva'],'bytes':n['decoded_bytes'],'calls':len(n['direct_edges']),'indirect':len(n['indirect_sites']),'backward':len(n['backward_branches'])} for n in nodes],'excluded':excluded},indent=2))
if __name__=='__main__':main()
