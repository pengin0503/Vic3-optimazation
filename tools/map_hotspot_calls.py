#!/usr/bin/env python3
"""Bounded static call/reference graph for measured TickTask code anchors.

Requires optional Capstone. Decodes individual chained-unwind code ranges;
does not infer runtime reachability, callback invocation, or task dependencies.
"""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import struct
import sys

from analyze_vic3 import Error, PE, read_input
from map_ticktask_rtti import runtime_functions
from runtime_function_groups import RuntimeFunctionIndex, backed_bytes, group_metadata


def verify_hash(binary: bytes, expected: str) -> str:
    actual = hashlib.sha256(binary).hexdigest()
    if actual != expected:
        raise Error(f'executable hash mismatch: expected {expected}, got {actual}')
    return actual


def executable_rva(pe, rva):
    return any(s['virtual_address'] <= rva < s['virtual_address'] + s['raw_size']
               and int(s['characteristics'], 16) & 0x20000000 for s in pe.sections)


def referenced_vtable(binary, pe, rva):
    """Validate MSVC COL/type-name and enumerate candidate virtual slots."""
    try:
        col = struct.unpack('<Q', backed_bytes(binary, pe, rva - 8, 8))[0] - pe.imagebase
        signature, _, _, td, _, pself = struct.unpack('<6I', backed_bytes(binary, pe, col, 24))
        if signature != 1 or pself != col:
            return None
        section = next((s for s in pe.sections if s['virtual_address'] <= td + 16
                        < s['virtual_address'] + s['raw_size']), None)
        if section is None:
            return None
        available = section['virtual_address'] + section['raw_size'] - td - 16
        raw_name = backed_bytes(binary, pe, td + 16, min(available, 4096))
        end = raw_name.find(b'\0')
        if end < 0 or not raw_name.startswith((b'.?AV', b'.?AU')):
            return None
        name = raw_name[:end].decode('ascii')
        slots = []
        for slot in range(24):
            target = struct.unpack('<Q', backed_bytes(binary, pe, rva + slot*8, 8))[0] - pe.imagebase
            if not executable_rva(pe, target):
                break
            slots.append({'slot':slot, 'target_rva':f'0x{target:x}', 'kind':'vtable_slot_candidate'})
        if not slots:
            return None
        return {'vtable_rva':f'0x{rva:x}', 'complete_object_locator_rva':f'0x{col:x}',
                'type_descriptor_rva':f'0x{td:x}', 'type_name':name, 'slots':slots}
    except (Error, UnicodeError, struct.error):
        return None


def analyze_function(binary, pe, index, entry_rva: int) -> dict:
    try:
        import capstone as cs
        from capstone import x86_const as x86
    except ImportError as exc:
        raise Error('install optional dependency: python -m pip install -r tools/requirements-callgraph.txt') from exc
    group = index.group_for(entry_rva)
    if group is None or group['status'] != 'resolved':
        raise Error(f'no resolved unwind group for 0x{entry_rva:x}')
    decoder = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_64)
    decoder.detail = True
    output = {'entry_rva': f'0x{entry_rva:x}', 'metadata': group_metadata(group),
              'ranges': [], 'decoded_bytes': 0, 'fully_decoded': True,
              'direct_edges': [], 'indirect_sites': [], 'code_address_references': [],
              'vtable_address_references': []}

    def in_group(rva):
        return any(begin <= rva < end for begin, end in group['ranges'])

    for begin, end in group['ranges']:
        raw = backed_bytes(binary, pe, begin, end - begin)
        decoded = 0
        for instruction in decoder.disasm(raw, begin):
            decoded += instruction.size
            kind = instruction.mnemonic
            if kind in ('call', 'jmp'):
                op = instruction.operands[0]
                if op.type == x86.X86_OP_IMM:
                    target = op.imm
                    if kind == 'call' or not in_group(target):
                        output['direct_edges'].append({
                            'instruction_rva': f'0x{instruction.address:x}',
                            'target_rva': f'0x{target:x}',
                            'kind': 'call' if kind == 'call' else 'tail_jump_candidate'})
                else:
                    site = {'instruction_rva': f'0x{instruction.address:x}',
                            'kind': kind, 'operand': instruction.op_str}
                    if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP:
                        site['pointer_slot_rva'] = f'0x{instruction.address + instruction.size + op.mem.disp:x}'
                    output['indirect_sites'].append(site)
            # Address materialization is evidence of a code pointer, not a call.
            if kind in ('lea', 'mov', 'movabs'):
                for op in instruction.operands[1:]:
                    target = None
                    if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP and kind == 'lea':
                        target = instruction.address + instruction.size + op.mem.disp
                    elif op.type == x86.X86_OP_IMM:
                        target = op.imm - pe.imagebase
                    if target is not None and executable_rva(pe, target) and not in_group(target):
                        output['code_address_references'].append({
                            'instruction_rva': f'0x{instruction.address:x}',
                            'target_rva': f'0x{target:x}', 'kind': 'code_address_candidate',
                            'destination': instruction.op_str.split(',')[0]})
                    if target is not None:
                        vtable = referenced_vtable(binary, pe, target)
                        if vtable:
                            vtable['instruction_rva'] = f'0x{instruction.address:x}'
                            output['vtable_address_references'].append(vtable)
        complete = decoded == len(raw)
        output['ranges'].append({'begin_rva': f'0x{begin:x}', 'end_rva': f'0x{end:x}',
                                 'size_bytes': len(raw), 'decoded_bytes': decoded,
                                 'fully_decoded': complete, 'sha256': hashlib.sha256(raw).hexdigest()})
        output['decoded_bytes'] += decoded
        output['fully_decoded'] &= complete
    return output


