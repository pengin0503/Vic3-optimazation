from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'build_employment_stage_map',
    ROOT / 'tools/build_employment_stage_map.py',
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def region(entry, end):
    return {
        'entry_rva': entry,
        'metadata': {
            'status': 'resolved',
            'ranges': [{'begin_rva': entry, 'end_rva': end}],
        },
        'ranges': [{
            'begin_rva': entry,
            'end_rva': end,
            'fully_decoded': True,
            'size_bytes': int(end, 16) - int(entry, 16),
        }],
    }


def fixtures():
    digest = mod.EXPECTED_SHA256
    dispatch = {
        'format_version': 1,
        'executable_sha256': digest,
        'regions': {
            'employment_prepare': region('0x13b8310', '0x13b853b'),
            'employment_collect_continuation': region('0x13cada0', '0x13cae91'),
            'employment_sort_callback': region('0x13cad10', '0x13cad62'),
            'employment_work_item_candidate': region('0x10befb0', '0x10bf094'),
            'dispatcher_candidate': region('0x7dc160', '0x7dc606'),
            'range_runner_candidate': region('0x7dbaa0', '0x7dc13e'),
            'heuristic_candidate': region('0x7db150', '0x7dba91'),
        },
    }
    callers = {
        'format_version': 1,
        'executable_sha256': digest,
        'targets': {
            'dispatcher_candidate': '0x7dc160',
            'range_runner_candidate': '0x7dbaa0',
            'heuristic_candidate': '0x7db150',
        },
        'confirmed_calls': [
            {
                'instruction_rva': '0x7dc412',
                'caller_root_rva': '0x7dc160',
                'target_rva': '0x7dbaa0',
                'kind': 'decoded_direct_call',
            },
            {
                'instruction_rva': '0x7dbde0',
                'caller_root_rva': '0x7dbaa0',
                'target_rva': '0x7db150',
                'kind': 'decoded_direct_call',
            },
        ],
    }
    return dispatch, callers


class EmploymentStageMapTests(unittest.TestCase):
    def test_builder_requires_expected_stages_provenance_and_runtime_unverified(self):
        dispatch, callers = fixtures()
        doc = mod.build_stage_map(dispatch, callers)
        by_id = {item['target_id']: item for item in doc['targets']}
        self.assertEqual(set(by_id), set(mod.STAGE_SPECS))
        for target in by_id.values():
            self.assertTrue(target['runtime_unverified'])
            self.assertIn(target['confidence'], {'confirmed_static', 'candidate_static'})
            self.assertTrue(target['locations'])
            self.assertTrue(target['evidence'])
            self.assertFalse(target['claims_inclusive_ticktask_cost'])
        self.assertEqual(by_id['employment.prepare']['locations'][0]['begin_rva'], '0x13b8310')

    def test_wrong_hash_and_missing_source_region_fail_closed(self):
        dispatch, callers = fixtures()
        dispatch['executable_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            mod.build_stage_map(dispatch, callers)

        dispatch, callers = fixtures()
        del dispatch['regions']['employment_sort_callback']
        with self.assertRaises(ValueError):
            mod.build_stage_map(dispatch, callers)

    def test_validator_rejects_total_employment_cost_claim(self):
        dispatch, callers = fixtures()
        doc = mod.build_stage_map(dispatch, callers)
        target = next(item for item in doc['targets'] if item['target_id'] == 'employment.prepare')
        target['claims_inclusive_ticktask_cost'] = True
        with self.assertRaises(ValueError):
            mod.validate_stage_map(doc)

    def test_output_is_byte_deterministic(self):
        dispatch, callers = fixtures()
        first = mod.render(mod.build_stage_map(dispatch, callers))
        second = mod.render(mod.build_stage_map(dispatch, callers))
        self.assertEqual(first, second)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'dispatch.json').write_text(json.dumps(dispatch))
            (root / 'callers.json').write_text(json.dumps(callers))
            self.assertEqual(
                mod.main([
                    '--dispatch', str(root / 'dispatch.json'),
                    '--callers', str(root / 'callers.json'),
                    '--output', str(root / 'out.json'),
                ]),
                0,
            )
            self.assertEqual((root / 'out.json').read_bytes(), first)


if __name__ == '__main__':
    unittest.main()
