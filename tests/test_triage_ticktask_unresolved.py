"""Synthetic-only safety tests for TickTask static evidence triage."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import triage_ticktask_unresolved as mod

HASH = '9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'


def fixture():
    return {
        'format_version': 1, 'executable_sha256': HASH,
        'functions': [
            {'entry_rva': '0x1000', 'ranges': [{'begin_rva': '0x1000', 'end_rva': '0x1020'}]},
            {'entry_rva': '0x2000', 'ranges': [{'begin_rva': '0x2000', 'end_rva': '0x2020'}]},
        ],
        'candidate_dependency_edges': [{'confidence': 'candidate'}],
        'unresolved': [
            {'reason': 'indirect_call_or_jump', 'rva': '0x1005', 'operand': 'rax'},
            {'reason': 'no_unwind_metadata', 'rva': '0x3000'},
            {'reason': 'parent_child_dataflow_not_reconstructed'},
            {'reason': 'future_reason', 'rva': '0x1020'},
        ],
    }


class TriageTests(unittest.TestCase):
    def test_classifies_without_inventing_edges(self):
        source = fixture()
        original = copy.deepcopy(source)
        output = mod.build_triage(source)
        self.assertEqual(source, original)
        self.assertEqual(output['source_unresolved_count'], 4)
        self.assertEqual(output['input_dependency_edges'], 1)
        self.assertEqual(output['by_reason'], {
            'indirect_call_or_jump': 1,
            'no_unwind_metadata': 1,
            'parent_child_dataflow_not_reconstructed': 1,
            'future_reason': 1,
        })
        items = {item['reason']: item for item in output['work_items']}
        self.assertEqual(items['indirect_call_or_jump']['analysis_category'], 'indirect_dispatch')
        self.assertEqual(items['no_unwind_metadata']['analysis_category'], 'metadata_or_decode')
        self.assertEqual(items['parent_child_dataflow_not_reconstructed']['analysis_category'], 'structural_dataflow')
        self.assertEqual(items['future_reason']['analysis_category'], 'other')
        self.assertEqual(items['indirect_call_or_jump']['operand'], 'rax')
        self.assertTrue(all(item['runtime_verified'] is False for item in items.values()))
        self.assertIn('not', output['warning'].lower())
        self.assertEqual(mod.build_triage(source), output)

    def test_owner_half_open_and_ambiguous(self):
        source = fixture()
        source['functions'].append({'entry_rva': '0x1010', 'ranges': [
            {'begin_rva': '0x1010', 'end_rva': '0x1030'}]})
        source['unresolved'] += [
            {'reason': 'indirect_call_or_jump', 'rva': '0x1015'},
            {'reason': 'indirect_call_or_jump', 'rva': '0x2005'},
        ]
        items = mod.build_triage(source)['work_items']
        by_rva = {item['rva']: item for item in items if 'rva' in item}
        self.assertEqual(by_rva['0x1005']['owner_function_rva'], '0x1000')
        self.assertEqual(by_rva['0x1015']['owner_function_rva'], None)
        self.assertTrue(by_rva['0x1015']['ownership_ambiguous'])
        self.assertEqual(by_rva['0x1020']['owner_function_rva'], '0x1010')
        self.assertEqual(by_rva['0x2005']['owner_function_rva'], '0x2000')
        self.assertFalse(by_rva['0x2005']['ownership_ambiguous'])
        # The last address is exactly the end of the first function, not inside it.
        self.assertFalse(by_rva['0x1020']['ownership_ambiguous'])

    def test_rejects_wrong_build_and_malformed_inputs(self):
        for key, bad in [('format_version', 2), ('executable_sha256', 'bad'),
                         ('unresolved', 'invalid'), ('functions', 'invalid'),
                         ('candidate_dependency_edges', None)]:
            data = fixture()
            data[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.build_triage(data)
        for bad_rva in ['1000', '0x-1', '0xzz', '-0x1', 1000, '0x']:
            data = fixture()
            data['unresolved'].append({'reason': 'no_unwind_metadata', 'rva': bad_rva})
            with self.subTest(rva=bad_rva), self.assertRaises(ValueError):
                mod.build_triage(data)
        data = fixture()
        data['functions'][0]['ranges'][0]['end_rva'] = '0x1000'
        with self.assertRaises(ValueError):
            mod.build_triage(data)
        with self.assertRaises(ValueError):
            mod.build_triage([])

    def test_empty_valid_artifact(self):
        data = fixture()
        data['functions'] = []
        data['unresolved'] = []
        data['candidate_dependency_edges'] = []
        output = mod.build_triage(data)
        self.assertEqual(output['work_items'], [])
        self.assertEqual(output['by_reason'], {})

    def test_cli_repeatable_and_source_hash(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            source = td / 'in.json'
            source.write_text(json.dumps(fixture(), indent=1), encoding='utf-8')
            out_a, out_b = td / 'a.json', td / 'b.json'
            self.assertEqual(mod.main([str(source), '--output', str(out_a)]), 0)
            self.assertEqual(mod.main([str(source), '--output', str(out_b)]), 0)
            self.assertEqual(out_a.read_bytes(), out_b.read_bytes())
            self.assertEqual(json.loads(out_a.read_text())['source_json_sha256'],
                             hashlib.sha256(source.read_bytes()).hexdigest())

    def test_cli_invalid_input_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            source, output = td / 'broken.json', td / 'existing.json'
            source.write_text('{not JSON', encoding='utf-8')
            output.write_text('KEEP', encoding='utf-8')
            self.assertEqual(mod.main([str(source), '--output', str(output)]), 2)
            self.assertEqual(output.read_text(), 'KEEP')

    def test_cli_refuses_input_as_output(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'in.json'
            source.write_text(json.dumps(fixture()), encoding='utf-8')
            before = source.read_bytes()
            self.assertEqual(mod.main([str(source), '--output', str(source)]), 2)
            self.assertEqual(source.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
