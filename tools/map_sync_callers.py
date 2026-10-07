#!/usr/bin/env python3
"""Map instruction-boundary references to imported Windows synchronization APIs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

from analyze_vic3 import Error, PE, read_input, u16, u32, u64
from map_hotspot_calls import verify_hash
from map_ticktask_rtti import runtime_functions
from runtime_function_groups import RuntimeFunctionIndex, backed_bytes, group_metadata

SYNC_IMPORT_NAMES = {
    'WaitForSingleObject', 'WaitForMultipleObjects', 'WaitOnAddress',
    'SleepConditionVariableSRW', 'AcquireSRWLockExclusive', 'AcquireSRWLockShared',
    'ReleaseSRWLockExclusive', 'ReleaseSRWLockShared', 'WakeByAddressSingle',
    'WakeByAddressAll', 'EnterCriticalSection', 'LeaveCriticalSection',
}
KNOWN_STATIC_REGIONS = {
    'scheduler_heuristic_candidate': (0x7DB150, 0x7DBA91),
    'range_runner_candidate': (0x7DBAA0, 0x7DC13E),
    'dispatcher_candidate': (0x7DC160, 0x7DC606),
}
WARNING = (
    'Instruction-boundary static import-reference evidence only. A direct_iat_call is '
    'an indirect machine call whose IAT slot resolves the imported API; address loads and '
    'other indirect calls remain separate. Runtime wait duration, causality, game-state '
    'release identity and optimization benefit are unproven.'
)


def enumerate_sync_imports(binary: bytes, pe: PE) -> list[dict]:
    directory_rva, _ = pe.directory(1)
    if not directory_rva:
        return []
    out = []
    base = pe.rva(directory_rva)
    for descriptor_index in range(4096):
        offset = base + descriptor_index * 20
        oft, _, _, name_rva, first_thunk = struct.unpack_from('<IIIII', binary, offset)
        if not any((oft, name_rva, first_thunk)):
            break
        dll = pe.cstr(name_rva)
        lookup = oft or first_thunk
        if not lookup or not first_thunk:
            continue
        lookup_offset = pe.rva(lookup)
        for index in range(200000):
            value = u64(binary, lookup_offset + index * 8)
            if not value:
                break
            if value >> 63:
                continue
            name_offset = pe.rva(value)
            hint = u16(binary, name_offset)
            end = binary.find(b'\0', name_offset + 2, min(len(binary), name_offset + 4096))
            if end < 0:
                raise Error('unterminated import name')
            name = binary[name_offset + 2:end].decode('ascii', 'replace')
            if name in SYNC_IMPORT_NAMES:
                out.append({
                    'dll': dll,
                    'name': name,
                    'hint': hint,
                    'iat_rva': f'0x{first_thunk + index * 8:x}',
                })
    return sorted(out, key=lambda item: (item['dll'].lower(), item['name'], int(item['iat_rva'], 16)))


def _known_region_tags(group: dict) -> list[str]:
    tags = []
    for name, (wanted_begin, wanted_end) in KNOWN_STATIC_REGIONS.items():
        if any(begin < wanted_end and wanted_begin < end for begin, end in group['ranges']):
            tags.append(name)
    return sorted(tags)


def map_sync_references(binary: bytes, pe: PE, index: RuntimeFunctionIndex, imports: list[dict], *, max_group_bytes=65536) -> dict:
    if max_group_bytes < 1:
        raise Error('max_group_bytes must be positive')
    try:
        import capstone as cs
        from capstone import x86_const as x86
    except ImportError as exc:
        raise Error('install optional dependency: python -m pip install -r tools/requirements-callgraph.txt') from exc

    by_slot = {int(item['iat_rva'], 16): item for item in imports}
    if len(by_slot) != len(imports):
        raise Error('duplicate synchronization IAT slot')
    decoder = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_64)
    decoder.detail = True
    references, unresolved, partial, caller_groups = [], [], [], {}
    skipped_oversize = 0

    for _, group in sorted(index.groups.items()):
        root = group['root'][0]
        if group['size_bytes'] > max_group_bytes:
            skipped_oversize += 1
            continue
        local_refs, local_indirect, local_partial, incomplete = [], [], [], False
        for begin, end in group['ranges']:
            raw = backed_bytes(binary, pe, begin, end - begin)
            decoded = 0
            for insn in decoder.disasm(raw, begin):
                decoded += insn.size
                matched_iat = False
                for operand in insn.operands:
                    target_slot = None
                    if operand.type == x86.X86_OP_MEM and operand.mem.base == x86.X86_REG_RIP:
                        target_slot = insn.address + insn.size + operand.mem.disp
                    elif operand.type == x86.X86_OP_IMM:
                        for slot in by_slot:
                            if operand.imm == pe.imagebase + slot:
                                target_slot = slot
                                break
                    if target_slot not in by_slot:
                        continue
                    matched_iat = True
                    item = by_slot[target_slot]
                    if insn.mnemonic == 'call':
                        kind = 'direct_iat_call'
                    elif insn.mnemonic == 'jmp':
                        kind = 'direct_iat_jump'
                    elif insn.mnemonic == 'mov':
                        kind = 'iat_pointer_load'
                    elif insn.mnemonic == 'lea':
                        kind = 'iat_slot_address'
                    else:
                        kind = 'iat_address_reference'
                    local_refs.append({
                        'instruction_rva': f'0x{insn.address:x}',
                        'caller_root_rva': f'0x{root:x}',
                        'reference_kind': kind,
                        'operand': insn.op_str,
                        'dll': item['dll'],
                        'import_name': item['name'],
                        'iat_rva': item['iat_rva'],
                    })
                if insn.mnemonic in ('call', 'jmp') and not matched_iat:
                    op = insn.operands[0]
                    if op.type != x86.X86_OP_IMM:
                        local_indirect.append({
                            'instruction_rva': f'0x{insn.address:x}',
                            'caller_root_rva': f'0x{root:x}',
                            'kind': insn.mnemonic,
                            'operand': insn.op_str,
                            'import_identity': None,
                        })
            if decoded != len(raw):
                incomplete = True
                local_partial.append({
                    'caller_root_rva': f'0x{root:x}',
                    'begin_rva': f'0x{begin:x}',
                    'end_rva': f'0x{end:x}',
                    'decoded_bytes': decoded,
                    'size_bytes': len(raw),
                })
        if local_refs:
            references.extend(local_refs)
            if any(ref['reference_kind'] not in ('direct_iat_call', 'direct_iat_jump') for ref in local_refs):
                unresolved.extend(local_indirect)
            partial.extend(local_partial)
            caller_groups[f'0x{root:x}'] = {
                'metadata': group_metadata(group),
                'known_static_region_tags': _known_region_tags(group),
                'fully_decoded': not incomplete,
            }

    return {
        'format_version': 1,
        'executable_sha256': hashlib.sha256(binary).hexdigest(),
        'references': sorted(references, key=lambda item: (int(item['instruction_rva'], 16), item['import_name'], item['reference_kind'])),
        'unresolved_indirect_sites': sorted(unresolved, key=lambda item: (int(item['instruction_rva'], 16), item['operand'])),
        'partial_groups': sorted(partial, key=lambda item: (int(item['caller_root_rva'], 16), int(item['begin_rva'], 16))),
        'caller_groups': {key: caller_groups[key] for key in sorted(caller_groups, key=lambda value: int(value, 16))},
        'budgets': {'max_group_bytes': max_group_bytes},
        'skipped_oversize_group_count': skipped_oversize,
        'warning': WARNING,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        binary, _ = read_input(args.input, 'victoria3.exe')
        verify_hash(binary, args.expected_sha256)
        pe = PE(binary)
        imports = enumerate_sync_imports(binary, pe)
        index = RuntimeFunctionIndex(binary, pe, runtime_functions(binary, pe))
        result = map_sync_references(binary, pe, index, imports)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    except (Error, OSError, ValueError, struct.error) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