def build_graph(binary, pe, index, seeds: dict, *, max_depth=2, max_functions=80, max_function_bytes=65536):
    if not 0 <= max_depth <= 3 or max_functions < 1 or max_function_bytes < 1:
        raise Error('invalid graph budget: depth 0..3 and positive size/count required')
    pending = deque((entry, 0) for _, entry in sorted(seeds.items()))
    nodes, skipped, visited = [], {}, set()
    while pending:
        entry, depth = pending.popleft()
        group = index.group_for(entry)
        if group is None or group['status'] != 'resolved':
            skipped[f'0x{entry:x}'] = 'no_unwind_metadata' if group is None else group['error']
            continue
        root = group['root'][0]
        if root in visited:
            continue
        if depth > max_depth:
            skipped[f'0x{entry:x}'] = 'depth_budget'
            continue
        if len(nodes) >= max_functions or group['size_bytes'] > max_function_bytes:
            skipped[f'0x{entry:x}'] = 'function_budget' if len(nodes) >= max_functions else 'byte_budget'
            continue
        visited.add(root)
        result = analyze_function(binary, pe, index, entry)
        result['depth'] = depth
        nodes.append(result)
        # Callback candidates count as a graph step but remain a separate edge type.
        for edge in result['direct_edges'] + result['code_address_references']:
            pending.append((int(edge['target_rva'], 16), depth + 1))
        for reference in result['vtable_address_references']:
            for slot in reference['slots']:
                pending.append((int(slot['target_rva'], 16), depth + 1))
    # A target initially beyond budget may later be expanded through another path.
    skipped = {rva: reason for rva, reason in skipped.items()
               if index.group_for(int(rva,16)) is None
               or index.group_for(int(rva,16))['root'] is None
               or index.group_for(int(rva,16))['root'][0] not in visited}
    return {'format_version': 1, 'executable_sha256': hashlib.sha256(binary).hexdigest(),
            'seeds': {name: f'0x{entry:x}' for name, entry in sorted(seeds.items())},
            'budgets': {'max_depth': max_depth, 'max_functions': max_functions,
                        'max_function_bytes': max_function_bytes},
            'nodes': sorted(nodes, key=lambda x:int(x['entry_rva'],16)),
            'not_expanded': dict(sorted(skipped.items())),
            'warning': 'Linear static decode of metadata ranges only. Direct calls, tail-jump candidates, and code-address candidates are distinct; no runtime reachability, callback execution, task dependency, lock causality, or optimization benefit is proven.'}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    parser.add_argument('--rtti', type=Path, required=True)
    parser.add_argument('--task', action='append', required=True)
    parser.add_argument('--depth', type=int, default=2)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        binary, _ = read_input(args.input, 'victoria3.exe')
        actual = verify_hash(binary, args.expected_sha256)
        rtti = json.loads(args.rtti.read_text(encoding='utf-8'))
        if rtti.get('executable_sha256') != actual:
            raise Error('RTTI map belongs to a different executable')
        classes = {c['name']:c for c in rtti['classes']}
        seeds = {}
        for task in args.task:
            name = task if task.startswith('CTickTask_') else 'CTickTask_' + task
            if name not in classes or classes[name]['vtable_candidate_count'] != 1:
                raise Error(f'unmapped/ambiguous TickTask {name}')
            seeds[name] = int(classes[name]['task_specific_tail_vfunc_rva'],16)
        pe = PE(binary)
        index = RuntimeFunctionIndex(binary, pe, runtime_functions(binary, pe))
        result = build_graph(binary, pe, index, seeds, max_depth=args.depth)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n',encoding='utf-8')
    except (Error, OSError, ValueError, KeyError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    print(f"Mapped {len(result['nodes'])} function groups; {len(result['not_expanded'])} targets remain unexpanded.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
