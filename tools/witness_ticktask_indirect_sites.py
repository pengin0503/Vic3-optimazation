#!/usr/bin/env python3
"""Bounded exact-build instruction witnesses, never inferred dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from analyze_vic3 import PE, Error, read_input
from runtime_function_groups import backed_bytes
from triage_ticktask_unresolved import EXPECTED_SHA256, build_triage
from parse_native_profiler_trace import unique_object, reject_constant


def decode_witness(code: bytes, begin_rva: int, site_rva: int) -> dict:
    import capstone as cs
    from capstone import x86_const as x86
    if (not isinstance(code, bytes) or not 1 <= len(code) <= 65536 or
        type(begin_rva) is not int or type(site_rva) is not int or
        not 0 <= begin_rva <= site_rva < begin_rva+len(code) <= 1<<64):
        raise ValueError('invalid bounded code range/site')
    decoder = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_64)
    decoder.detail = True
    instructions = list(decoder.disasm(code, begin_rva))
    if sum(i.size for i in instructions) != len(code):
        raise ValueError('partial range decode; site boundary not trusted')
    index = next((n for n, i in enumerate(instructions) if i.address == site_rva), None)
    if index is None:
        raise ValueError('site is not a decoded instruction boundary')
    ins = instructions[index]
    if (ins.mnemonic not in ('call', 'jmp') or len(ins.operands) != 1 or
        ins.operands[0].type not in (x86.X86_OP_MEM, x86.X86_OP_REG)):
        raise ValueError('site is not an indirect call/jump')
    def row(i):
        return dict(instruction_rva=hex(i.address), bytes=i.bytes.hex(' '),
                    mnemonic=i.mnemonic, operand=i.op_str)
    return dict(instruction=row(ins), context=[row(i) for i in instructions[max(0,index-8):index]],
                indirect_operand_kind='memory' if ins.operands[0].type == x86.X86_OP_MEM else 'register',
                callee_rva=None, dependency_edge_confirmed=False, runtime_verified=False)


def source_sites(source: dict) -> list:
    sites = {}
    for item in build_triage(source)['work_items']:
        if item['reason'] != 'indirect_call_or_jump':
            continue
        owner, address = item['owner_function_rva'], int(item.get('rva', '0'), 16)
        if owner is None or item['ownership_ambiguous']:
            raise ValueError('indirect site lacks a unique owner')
        ranges = set()
        for function in source['functions']:
            if function['entry_rva'] == owner:
                ranges.update((int(r['begin_rva'],16), int(r['end_rva'],16)) for r in function['ranges'])
        matches = [(b,e) for b,e in ranges if b <= address < e]
        if len(matches) != 1:
            raise ValueError('indirect site lacks a unique owner range')
        begin, end = matches[0]
        if end-begin > 65536:
            raise ValueError('owner range exceeds decode budget')
        record = (hex(address), owner, begin, end)
        if address in sites and sites[address] != record:
            raise ValueError('conflicting site ownership')
        sites[address] = record
    if len(sites) > 256:
        raise ValueError('site budget exceeded')
    return [sites[k] for k in sorted(sites)]


def build_witnesses(binary: bytes, source: dict) -> dict:
    actual = hashlib.sha256(binary).hexdigest()
    if actual != EXPECTED_SHA256:
        raise ValueError('unsupported executable hash')
    sites = source_sites(source)
    pe = PE(binary)
    cache, rows = {}, []
    for site, owner, begin, end in sites:
        if (begin, end) not in cache:
            cache[begin,end] = backed_bytes(binary, pe, begin, end-begin)
        code = cache[begin,end]
        witness = decode_witness(code, begin, int(site,16))
        witness.update(owner_function_rva=owner, range_begin_rva=hex(begin),
                       range_end_rva=hex(end), range_sha256=hashlib.sha256(code).hexdigest())
        rows.append(witness)
    return dict(format_version=1, executable_sha256=actual, static_only=True,
                confirmed_dependency_edges=[], witness_count=len(rows), witnesses=rows,
                warning='Instruction/owner witnesses only; callee, object type, dependency and runtime cost remain unverified.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('source_json', type=Path)
    args = parser.parse_args(argv)
    try:
        binary, _ = read_input(args.executable, 'victoria3.exe')
        raw = args.source_json.read_bytes()
        source = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object, parse_constant=reject_constant)
        result = build_witnesses(binary, source)
        result['source_json_sha256'] = hashlib.sha256(raw).hexdigest()
        print(json.dumps(result, indent=2, sort_keys=True)+'\n', end='')
        return 0
    except (ValueError, Error, OSError, ImportError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
