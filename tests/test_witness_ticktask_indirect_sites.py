import copy
import importlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
try:
    witness = importlib.import_module('witness_ticktask_indirect_sites')
except ImportError:
    witness = None


class WitnessTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(witness, 'bounded witness extractor is not implemented')

    def test_memory_call_keeps_exact_boundary_bytes_and_prior_context(self):
        result = witness.decode_witness(bytes.fromhex('48 8b 03 ff 50 08 c3'), 0x1000, 0x1003)
        self.assertEqual(result['instruction']['bytes'], 'ff 50 08')
        self.assertEqual(result['instruction']['instruction_rva'], '0x1003')
        self.assertEqual(result['indirect_operand_kind'], 'memory')
        self.assertEqual(result['context'][0]['mnemonic'], 'mov')
        self.assertIsNone(result['callee_rva'])
        self.assertFalse(result['dependency_edge_confirmed'])
        self.assertFalse(result['runtime_verified'])

    def test_register_call_and_tail_jump_remain_unknown(self):
        for opcode, mnemonic in [('ff d0 c3', 'call'), ('ff e0', 'jmp')]:
            r = witness.decode_witness(bytes.fromhex(opcode), 0x1000, 0x1000)
            self.assertEqual(r['instruction']['mnemonic'], mnemonic)
            self.assertEqual(r['indirect_operand_kind'], 'register')
            self.assertEqual(r['context'], [])
            self.assertIsNone(r['callee_rva'])

    def test_mid_instruction_direct_and_non_control_sites_rejected(self):
        for code, site in [('48 8b 03 ff 50 08 c3', 0x1004), ('e8 00 00 00 00 c3', 0x1000), ('90 ff d0', 0x1000)]:
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    witness.decode_witness(bytes.fromhex(code), 0x1000, site)

    def test_partial_decode_and_large_range_fail_closed(self):
        for code in (bytes.fromhex('ff d0 0f'), b'\x90'*65537, b''):
            with self.assertRaises(ValueError):
                witness.decode_witness(code, 0x1000, 0x1000)

    def test_context_is_bounded_to_eight_preceding_instructions(self):
        r = witness.decode_witness(b'\x90'*20+bytes.fromhex('ff d0 c3'), 0x1000, 0x1014)
        self.assertEqual(len(r['context']), 8)
        self.assertEqual(r['context'][0]['instruction_rva'], '0x100c')

    def test_wrong_binary_hash_rejected_before_pe_decode(self):
        with self.assertRaisesRegex(ValueError, 'executable hash'):
            witness.build_witnesses(b'owned fixture, not an exact game exe', {})

    def test_source_identity_and_ownership_are_not_synthesized(self):
        from triage_ticktask_unresolved import EXPECTED_SHA256
        source = dict(format_version=1, executable_sha256=EXPECTED_SHA256,
            functions=[dict(entry_rva='0x1000', ranges=[dict(begin_rva='0x1000', end_rva='0x1010')])],
            candidate_dependency_edges=[], unresolved=[dict(reason='indirect_call_or_jump', rva='0x1003')]*2)
        original = copy.deepcopy(source)
        self.assertEqual(witness.source_sites(source), [('0x1003', '0x1000', 0x1000, 0x1010)])
        self.assertEqual(source, original)
        source['functions'].append(dict(entry_rva='0x1001', ranges=[dict(begin_rva='0x1001', end_rva='0x1010')]))
        with self.assertRaisesRegex(ValueError, 'owner'):
            witness.source_sites(source)

    def test_wrong_types_and_out_of_range_addresses_rejected(self):
        for begin, site in ((True, 1), (-1, 0), (0x1000, 0xfff), (0x1000, 0x1003), (1<<64, 1<<64)):
            with self.assertRaises(ValueError):
                witness.decode_witness(bytes.fromhex('ff d0 c3'), begin, site)


if __name__ == '__main__':
    unittest.main()
