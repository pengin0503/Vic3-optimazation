#!/usr/bin/env python3
"""Reproduce the bounded 1.14.5 dispatch investigation; no game writes/hooks."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from analyze_vic3 import Error, PE, read_input
from map_ticktask_rtti import runtime_functions
from runtime_function_groups import RuntimeFunctionIndex, backed_bytes
from map_hotspot_calls import analyze_function, verify_hash
from map_native_callers import map_callers

EXPECTED = '9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'
REGIONS = {
    'investment_prepare':0xf6e590, 'investment_prepare_callback':0xf7ec40,
    'migration_prepare':0x11b0c00, 'migration_prepare_callback':0x11baee0,
    'employment_prepare':0x13b8310, 'employment_prepare_callback':0x13caed0,
    'employment_collect_candidate':0x13b8540, 'employment_collect_continuation':0x13cada0,
    'employment_sort_callback':0x13cad10, 'employment_sort_branch_candidate':0x13c3140,
    'employment_work_item_candidate':0x10befb0, 'callable_transfer_candidate':0x74f7b0,
    'shared_slot1':0x3bf7200, 'shared_slot3':0x3bf7270,
    'shared_slot4_thunk_target':0x3bf2d60,
    'dispatcher_candidate':0x7dc160, 'range_runner_candidate':0x7dbaa0,
    'heuristic_candidate':0x7db150,
}
# Select instructions from decodes beginning at unwind range starts, never
# restart decoding at an arbitrary address inside a machine instruction.
WINDOWS = {
    'investment_prepare':[(0xf6e726,0xf6e761)],
    'migration_prepare':[(0x11b0d20,0x11b0d90)],
    'employment_prepare':[(0x13b84dd,0x13b850a)],
    'employment_collect_candidate':[(0x13b86e8,0x13b875a)],
    'employment_collect_continuation':[(0x13cadc4,0x13cae60)],
    'employment_sort_callback':[(0x13cad1f,0x13cad52)],
    'employment_sort_branch_candidate':[(0x13c316f,0x13c3192),(0x13c31de,0x13c32bc)],
    'callable_transfer_candidate':[(0x74f7bd,0x74f7f0),(0x74f814,0x74f845)],
    'shared_slot3':[(0x3bf72e3,0x3bf72f3)],
    'dispatcher_candidate':[(0x7dc233,0x7dc282),(0x7dc3f5,0x7dc4e7)],
    'range_runner_candidate':[(0x7dbdcb,0x7dbded)],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output_directory', type=Path)
    args = parser.parse_args()
    import capstone as cs
    binary, logical = read_input(args.input, 'victoria3.exe')
    verify_hash(binary, EXPECTED)
    pe = PE(binary)
    index = RuntimeFunctionIndex(binary, pe, runtime_functions(binary, pe))
    decoder = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_64)
    regions, windows = {}, {}
    for name, rva in sorted(REGIONS.items()):
        region = analyze_function(binary, pe, index, rva)
        if not region['fully_decoded']:
            raise Error(f'incomplete selected region: {name}')
        regions[name] = region
        if name in WINDOWS:
            windows[name] = []
            for span in region['ranges']:
                begin = int(span['begin_rva'],16)
                for instruction in decoder.disasm(backed_bytes(binary, pe, begin, span['size_bytes']), begin):
                    if any(lo <= instruction.address < hi for lo,hi in WINDOWS[name]):
                        windows[name].append({'rva':hex(instruction.address), 'bytes':instruction.bytes.hex(),
                                              'mnemonic':instruction.mnemonic, 'operand':instruction.op_str})
    # .pdata is absent for this known short thunk. Verify only these observed
    # eight bytes; no guessed function size or extension into adjacent padding.
    thunk = backed_bytes(binary, pe, 0x1808250, 8)
    if thunk.hex() != '488bcae908ab3e02' or index.group_for(0x1808250) is not None:
        raise Error('slot4 thunk observation no longer matches')
    selected = {'format_version':1, 'executable_sha256':EXPECTED,
                'logical_input':Path(logical).name, 'regions':regions, 'instruction_windows':windows,
                'bounded_thunk_observation':{'rva':'0x1808250','observed_bytes':thunk.hex(),
                    'observed_size_bytes':8, 'unwind_metadata':None, 'function_extent':'unknown',
                    'instructions':[{'rva':hex(x.address),'mnemonic':x.mnemonic,'operand':x.op_str} for x in decoder.disasm(thunk,0x1808250)]},
                'warning':'Static candidates only. Callback installation, virtual invocation and direct calls remain distinct. Runtime task identity, critical path, ABI and benefit are unproven.'}
    callers = map_callers(binary, pe, index, {'dispatcher_candidate':0x7dc160,
                         'range_runner_candidate':0x7dbaa0, 'heuristic_candidate':0x7db150})
    args.output_directory.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for filename, result in (('dispatch-regions.json',selected),('scheduler-callers.json',callers)):
        content = (json.dumps(result, indent=2, sort_keys=True)+'\n').encode()
        (args.output_directory/filename).write_bytes(content)
        hashes[filename] = hashlib.sha256(content).hexdigest()
    (args.output_directory/'artifact-index.json').write_text(json.dumps({'format_version':1,
        'executable_sha256':EXPECTED, 'artifacts':hashes}, indent=2, sort_keys=True)+'\n')
    print(f'Reproduced {len(regions)} selected regions and {len(callers["confirmed_calls"])} direct caller sites.')


if __name__ == '__main__':
    main()
