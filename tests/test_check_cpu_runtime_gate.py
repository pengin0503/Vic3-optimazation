import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_cpu_runtime_gate as gate
import native_profiler_format as fmt


def index():
    return {'format_version': 1, 'executable_sha256': fmt.EXPECTED_SHA256,
            'runs_root': None, 'artifacts': [], 'reviews': {}, 'hypotheses': []}


def artifact(root, document, path, data=b'evidence', *, kind='historical', role='source'):
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    record = {'id': path, 'path': path, 'sha256': hashlib.sha256(data).hexdigest(),
              'kind': kind, 'role': role, 'notes': 'owned test fixture'}
    document['artifacts'].append(record)
    return record['id']


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_empty_bundle_is_blocked_and_absent_overhead_is_null(self):
        result = gate.audit(index(), self.root)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['runtime_capture_count'], 0)
        self.assertIsNone(result['overhead'])
        self.assertFalse(result['performance_patch_authorized'])
        self.assertTrue(all(x['status'] == 'missing' for x in result['requirements'].values()))

    def test_verified_historical_and_synthetic_bytes_do_not_fill_runtime(self):
        doc = index()
        for kind in ('static', 'historical', 'synthetic'):
            artifact(self.root, doc, kind, kind=kind)
        result = gate.audit(doc, self.root)
        self.assertTrue(result['provenance_valid'])
        self.assertEqual([x['status'] for x in result['inventory']], ['verified'] * 3)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['runtime_capture_count'], 0)

    def test_missing_and_hash_mismatch_are_recorded_not_success(self):
        doc = index()
        artifact(self.root, doc, 'gone')
        (self.root / 'gone').unlink()
        artifact(self.root, doc, 'changed')
        (self.root / 'changed').write_bytes(b'changed')
        result = gate.audit(doc, self.root)
        self.assertEqual([x['status'] for x in result['inventory']], ['missing', 'rejected'])
        self.assertEqual({x['code'] for x in result['issues']},
                         {'missing_artifact', 'artifact_hash_mismatch'})
        self.assertFalse(result['provenance_valid'])

    def test_rejects_wrong_build_version_and_json_types(self):
        for key, value in [('format_version', True), ('format_version', 2),
                           ('executable_sha256', '0' * 64), ('artifacts', {}),
                           ('reviews', []), ('hypotheses', {})]:
            with self.subTest(key=key, value=value):
                doc = index(); doc[key] = value
                with self.assertRaises(ValueError):
                    gate.audit(doc, self.root)

    def test_rejects_duplicate_ids_and_resolved_paths(self):
        doc = index(); artifact(self.root, doc, 'a')
        for duplicate in (copy.deepcopy(doc['artifacts'][0]),
                          dict(doc['artifacts'][0], id='other')):
            with self.subTest(duplicate=duplicate):
                bad = copy.deepcopy(doc); bad['artifacts'].append(duplicate)
                with self.assertRaises(ValueError):
                    gate.audit(bad, self.root)

    def test_rejects_absolute_parent_and_symlink_escape(self):
        doc = index(); artifact(self.root, doc, 'a')
        for path in ('../outside', str(self.root / 'a')):
            bad = copy.deepcopy(doc); bad['artifacts'][0]['path'] = path
            with self.assertRaises(ValueError):
                gate.audit(bad, self.root)
        with tempfile.TemporaryDirectory() as td:
            (self.root / 'escape').symlink_to(Path(td), target_is_directory=True)
            bad = copy.deepcopy(doc); bad['artifacts'][0]['path'] = 'escape/a'
            with self.assertRaises(ValueError):
                gate.audit(bad, self.root)

    def test_invalid_kind_role_digest_and_empty_notes_are_schema_errors(self):
        doc = index(); artifact(self.root, doc, 'a')
        for key, value in [('kind', 'runtime_verified'), ('role', 'trcae'),
                           ('kind', []), ('role', {}),
                           ('sha256', None), ('sha256', 'x' * 64), ('notes', '')]:
            bad = copy.deepcopy(doc); bad['artifacts'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                gate.audit(bad, self.root)

    def test_hypothesis_preserves_refutation_but_cannot_assert_runtime_truth(self):
        doc = index(); aid = artifact(self.root, doc, 'static')
        h = {'id': 'serial', 'claim': 'A serial section may limit scaling',
             'artifact_ids': [aid], 'falsification': 'Synchronized states show other limits',
             'runtime_verified': False}
        doc['hypotheses'] = [h]
        self.assertEqual(gate.audit(doc, self.root)['hypotheses'], [h])
        for changes in ({'artifact_ids': ['unknown']}, {'falsification': ''},
                        {'runtime_verified': True}):
            bad = copy.deepcopy(doc); bad['hypotheses'][0].update(changes)
            with self.assertRaises(ValueError):
                gate.audit(bad, self.root)

    def test_deterministic_report_does_not_mutate_input(self):
        doc = index(); artifact(self.root, doc, 'a')
        original = copy.deepcopy(doc)
        first = json.dumps(gate.audit(doc, self.root), sort_keys=True)
        self.assertEqual(first, json.dumps(gate.audit(doc, self.root), sort_keys=True))
        self.assertEqual(doc, original)


if __name__ == '__main__':
    unittest.main()
