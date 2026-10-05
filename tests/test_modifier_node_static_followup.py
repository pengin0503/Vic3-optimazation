from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from analyze_vic3 import Error

SPEC = importlib.util.spec_from_file_location(
    'reproduce_modifier_node_evidence',
    ROOT / 'research/recipes/reproduce_modifier_node_evidence.py',
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def rtti_fixture(digest='a' * 64):
    return {
        'format_version': 1,
        'executable_sha256': digest,
        'classes': [{
            'name': 'CTickTask_RecalculateModifierNodes',
            'vtable_candidate_count': 1,
            'task_specific_tail_vfunc_rva': '0x7da740',
            'type_descriptor_rva': '0x548be90',
            'complete_object_locator_rva': '0x49a1f00',
            'vtable_rva': '0x44d8f58',
        }],
    }


def graph_fixture(digest='a' * 64, *, full=True):
    return {
        'format_version': 1,
        'executable_sha256': digest,
        'seeds': {'CTickTask_RecalculateModifierNodes': '0x7da740'},
        'budgets': {'max_depth': 2, 'max_functions': 80, 'max_function_bytes': 65536},
        'nodes': [{
            'entry_rva': '0x7da740',
            'depth': 0,
            'fully_decoded': full,
            'decoded_bytes': 16,
            'metadata': {
                'status': 'resolved',
                'size_bytes': 16,
                'ranges': [{'begin_rva': '0x7da740', 'end_rva': '0x7da750'}],
            },
            'ranges': [{
                'begin_rva': '0x7da740',
                'end_rva': '0x7da750',
                'size_bytes': 16,
                'decoded_bytes': 16 if full else 15,
                'fully_decoded': full,
                'sha256': 'b' * 64,
            }],
            'direct_edges': [{
                'instruction_rva': '0x7da744',
                'target_rva': '0x7dbaa0',
                'kind': 'call',
            }],
            'indirect_sites': [{
                'instruction_rva': '0x7da748',
                'kind': 'call',
                'operand': 'rax',
            }],
            'code_address_references': [{
                'instruction_rva': '0x7da74a',
                'target_rva': '0x7db150',
                'kind': 'code_address_candidate',
                'destination': 'rcx',
            }],
            'vtable_address_references': [{
                'instruction_rva': '0x7da74c',
                'vtable_rva': '0x44d8f58',
                'type_name': '.?AVExample@@',
                'slots': [{
                    'slot': 0,
                    'target_rva': '0x7dc160',
                    'kind': 'vtable_slot_candidate',
                }],
            }],
        }],
        'not_expanded': {},
        'warning': 'no runtime reachability or optimization benefit is proven',
    }


class ModifierNodeStaticFollowupTests(unittest.TestCase):
    def test_seed_is_resolved_by_exact_rtti_class_not_external_rva(self):
        seed = mod.resolve_modifier_node_seed(rtti_fixture())
        self.assertEqual(seed['class_name'], 'CTickTask_RecalculateModifierNodes')
        self.assertEqual(seed['task_specific_tail_vfunc_rva'], '0x7da740')
        self.assertNotIn('seed_rva', mod.reproduce.__annotations__)
        bad = rtti_fixture()
        bad['classes'][0]['vtable_candidate_count'] = 2
        with self.assertRaises(Error):
            mod.resolve_modifier_node_seed(bad)

    def test_edge_classes_remain_separate_and_shared_helpers_require_observed_evidence(self):
        graph = graph_fixture()
        mod.validate_graph(graph)
        refs = mod.classify_known_helper_evidence(graph)
        self.assertEqual(refs['range_runner_candidate']['evidence'][0]['edge_class'], 'direct_call')
        self.assertEqual(refs['heuristic_candidate']['evidence'][0]['edge_class'], 'code_address_reference')
        self.assertEqual(refs['dispatcher_candidate']['evidence'][0]['edge_class'], 'rtti_vtable_reference')
        self.assertTrue(all(item['observed_in_bounded_graph'] for item in refs.values()))

        broken = graph_fixture()
        broken['nodes'][0]['direct_edges'].append({
            'instruction_rva': '0x1',
            'target_rva': '0x2',
            'kind': 'indirect_call',
        })
        with self.assertRaises(Error):
            mod.validate_graph(broken)

    def test_selected_region_partial_decode_fails_closed(self):
        graph = graph_fixture(full=False)
        mod.validate_graph(graph)
        with self.assertRaises(Error):
            mod.select_regions(graph, {'0x7da740'})

    def test_hash_mismatch_fails_before_output_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'out'
            with patch.object(mod, 'read_input', return_value=(b'wrong', 'fixture.exe')):
                with self.assertRaises(Error):
                    mod.reproduce(Path(directory) / 'input.zip', out)
            self.assertFalse(out.exists())

    def test_reproduce_is_deterministic_and_warns_about_runtime_unknowns(self):
        binary = b'exact-fixture'
        digest = hashlib.sha256(binary).hexdigest()
        graph = graph_fixture(digest)
        callers = {
            'format_version': 1,
            'executable_sha256': digest,
            'confirmed_calls': [],
            'rejected_candidates': [],
            'unresolved_candidates': [],
            'caller_regions': [],
            'warning': 'static only',
        }
        rtti = rtti_fixture(digest)

        class DummyPE:
            pass

        with tempfile.TemporaryDirectory() as directory, \
             patch.object(mod, 'EXPECTED_SHA256', digest), \
             patch.object(mod, 'read_input', return_value=(binary, 'fixture.exe')), \
             patch.object(mod, 'PE', return_value=DummyPE()), \
             patch.object(mod, 'runtime_functions', return_value=[]), \
             patch.object(mod, 'RuntimeFunctionIndex', return_value=object()), \
             patch.object(mod, 'analyze_rtti', return_value=rtti), \
             patch.object(mod, 'build_graph', return_value=graph), \
             patch.object(mod, 'map_callers', return_value=callers):
            first = Path(directory) / 'first'
            second = Path(directory) / 'second'
            mod.reproduce(Path(directory) / 'input.zip', first)
            mod.reproduce(Path(directory) / 'input.zip', second)

            for name in mod.ARTIFACT_NAMES:
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

            doc = json.loads((first / 'modifier-node-callgraph.json').read_text())
            warning = doc['warning'].lower()
            self.assertIn('runtime reachability', warning)
            self.assertIn('optimization benefit', warning)

            selected = json.loads((first / 'modifier-node-selected-regions.json').read_text())
            self.assertEqual(selected['seed']['class_name'], 'CTickTask_RecalculateModifierNodes')
            self.assertTrue(selected['runtime_unverified'])
            self.assertEqual(
                set(selected['edge_classes']),
                {
                    'direct_calls_and_tail_jumps',
                    'indirect_sites',
                    'code_address_references',
                    'rtti_vtable_references',
                },
            )


if __name__ == '__main__':
    unittest.main()
