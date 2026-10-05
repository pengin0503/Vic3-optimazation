from __future__ import annotations

import sys
import struct
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_analyze_vic3 import minimal_pe64
from analyze_vic3 import PE
import map_ticktask_rtti as mod


class RuntimeFunctionGroupTests(unittest.TestCase):
    def fixture(self, entries, parents=(), codes=1):
        binary = bytearray(minimal_pe64(b'\x90' * 0x1000))
        pe = PE(binary)
        for _, _, unwind in entries:
            struct.pack_into('<4B', binary, pe.rva(unwind), 1, 0, 0, 0)
        for child, parent in parents:
            offset = pe.rva(child[2])
            struct.pack_into('<4B', binary, offset, 1 | (4 << 3), 0, codes, 0)
            struct.pack_into('<III', binary, offset + 4 + ((codes + 1) & ~1) * 2, *parent)
        return binary, pe

    def test_multilevel_chain_preserves_noncontiguous_ranges(self):
        entries = [(0x1000, 0x100a, 0x1800), (0x100a, 0x1050, 0x1820), (0x1100, 0x1140, 0x1840)]
        binary, pe = self.fixture(entries, [(entries[1], entries[0]), (entries[2], entries[1])])
        index = mod.RuntimeFunctionIndex(binary, pe, entries)
        result = index.group_for(0x1110)
        self.assertEqual(result['status'], 'resolved')
        self.assertEqual(result['root'], entries[0])
        self.assertEqual(result['ranges'], [(0x1000, 0x1050), (0x1100, 0x1140)])
        self.assertEqual(result['size_bytes'], 144)
        self.assertEqual(result['fragment_count'], 3)
        self.assertEqual(result, index.group_for(0x1000))
        self.assertIsNone(index.group_for(0x1080))

    def test_shared_unwind_does_not_merge_unrelated_functions(self):
        entries = [(0x1000, 0x1020, 0x1800), (0x1200, 0x1220, 0x1800)]
        binary, pe = self.fixture(entries)
        index = mod.RuntimeFunctionIndex(binary, pe, entries)
        self.assertEqual(index.group_for(0x1000)['ranges'], [(0x1000, 0x1020)])
        self.assertEqual(index.group_for(0x1200)['root'], entries[1])

    def test_odd_and_even_unwind_code_counts_align_chain_entry(self):
        entries = [(0x1000, 0x1020, 0x1800), (0x1100, 0x1120, 0x1820)]
        for count in (0, 1, 2, 3):
            with self.subTest(count=count):
                binary, pe = self.fixture(entries, [(entries[1], entries[0])], codes=count)
                result = mod.RuntimeFunctionIndex(binary, pe, entries).group_for(0x1100)
                self.assertEqual(result['fragment_count'], 2)

    def test_cycle_is_reported_without_fabricated_range(self):
        entries = [(0x1000, 0x1020, 0x1800), (0x1100, 0x1120, 0x1820)]
        binary, pe = self.fixture(entries, [(entries[0], entries[1]), (entries[1], entries[0])])
        result = mod.RuntimeFunctionIndex(binary, pe, entries).group_for(0x1000)
        self.assertEqual(result['status'], 'invalid')
        self.assertEqual(result['ranges'], [])
        self.assertIn('cycle', result['error'])

    def test_missing_chain_target_is_reported(self):
        entries = [(0x1000, 0x1020, 0x1800)]
        binary, pe = self.fixture(entries, [(entries[0], (0x1100, 0x1120, 0x1820))])
        result = mod.RuntimeFunctionIndex(binary, pe, entries).group_for(0x1000)
        self.assertEqual(result['status'], 'invalid')
        self.assertIn('target', result['error'])

    def test_truncated_and_unbacked_unwind_are_reported(self):
        for unwind in (0x1ffe, 0x2500):
            with self.subTest(unwind=unwind):
                binary = minimal_pe64(b'\x90' * 0x1000)
                entries = [(0x1000, 0x1020, unwind)]
                result = mod.RuntimeFunctionIndex(binary, PE(binary), entries).group_for(0x1000)
                self.assertEqual(result['status'], 'invalid')
                self.assertEqual(result['ranges'], [])

    def test_conflicting_handler_flags_are_rejected(self):
        entries = [(0x1000, 0x1020, 0x1800)]
        binary, pe = self.fixture(entries)
        binary[pe.rva(0x1800)] = 1 | (5 << 3)
        result = mod.RuntimeFunctionIndex(binary, pe, entries).group_for(0x1000)
        self.assertEqual(result['status'], 'invalid')

    def test_unsupported_version_is_not_assumed_to_be_version_one(self):
        entries = [(0x1000, 0x1020, 0x1800)]
        binary, pe = self.fixture(entries)
        binary[pe.rva(0x1800)] = 3
        result = mod.RuntimeFunctionIndex(binary, pe, entries).group_for(0x1000)
        self.assertEqual(result['status'], 'invalid')

    def test_deep_chain_does_not_depend_on_python_recursion_limit(self):
        count = 1100
        binary = bytearray(minimal_pe64(b'\x90' * 0x12000))
        pe = PE(binary)
        entries = [(0x1000 + i * 0x10, 0x1008 + i * 0x10, 0x6000 + i * 0x20) for i in range(count)]
        for i, entry in enumerate(entries):
            offset = pe.rva(entry[2])
            struct.pack_into('<4B', binary, offset, 1 | (4 << 3) if i else 1, 0, 0, 0)
            if i:
                struct.pack_into('<III', binary, offset + 4, *entries[i-1])
        result = mod.RuntimeFunctionIndex(binary, pe, entries).group_for(entries[-1][0])
        self.assertEqual(result['fragment_count'], 1100)
        self.assertEqual(result['size_bytes'], 8800)

    def test_overlap_is_invalid_at_both_ambiguous_and_outer_tail_addresses(self):
        entries = [(0x1000, 0x1080, 0x1800), (0x1040, 0x1060, 0x1820)]
        binary, pe = self.fixture(entries)
        index = mod.RuntimeFunctionIndex(binary, pe, entries)
        for address in (0x1010, 0x1050, 0x1070):
            result = index.group_for(address)
            self.assertIsNotNone(result)
            self.assertEqual(result['status'], 'invalid')
            self.assertIn('overlap',result['error'])

    def test_same_start_conflict_cannot_select_an_arbitrary_function(self):
        entries = [(0x1000, 0x1080, 0x1800), (0x1000, 0x1020, 0x1820)]
        binary, pe = self.fixture(entries)
        index = mod.RuntimeFunctionIndex(binary, pe, entries)
        self.assertEqual(index.group_for(0x1000)['status'],'invalid')
        self.assertEqual(index.group_for(0x1070)['status'],'invalid')


if __name__ == '__main__':
    unittest.main()
