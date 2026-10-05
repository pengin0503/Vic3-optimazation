#!/usr/bin/env python3
"""Find E8 rel32 callers, validating instruction boundaries via unwind groups.

Raw opcode matches, rejected matches and unresolved matches remain distinct.
Does not enumerate indirect callers, tail jumps, or runtime reachability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

from analyze_vic3 import Error, PE, read_input
from map_ticktask_rtti import runtime_functions
from runtime_function_groups import RuntimeFunctionIndex, backed_bytes
from map_hotspot_calls import analyze_function, executable_rva, verify_hash


def map_callers(binary, pe, index, targets, *, max_caller_regions=128, max_function_bytes=65536):
    if not targets or len(targets) > 32 or max_caller_regions < 1 or max_function_bytes < 1:
        raise Error('require 1..32 targets and positive caller/byte budgets')
    if any(not executable_rva(pe, rva) for rva in targets.values()):
        raise Error('all targets must be file-backed executable RVAs')
    try:
        import capstone as cs
    except ImportError as exc:
        raise Error('install optional dependency: python -m pip install -r tools/requirements-callgraph.txt') from exc
    decoder = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_64)
    target_rvas = set(targets.values())
    candidates = []
    for section in pe.sections:
        if not int(section['characteristics'], 16) & 0x20000000 or not section['raw_size']:
            continue
        begin = section['virtual_address']
        raw = backed_bytes(binary, pe, begin, section['raw_size'])
        offset = raw.find(b'\xe8')
        while offset >= 0:
            if offset + 5 <= len(raw):
                site = begin + offset
                target = site + 5 + struct.unpack_from('<i', raw, offset + 1)[0]
                if target in target_rvas:
                    candidates.append((site, target))
            offset = raw.find(b'\xe8', offset + 1)
    cache, opcode_calls, confirmed, rejected, unresolved = {}, {}, [], [], []
    for site, target in sorted(candidates):
        item = {'opcode_rva':f'0x{site:x}', 'target_rva':f'0x{target:x}'}
        group = index.group_for(site)
        if group is None or group['status'] != 'resolved':
            unresolved.append({**item, 'reason':'no_unwind_metadata' if group is None else group['error']})
            continue
        root = group['root'][0]
        if root not in cache:
            if len(cache) >= max_caller_regions or group['size_bytes'] > max_function_bytes:
                unresolved.append({**item, 'reason':'caller_budget' if len(cache) >= max_caller_regions else 'byte_budget'})
                continue
            cache[root] = analyze_function(binary, pe, index, root)
            # E8 may follow legal instruction prefixes. Retain the decoded
            # instruction start separately from its raw opcode position.
            calls = {int(e['instruction_rva'],16):int(e['target_rva'],16)
                     for e in cache[root]['direct_edges'] if e['kind'] == 'call'}
            opcode_calls[root] = {}
            for begin,end in group['ranges']:
                for instruction in decoder.disasm(backed_bytes(binary, pe, begin, end-begin), begin):
                    if instruction.address in calls and instruction.size >= 5 and instruction.bytes[-5] == 0xe8:
                        opcode_calls[root][instruction.address + instruction.size - 5] = (instruction.address, calls[instruction.address])
        region = cache[root]
        decoded_call = opcode_calls[root].get(site)
        if decoded_call is not None and decoded_call[1] == target:
            confirmed.append({**item, 'instruction_rva':f'0x{decoded_call[0]:x}',
                              'caller_root_rva':f'0x{root:x}', 'kind':'decoded_direct_call'})
        elif region['fully_decoded']:
            rejected.append({**item, 'reason':'not_a_decoded_direct_call'})
        else:
            unresolved.append({**item, 'reason':'incomplete_decode'})
    return {'format_version':1, 'executable_sha256':hashlib.sha256(binary).hexdigest(),
            'targets':{name:f'0x{rva:x}' for name,rva in sorted(targets.items())},
            'scan_scope':'E8 rel32 candidates in all file-backed executable sections',
            'budgets':{'max_caller_regions':max_caller_regions, 'max_function_bytes':max_function_bytes},
            'raw_candidate_count':len(candidates), 'confirmed_calls':confirmed,
            'rejected_candidates':rejected, 'unresolved_candidates':unresolved,
            'caller_regions':[cache[root] for root in sorted(cache)],
            'warning':'Instruction-boundary validation is linear static evidence, not runtime reachability. Indirect calls, tail jumps, and regions without unwind metadata are not exhaustively mapped.'}


def named_rva(value):
    try:
        name, address = value.split('=', 1)
        rva = int(address, 0)
        if not name or rva < 0:
            raise ValueError()
        return name, rva
    except ValueError as exc:
        raise argparse.ArgumentTypeError('expected name=0xRVA') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--target', action='append', type=named_rva, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if len({name for name,_ in args.target}) != len(args.target):
            raise Error('duplicate target names')
        binary, _ = read_input(args.input, 'victoria3.exe')
        verify_hash(binary, args.expected_sha256)
        pe = PE(binary)
        index = RuntimeFunctionIndex(binary, pe, runtime_functions(binary, pe))
        result = map_callers(binary, pe, index, dict(args.target))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    except (Error, OSError, ValueError, struct.error) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    print(f"Validated {len(result['confirmed_calls'])} direct calls; {len(result['unresolved_candidates'])} candidates unresolved.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
