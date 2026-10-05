from __future__ import annotations

import struct
import importlib.util
import hashlib
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_analyze_vic3 import minimal_pe64
from analyze_vic3 import Error, PE
from runtime_function_groups import RuntimeFunctionIndex


@unittest.skipUnless(importlib.util.find_spec('capstone'), 'optional callgraph dependency: capstone')
class NativeCallerTests(unittest.TestCase):
    def fixture(self):
        binary = bytearray(minimal_pe64(b'\x90' * 0x1000))
        pe = PE(binary)
        entries = [(0x1000, 0x1010, 0x1800)]
        binary[pe.rva(0x1800):pe.rva(0x1800)+4] = b'\x01\x00\x00\x00'
        # A real call and a false E8 inside movabs's immediate both point to 0x1100.
        binary[pe.rva(0x1000):pe.rva(0x1010)] = bytes.fromhex('e8fb00000048b8e8f4000000000000c3')
        # Genuine call without unwind metadata must remain unresolved.
        binary[pe.rva(0x1200):pe.rva(0x1205)] = b'\xe8' + struct.pack('<i', 0x1100-0x1205)
        return bytes(binary), pe, entries

    def test_opcode_inside_immediate_is_rejected_and_missing_metadata_is_explicit(self):
        import map_native_callers as mod
        binary, pe, entries = self.fixture()
        result = mod.map_callers(binary, pe, RuntimeFunctionIndex(binary, pe, entries), {'callee':0x1100})
        self.assertEqual([x['instruction_rva'] for x in result['confirmed_calls']], ['0x1000'])
        self.assertEqual(result['raw_candidate_count'], 3)
        self.assertEqual(result['rejected_candidates'], [{'opcode_rva':'0x1007', 'target_rva':'0x1100', 'reason':'not_a_decoded_direct_call'}])
        self.assertEqual(result['unresolved_candidates'], [{'opcode_rva':'0x1200', 'target_rva':'0x1100', 'reason':'no_unwind_metadata'}])
        self.assertEqual(len(result['caller_regions']), 1)

    def test_non_executable_target_and_empty_target_list_fail(self):
        import map_native_callers as mod
        binary, pe, entries = self.fixture()
        index = RuntimeFunctionIndex(binary, pe, entries)
        for targets in ({}, {'outside':0x3000}):
            with self.assertRaises(Error):
                mod.map_callers(binary, pe, index, targets)

    def test_raw_candidate_after_decode_stops_remains_unresolved(self):
        import map_native_callers as mod
        binary, pe, entries = self.fixture()
        binary = bytearray(binary)
        # Invalid opcode precedes the apparent call, so no boundary proof is possible.
        binary[pe.rva(0x1000):pe.rva(0x1007)] = bytes.fromhex('0f04e8f9000000')
        result = mod.map_callers(bytes(binary), pe, RuntimeFunctionIndex(binary, pe, entries), {'callee':0x1100})
        self.assertEqual(result['confirmed_calls'], [])
        self.assertIn({'opcode_rva':'0x1002','target_rva':'0x1100','reason':'incomplete_decode'}, result['unresolved_candidates'])

    def test_byte_budget_leaves_candidates_unresolved(self):
        import map_native_callers as mod
        binary, pe, entries = self.fixture()
        result = mod.map_callers(binary, pe, RuntimeFunctionIndex(binary, pe, entries), {'callee':0x1100}, max_function_bytes=8)
        self.assertEqual(result['confirmed_calls'], [])
        self.assertEqual(result['caller_regions'], [])
        self.assertEqual([x['reason'] for x in result['unresolved_candidates']], ['byte_budget','byte_budget','no_unwind_metadata'])

    def test_prefixed_call_retains_instruction_start_and_opcode_position(self):
        import map_native_callers as mod
        binary, pe, entries = self.fixture()
        binary = bytearray(binary)
        binary[pe.rva(0x1000):pe.rva(0x1006)] = bytes.fromhex('48e8fa000000')
        result = mod.map_callers(bytes(binary), pe, RuntimeFunctionIndex(binary, pe, entries), {'callee':0x1100})
        self.assertEqual(result['confirmed_calls'][0]['instruction_rva'], '0x1000')
        self.assertEqual(result['confirmed_calls'][0]['opcode_rva'], '0x1001')

    def test_cli_wrong_hash_and_duplicate_names_do_not_write_output(self):
        import map_native_callers as mod
        binary, _, _ = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/'source.exe', Path(directory)/'result.json'
            source.write_bytes(binary)
            args = [str(source),'--target','test=0x1100','--output',str(output),'--expected-sha256']
            self.assertEqual(mod.main(args+['0'*64]), 2)
            self.assertFalse(output.exists())
            self.assertEqual(mod.main(args+[hashlib.sha256(binary).hexdigest(),'--target','test=0x1200']), 2)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
