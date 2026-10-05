import hashlib
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_analyze_vic3 import minimal_pe64
from analyze_vic3 import Error, PE
import map_ticktask_dependencies as mod


def fixture():
    b = bytearray(minimal_pe64(b'\x90' * 0x1000))
    struct.pack_into('<H', b, 0x86, 2)
    b[0x1b0:0x1b8] = b'.pdata\0\0'
    struct.pack_into('<IIII', b, 0x1b8, 24, 0x3000, 24, 0x1200)
    b.extend(b'\0' * 24)
    pe = PE(b)
    # PE exception directory: two independently validated function records.
    struct.pack_into('<II', b, 0x98 + 112 + 3 * 8, 0x3000, 24)
    for i, entry in enumerate([(0x1000, 0x1015, 0x1800), (0x1100, 0x1101, 0x1820)]):
        struct.pack_into('<III', b, pe.rva(0x3000) + i * 12, *entry)
        b[pe.rva(entry[2]):pe.rva(entry[2])+4] = b'\x01\0\0\0'
    # Duplicate direct calls, indirect call, RIP-relative reference, tail jump.
    b[pe.rva(0x1000):pe.rva(0x1015)] = bytes.fromhex('e8fb000000e8f6000000ffd0488d0ded080000eb0b')
    b[pe.rva(0x1100)] = 0xc3
    return bytes(b)


class DependencyTests(unittest.TestCase):
    def analyze(self, **kw):
        binary = fixture()
        digest = hashlib.sha256(binary).hexdigest()
        with patch.object(mod, 'EXPECTED_SHA256', digest):
            return mod.analyze_dependency_evidence(binary, 'fixture.exe', {'executable_sha256': digest, 'classes': []}, graph_root_rva=0x1000, list_root_rva=0x1000, **kw)

    def test_wrong_hash_and_rtti_hash_fail_closed(self):
        with self.assertRaises(Error):
            mod.analyze_dependency_evidence(b'bad', 'bad', {})
        binary = fixture()
        with patch.object(mod, 'EXPECTED_SHA256', hashlib.sha256(binary).hexdigest()):
            with self.assertRaises(Error):
                mod.analyze_dependency_evidence(binary, 'fixture', {'executable_sha256':'0'*64})

    def test_deterministic_deduplicated_direct_edges_and_separate_indirect_sites(self):
        result = self.analyze()
        self.assertEqual(result, self.analyze())
        root = result['functions'][0]
        calls = [e for e in root['direct_edges'] if e['kind'] == 'call']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['target_rva'], '0x1100')
        self.assertEqual(calls[0]['evidence_rvas'], ['0x1000', '0x1005'])
        self.assertEqual(root['indirect_sites'][0]['instruction_rva'], '0x100a')
        self.assertIn('0x1900', [e['target_rva'] for e in root['rip_relative_data_references']])
        self.assertEqual(result['candidate_dependency_edges'], [])

    def test_budgets_and_unresolved_preserved(self):
        result = self.analyze(max_functions=1)
        self.assertEqual(len(result['functions']), 1)
        self.assertTrue(any(x['reason'] == 'function_budget' for x in result['unresolved']))
        self.assertTrue(any(x['reason'] == 'indirect_call_or_jump' for x in result['unresolved']))
        self.assertTrue(any(x['reason'] == 'depth_budget' for x in self.analyze(max_depth=0)['unresolved']))

    def test_invalid_budget(self):
        with self.assertRaises(Error):
            self.analyze(max_functions=0)


class ClassificationTests(unittest.TestCase):
    def test_only_attested_structural_traversal_can_be_confirmed(self):
        identities = {'CTickTask_A', 'CTickTask_B'}
        base = {'source_task':'CTickTask_A','target_task':'CTickTask_B',
                'evidence_kind':'direct_structural_traversal','evidence_rvas':['0x1000'],
                'structural_relation':{'operation':'parent_child','verified':True}}
        result = mod.classify_relationship(base, identities)
        self.assertEqual(result['confidence'], 'confirmed-static')
        for kind in ('indirect_call', 'shared_helper', 'direct_call'):
            self.assertEqual(mod.classify_relationship(dict(base,evidence_kind=kind),identities)['confidence'],'candidate')
        self.assertEqual(mod.classify_relationship(dict(base,target_task=None),identities)['confidence'],'unresolved')
        self.assertEqual(mod.classify_relationship(dict(base,evidence_rvas=[]),identities)['confidence'],'unresolved')
        self.assertEqual(mod.classify_relationship(dict(base,structural_relation={}),identities)['confidence'],'candidate')

    def test_markdown_reports_zero_confirmed_and_unresolved(self):
        text = mod.render_markdown({'executable_sha256':'x','functions':[], 'candidate_dependency_edges':[], 'unresolved':[{'reason':'unmapped'}]})
        self.assertIn('No confirmed-static parent/child', text)
        self.assertIn('unmapped', text)
        self.assertIn('runtime', text)
