from __future__ import annotations

import hashlib
import importlib.util
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_analyze_vic3 import minimal_pe64
from analyze_vic3 import PE
from runtime_function_groups import RuntimeFunctionIndex


@unittest.skipUnless(importlib.util.find_spec('capstone'), 'optional callgraph dependency: capstone')
class HotspotCallTests(unittest.TestCase):
    def fixture(self):
        binary = bytearray(minimal_pe64(b'\x90' * 0x1000))
        pe = PE(binary)
        entries = [(0x1000, 0x1013, 0x1800), (0x1100, 0x1101, 0x1820)]
        for _, _, unwind in entries:
            binary[pe.rva(unwind):pe.rva(unwind)+4] = b'\x01\x00\x00\x00'
        # call 0x1100; call rax; lea rcx,[rip+0xf2]; jmp 0x1100.
        code = b'\xe8\xfb\x00\x00\x00\xff\xd0\x48\x8d\x0d\xf2\x00\x00\x00\xe9\xed\x00\x00\x00'
        binary[pe.rva(0x1000):pe.rva(0x1000)+len(code)] = code
        binary[pe.rva(0x1100)] = 0xc3
        return bytes(binary), pe, entries

    def test_direct_indirect_and_code_address_references_are_separate(self):
        import map_hotspot_calls as mod
        binary, pe, entries = self.fixture()
        index = RuntimeFunctionIndex(binary, pe, entries)
        result = mod.analyze_function(binary, pe, index, 0x1000)
        self.assertTrue(result['fully_decoded'])
        self.assertEqual(result['decoded_bytes'], 19)
        self.assertEqual([(x['instruction_rva'], x['target_rva'], x['kind']) for x in result['direct_edges']],
                         [('0x1000', '0x1100', 'call'), ('0x100e', '0x1100', 'tail_jump_candidate')])
        self.assertEqual(result['indirect_sites'][0]['instruction_rva'], '0x1005')
        self.assertEqual(result['code_address_references'][0]['target_rva'], '0x1100')
        self.assertEqual(result['ranges'][0]['sha256'], hashlib.sha256(binary[0x200:0x213]).hexdigest())

    def test_intra_function_branch_does_not_become_a_callee(self):
        import map_hotspot_calls as mod
        binary, pe, entries = self.fixture()
        binary = bytearray(binary)
        binary[pe.rva(0x100e):pe.rva(0x1013)] = b'\xe9\xed\xff\xff\xff'
        result = mod.analyze_function(binary, pe, RuntimeFunctionIndex(binary, pe, entries), 0x1000)
        self.assertEqual(len(result['direct_edges']), 1)

    def test_decode_stops_at_invalid_instruction_without_reporting_full_coverage(self):
        import map_hotspot_calls as mod
        binary, pe, entries = self.fixture()
        binary = bytearray(binary)
        binary[pe.rva(0x100e):pe.rva(0x1013)] = b'\x90\x90\x90\x90\x0f'
        result = mod.analyze_function(binary, pe, RuntimeFunctionIndex(binary, pe, entries), 0x1000)
        self.assertFalse(result['fully_decoded'])
        self.assertLess(result['decoded_bytes'], result['metadata']['size_bytes'])

    def test_depth_budget_is_explicit_and_hash_mismatch_fails_before_graph(self):
        import map_hotspot_calls as mod
        binary, pe, entries = self.fixture()
        index = RuntimeFunctionIndex(binary, pe, entries)
        result = mod.build_graph(binary, pe, index, {'example': 0x1000}, max_depth=0)
        self.assertEqual(len(result['nodes']), 1)
        self.assertIn('0x1100', result['not_expanded'])
        with self.assertRaises(mod.Error):
            mod.verify_hash(binary, '0' * 64)

    def test_fragment_gap_is_never_decoded_or_counted(self):
        import map_hotspot_calls as mod
        binary, pe, entries = self.fixture()
        binary = bytearray(binary)
        third = (0x1200, 0x1201, 0x1840)
        struct.pack_into('<4BIII', binary, pe.rva(third[2]), 1 | (4 << 3), 0, 0, 0, *entries[0])
        binary[pe.rva(0x1200)] = 0xc3
        result = mod.analyze_function(binary, pe, RuntimeFunctionIndex(binary, pe, entries + [third]), 0x1000)
        self.assertEqual(result['decoded_bytes'], 20)
        self.assertEqual(len(result['ranges']), 2)

    def test_referenced_vtable_has_validated_rtti_and_separate_candidate_edges(self):
        import map_hotspot_calls as mod
        binary, pe, entries = self.fixture()
        binary = bytearray(binary)
        struct.pack_into('<i', binary, pe.rva(0x100a), 0x8f2)
        struct.pack_into('<Q', binary, pe.rva(0x18f8), pe.imagebase + 0x1a00)
        struct.pack_into('<QQ', binary, pe.rva(0x1900), pe.imagebase + 0x1100, 0)
        struct.pack_into('<6I', binary, pe.rva(0x1a00), 1, 0, 0, 0x1a40, 0x1a80, 0x1a00)
        name = b'.?AVTestCallable@@\x00'
        binary[pe.rva(0x1a50):pe.rva(0x1a50)+len(name)] = name
        index = RuntimeFunctionIndex(binary, pe, entries)
        result = mod.analyze_function(binary, pe, index, 0x1000)
        reference = result['vtable_address_references'][0]
        self.assertEqual(reference['type_name'], '.?AVTestCallable@@')
        self.assertEqual(reference['vtable_rva'], '0x1900')
        self.assertEqual(reference['slots'], [{'slot': 0, 'target_rva': '0x1100', 'kind': 'vtable_slot_candidate'}])
        graph = mod.build_graph(binary, pe, index, {'example':0x1000}, max_depth=1)
        self.assertEqual(len(graph['nodes']), 2)

    def test_regular_data_reference_does_not_fabricate_a_vtable(self):
        import map_hotspot_calls as mod
        binary, pe, entries = self.fixture()
        binary = bytearray(binary)
        struct.pack_into('<i', binary, pe.rva(0x100a), 0x8f2)
        result = mod.analyze_function(binary, pe, RuntimeFunctionIndex(binary, pe, entries), 0x1000)
        self.assertEqual(result['vtable_address_references'], [])


if __name__ == '__main__':
    unittest.main()
