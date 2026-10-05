#!/usr/bin/env python3
"""Exact-build, bounded static evidence from TickTask.Graph/List. No graph guesses."""
from collections import deque
import hashlib
from pathlib import Path

from analyze_vic3 import Error, PE, read_input
from map_hotspot_calls import analyze_function, verify_hash
from map_ticktask_rtti import runtime_functions
from runtime_function_groups import RuntimeFunctionIndex, backed_bytes

EXPECTED_SHA256 = '9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'
WARNING = 'Static instruction/reference evidence only; no runtime reachability, dependency semantics, critical path, lock causality or performance benefit is proven.'


def require_capstone():
    try:
        import capstone
        return capstone
    except ImportError as exc:
        raise Error('install optional dependency: python -m pip install -r tools/requirements-callgraph.txt') from exc


def deduplicate_edges(edges):
    grouped = {}
    for edge in edges:
        key = (edge['kind'], edge['target_rva'])
        grouped.setdefault(key, set()).add(edge['instruction_rva'])
    return [{'kind': k, 'target_rva': r, 'evidence_rvas': sorted(s, key=lambda x:int(x,16))}
            for (k,r),s in sorted(grouped.items())]


def analyze_dependency_evidence(binary: bytes, logical_path: str, rtti: dict, *,
                                graph_root_rva=0x28cf820, list_root_rva=0x28cf5b0,
                                max_depth=3, max_functions=256) -> dict:
    actual = verify_hash(binary, EXPECTED_SHA256)
    if rtti.get('executable_sha256') != actual:
        raise Error('RTTI executable hash mismatch')
    if not 0 <= max_depth <= 3 or not 1 <= max_functions <= 256:
        raise Error('invalid budget: depth 0..3, functions 1..256')
    cs = require_capstone()
    from capstone import x86_const as x86
    pe = PE(binary)
    index = RuntimeFunctionIndex(binary, pe, runtime_functions(binary, pe))
    decoder = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_64)
    decoder.detail = True
    identities = {}
    unresolved = []
    for c in sorted(rtti.get('classes', []), key=lambda x:x['name']):
        if c.get('vtable_candidate_count') != 1:
            unresolved.append({'task':c['name'], 'reason':'ambiguous_ticktask_identity'})
            continue
        for field in ('vtable_rva','type_descriptor_rva'):
            if c.get(field):
                identities.setdefault(int(c[field],16), []).append((c['name'],field))
    for name in sorted(rtti.get('unmapped_ticktask_names', [])):
        unresolved.append({'task':name, 'reason':'unmapped_ticktask_identity'})
    roots = {'TickTask.Graph':hex(graph_root_rva), 'TickTask.List':hex(list_root_rva)}
    pending = deque((r,0) for r in sorted({graph_root_rva,list_root_rva}))
    visited, nodes, references = set(), [], []
    while pending:
        entry, depth = pending.popleft()
        group = index.group_for(entry)
        reason = ('no_unwind_metadata' if group is None else group.get('error'))
        if reason:
            unresolved.append({'rva':hex(entry), 'reason':reason})
            continue
        root = group['root'][0]
        if root in visited:
            continue
        if depth > max_depth or len(nodes) >= max_functions or group['size_bytes'] > 65536:
            reason = 'depth_budget' if depth > max_depth else 'function_budget' if len(nodes) >= max_functions else 'byte_budget'
            unresolved.append({'rva':hex(entry),'reason':reason})
            continue
        visited.add(root)
        node = analyze_function(binary, pe, index, root)
        node['depth'] = depth
        node['rip_relative_data_references'] = []
        for begin,end in group['ranges']:
            for ins in decoder.disasm(backed_bytes(binary,pe,begin,end-begin),begin):
                for op in ins.operands:
                    if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP:
                        target = ins.address + ins.size + op.mem.disp
                        record = {'instruction_rva':hex(ins.address),'target_rva':hex(target),'kind':'rip_relative_reference'}
                        node['rip_relative_data_references'].append(record)
                        for name,field in identities.get(target, []):
                            references.append({**record,'task':name,'identity_kind':field,'confidence':'confirmed-static'})
        node['direct_edges'] = deduplicate_edges(node['direct_edges'])
        if not node['fully_decoded']:
            unresolved.append({'rva':hex(root),'reason':'incomplete_decode'})
        for site in node['indirect_sites']:
            unresolved.append({'rva':site['instruction_rva'],'reason':'indirect_call_or_jump','operand':site['operand']})
        for edge in sorted(node['direct_edges'],key=lambda x:int(x['target_rva'],16)):
            pending.append((int(edge['target_rva'],16),depth+1))
        nodes.append(node)
    # Co-reference/call edges lack object dataflow and are never dependency edges.
    unresolved.append({'reason':'parent_child_dataflow_not_reconstructed'})
    unique = {str(sorted(x.items())):x for x in unresolved}
    return {'format_version':1,'executable_sha256':actual,'logical_input':Path(logical_path).name,
            'roots':roots,'budgets':{'max_depth':max_depth,'max_functions':max_functions,'max_function_bytes':65536},
            'functions':sorted(nodes,key=lambda x:int(x['entry_rva'],16)),
            'ticktask_references':sorted(references,key=lambda x:(int(x['instruction_rva'],16),x['task'],x['identity_kind'])),
            'candidate_dependency_edges':[], 'unresolved':[unique[k] for k in sorted(unique)],'warning':WARNING}
