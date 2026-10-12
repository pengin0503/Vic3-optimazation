import copy
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_cpu_runtime_gate as gate
import native_profiler_format as fmt
import render_native_profiler_targets as renderer


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

    def test_rejects_absolute_and_parent_escape(self):
        doc = index(); artifact(self.root, doc, 'a')
        for path in ('../outside', str(self.root / 'a')):
            bad = copy.deepcopy(doc); bad['artifacts'][0]['path'] = path
            with self.assertRaises(ValueError):
                gate.audit(bad, self.root)

    def test_rejects_symlink_escape(self):
        doc = index(); artifact(self.root, doc, 'a')
        with tempfile.TemporaryDirectory() as td:
            try:
                (self.root / 'escape').symlink_to(Path(td), target_is_directory=True)
            except OSError as error:
                if getattr(error, 'winerror', None) in (5, 1314):
                    self.skipTest(f'Windows symlink creation unavailable: {error}')
                raise
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


def runtime_bundle(root):
    """Owned positive fixture, never a captured game dataset."""
    doc = index(); doc['runs_root'] = 'runs'
    loader = artifact(root, doc, 'bin/loader.exe', b'owned loader', kind='synthetic', role='loader_binary')
    dll = artifact(root, doc, 'bin/profiler.dll', b'owned DLL', kind='synthetic', role='profiler_binary')
    db_path = Path(__file__).resolve().parents[1] / 'research/native-profiler-runtime-targets-1.14.5.json'
    targets = renderer.trace_targets(renderer.validate_database(json.loads(db_path.read_text())))
    run_ids = []
    for threads in (12, 16):
        for repeat in (1, 2, 3):
            for mode in ('disabled', 'enabled'):
                order = len(run_ids) + 1
                rid = f't{threads}-{mode}-r{repeat}'; run_ids.append(rid)
                base = 'runs/' + rid + '/'
                def add(name, data, role):
                    return artifact(root, doc, base + name, data, kind='game', role=role)
                csv_id = add('ticktask_timings.csv',
                    b'frame,task,milliseconds,calls,longest_lock\n10,A,1,1,0\n11,B,1,2,0\n', 'ticktask_csv')
                mask = 7 if mode == 'enabled' else 0
                meta = {'build_ids': fmt.BUILD_IDS, 'profiler_build_id': 'read-only-prototype-v1',
                        'disabled': mode == 'disabled', 'enabled_target_mask': mask, 'targets': targets}
                events = []
                if mask:
                    for tid in (1, 2, 3):
                        common = {'thread_id': 7, 'target_id': tid, 'correlation_id': tid}
                        events += [fmt.encode_event(dict(common, event_type=1, sequence=tid*2-1, timestamp_qpc=100+tid*10)),
                                   fmt.encode_event(dict(common, event_type=2, sequence=tid*2, timestamp_qpc=105+tid*10, status_flags=0))]
                header = fmt.encode_header(meta, qpc_frequency=1000, session_start_qpc=90,
                    executable_sha256=fmt.EXPECTED_SHA256, signature_db_version=1)
                native = {'capture_kind': 'game', 'mode': mode, 'source_commit': 'c'*40,
                          'fresh_process': True, 'pid': 1000+order,
                          'process_start_utc': f'2026-10-12T00:00:{order:02d}+00:00',
                          'loader_artifact_id': loader, 'dll_artifact_id': dll,
                          'attach_exit_code': 0, 'stop_exit_code': 0,
                          'identity_log_artifact_id': add('identity.log',
                              (fmt.EXPECTED_SHA256+'\n'+'b'*64+'\n').encode(), 'identity_log'),
                          'attach_log_artifact_id': add('attach.log', f'Profiler ready; enabled mask={mask}; output=fixture.v3pf\n'.encode(), 'attach_log'),
                          'stop_log_artifact_id': add('stop.log', b'Profiler stopped and capture finalized. DLL remains loaded and inert.\n', 'stop_log'),
                          'trace_artifact_id': add('trace.v3pf', fmt.encode_trace(header, events), 'native_trace')}
                os_capture = {'trace_artifact_id': add('os.etl', b'owned raw OS stand-in', 'os_trace'),
                              'boundary_artifact_id': add('boundaries.log', b'owned exact clock alignment evidence', 'boundary_log'),
                              'exact_boundaries': True, 'clock_alignment_verified': True,
                              'states': ['Running', 'Ready', 'Waiting'], 'dropped_events': 0,
                              'lost_buffers': 0, 'begin_ns': 1000, 'end_ns': 2000}
                manifest = {'format_version': 1, 'run_id': rid, 'variant': 'profiler-'+mode,
                            'task_thread_count': threads, 'repeat': repeat, 'warmup': False,
                            'warmup_performed': True, 'execution_order': order,
                            'wall_clock_seconds': 10+repeat*.01+(0.002 if mask else 0),
                            'start_date': '1911-03-01', 'end_date': '1911-06-01', 'game_speed': 5,
                            'build': {'victoria3_exe_sha256': fmt.EXPECTED_SHA256},
                            'save': {'sha256': 'b'*64}, 'game_rules': {'pop_consolidation': 'aggressive_consolidation'},
                            'environment': {'camera_state': 'fixed', 'ui_state': 'fixed'},
                            'capture': {'ticktask_csv_sha256': next(a['sha256'] for a in doc['artifacts'] if a['id']==csv_id),
                                        'identity_verified_at_start': True},
                            'ticktask_csv': 'ticktask_timings.csv', 'native_profiler': native, 'os_capture': os_capture}
                add('manifest.json', json.dumps(manifest).encode(), 'run_manifest')
    for key in sorted(gate.REVIEW_KEYS):
        aid = artifact(root, doc, 'reviews/'+key+'.md', b'Owned review of owned fixtures; not game evidence.', kind='game', role='review')
        doc['reviews'][key] = {'artifact_id': aid, 'accepted': True, 'run_ids': run_ids[:],
                              'evidence_sha256': {a['id']: a['sha256'] for a in doc['artifacts'] if a['role']!='review'},
                              'notes': 'explicit owned test review, not actual game acceptance'}
    return doc


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.doc = runtime_bundle(self.root)
        self.manifest_path = 'runs/t12-disabled-r1/manifest.json'

    def change_manifest(self, edit, path=None):
        path = path or self.manifest_path
        p = self.root / path; manifest = json.loads(p.read_text()); edit(manifest)
        p.write_text(json.dumps(manifest))
        next(a for a in self.doc['artifacts'] if a['path']==path)['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()

    def report(self):
        return gate.audit(self.doc, self.root)

    def assert_blocked(self, code):
        report = self.report()
        self.assertEqual(report['status'], 'blocked')
        self.assertIn(code, {x['code'] for x in report['issues']})
        return report

    def test_owned_complete_bundle_is_ready_for_review_never_patch_authorization(self):
        result = self.report()
        self.assertEqual(result['status'], 'ready_for_review')
        self.assertEqual(result['issues'], [])
        self.assertEqual(result['runtime_capture_count'], 12)
        self.assertTrue(all(x['status']=='satisfied' for x in result['requirements'].values()))
        self.assertFalse(result['performance_patch_authorized'])
        self.assertAlmostEqual(result['overhead'][0]['median_overhead_fraction'], 0.002/10.02)

    def test_synthetic_manifest_cannot_become_game_evidence(self):
        next(a for a in self.doc['artifacts'] if a['path']==self.manifest_path)['kind'] = 'synthetic'
        self.assert_blocked('non_game_evidence')

    def test_capture_identity_warmup_and_context_are_required(self):
        for edit in [lambda m:m['save'].update(sha256=None),
                     lambda m:m.update(warmup_performed=None),
                     lambda m:m['environment'].update(camera_state=None),
                     lambda m:m['native_profiler'].update(fresh_process=False)]:
            with self.subTest(edit=edit):
                self.doc = runtime_bundle(self.root); self.change_manifest(edit)
                self.assert_blocked('invalid_runtime_manifest')

    def test_context_and_profiler_source_must_match_across_runs(self):
        self.change_manifest(lambda m:m['environment'].update(ui_state='different'))
        self.assert_blocked('comparison_context_mismatch')

    def test_attach_and_stop_failure_cannot_be_hidden_by_valid_trace(self):
        for key in ('attach_exit_code', 'stop_exit_code'):
            with self.subTest(key=key):
                self.doc = runtime_bundle(self.root)
                self.change_manifest(lambda m:m['native_profiler'].update({key:4}))
                self.assert_blocked('native_capture_invalid')

    def test_incorrect_log_is_rejected_even_with_success_exit_code(self):
        a = next(a for a in self.doc['artifacts'] if a['role']=='stop_log')
        (self.root/a['path']).write_bytes(b'Stop/capture finalization failed; status 8.\n')
        a['sha256'] = hashlib.sha256((self.root/a['path']).read_bytes()).hexdigest()
        self.assert_blocked('native_capture_invalid')

    def test_trace_drops_broken_pairs_mask_and_target_table_are_rejected(self):
        p = 'runs/t12-enabled-r1/trace.v3pf'
        a = next(a for a in self.doc['artifacts'] if a['path']==p)
        raw = (self.root/p).read_bytes()
        import struct
        for replacement in ('drops', 'truncated', 'no-target3', 'mask', 'target-hash', 'wrong-exact-table'):
            with self.subTest(replacement=replacement):
                b = bytearray(raw)
                if replacement=='drops':struct.pack_into('<Q', b, 104, 1)
                elif replacement=='truncated':b = b[:-1]
                elif replacement=='no-target3':b = b[:-72]
                elif replacement=='target-hash':b[68] ^= 1
                elif replacement=='wrong-exact-table':
                    meta = copy.deepcopy(gate.parse_trace(raw)['metadata'])
                    meta['targets'][0]['name'] = 'other valid target identity'
                    header_size = struct.unpack_from('<H', raw, 6)[0]
                    b = fmt.encode_header(meta, qpc_frequency=1000, session_start_qpc=90,
                        executable_sha256=fmt.EXPECTED_SHA256, signature_db_version=1)+raw[header_size:]
                else:b = b.replace(b'"enabled_target_mask":7', b'"enabled_target_mask":3')
                (self.root/p).write_bytes(b); a['sha256'] = hashlib.sha256(b).hexdigest()
                self.assert_blocked('native_capture_invalid')

    def test_rejected_trace_preserves_structured_parser_diagnostics(self):
        import struct
        path = 'runs/t12-enabled-r1/trace.v3pf'
        for damage in ('truncated', 'dropped'):
            with self.subTest(damage=damage):
                self.doc = runtime_bundle(self.root)
                raw = bytearray((self.root/path).read_bytes())
                if damage == 'truncated':
                    raw = raw[:-1]
                else:
                    struct.pack_into('<Q', raw, 104, 3)
                (self.root/path).write_bytes(raw)
                next(a for a in self.doc['artifacts'] if a['path']==path)['sha256'] = hashlib.sha256(raw).hexdigest()
                self.bind_reviews()
                expected = gate.parse_trace(raw)['diagnostics']
                result = self.assert_blocked('native_capture_invalid')
                issue = next(i for i in result['issues'] if i['code']=='native_capture_invalid')
                self.assertEqual(issue.get('parser_diagnostics'), expected)
                self.assertIsNone(result['overhead'])
                self.assertEqual(json.loads(json.dumps(issue))['parser_diagnostics'], expected)

    def test_extra_csv_frame_stays_a_boundary_mismatch(self):
        p = 'runs/t12-disabled-r1/ticktask_timings.csv'
        a = next(a for a in self.doc['artifacts'] if a['path']==p)
        data = (self.root/p).read_bytes()+b'12,A,1,1,0\n'
        (self.root/p).write_bytes(data); a['sha256'] = hashlib.sha256(data).hexdigest()
        self.change_manifest(lambda m:m['capture'].update(ticktask_csv_sha256=a['sha256']))
        self.assertIsNone(self.assert_blocked('workload_boundary_mismatch')['overhead'])

    def test_duplicate_repeat_reused_process_and_non_alternating_order(self):
        for edit, code in [(lambda m:m.update(repeat=2), 'invalid_repeat_matrix'),
                           (lambda m:m['native_profiler'].update(pid=1002,process_start_utc='2026-10-12T00:00:02+00:00'), 'reused_process_instance'),
                           (lambda m:m.update(execution_order=35), 'non_alternating_modes')]:
            with self.subTest(code=code):
                self.doc = runtime_bundle(self.root)
                if code == 'non_alternating_modes':
                    for p in self.root.glob('runs/*/manifest.json'):
                        self.change_manifest(lambda m:m.update(execution_order=m['execution_order']*10), p.relative_to(self.root).as_posix())
                self.change_manifest(edit)
                self.assert_blocked(code)

    def test_os_outer_envelope_missing_state_and_loss_block_readiness(self):
        for fields in ({'exact_boundaries':False}, {'states':['Running','Waiting']}, {'dropped_events':1}):
            with self.subTest(fields=fields):
                self.doc = runtime_bundle(self.root)
                self.change_manifest(lambda m:m['os_capture'].update(fields))
                self.assert_blocked('os_evidence_incomplete')

    def test_review_must_be_accepted_and_cover_all_measured_runs(self):
        for fields in ({'accepted':False}, {'run_ids':['unknown']}, {'notes':''},
                       {'evidence_sha256':{'stale_capture':'0'*64}}):
            with self.subTest(fields=fields):
                self.doc = runtime_bundle(self.root)
                self.doc['reviews']['observer_overhead'].update(fields)
                self.assert_blocked('runtime_review_incomplete')

    def test_unindexed_manifest_and_csv_path_escape_are_rejected(self):
        self.doc['artifacts'] = [a for a in self.doc['artifacts'] if a['path']!=self.manifest_path]
        self.assert_blocked('unindexed_runtime_manifest')
        self.doc = runtime_bundle(self.root)
        self.change_manifest(lambda m:m.update(ticktask_csv='../../../../outside.csv'))
        self.assert_blocked('invalid_runtime_manifest')

    def bind_reviews(self):
        scope = {a['id']: a['sha256'] for a in self.doc['artifacts'] if a['role'] != 'review'}
        for review in self.doc['reviews'].values():
            review['evidence_sha256'] = scope.copy()

    def test_absolute_csv_cannot_read_or_overwrite_external_evidence(self):
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / 'external.csv'
            original = (self.root/'runs/t12-disabled-r1/ticktask_timings.csv').read_bytes()
            outside.write_bytes(original)
            # The old string join validates this shadow, while quality reads outside.
            # A drive colon cannot form this shadow directory on Windows.
            # The malicious absolute manifest and preservation checks still run.
            if os.name != 'nt':
                shadow = 'runs/t12-disabled-r1/' + outside.as_posix().lstrip('/')
                artifact(self.root, self.doc, shadow, original, kind='game', role='ticktask_csv')
            self.change_manifest(lambda m: m.update(ticktask_csv=outside.as_posix()))
            self.bind_reviews()
            result = self.report()
            with self.subTest(audit=True):
                self.assertEqual(result['status'], 'blocked')
                self.assertIn('invalid_runtime_manifest', {x['code'] for x in result['issues']})
            source = self.root/'index.json'; source.write_text(json.dumps(self.doc))
            with contextlib.redirect_stderr(io.StringIO()):
                code = gate.main([str(source), '--root', str(self.root), '--output', str(outside)])
            self.assertEqual(code, 2)
            self.assertEqual(outside.read_bytes(), original)

    def test_csv_drive_relative_and_backslash_paths_are_rejected(self):
        for name in ('C:/outside.csv', 'C:outside.csv', 'folder\\outside.csv'):
            with self.subTest(name=name):
                self.doc = runtime_bundle(self.root)
                # On Linux a colon can name a shadow path; it is a drive on Windows.
                if os.name != 'nt' and '\\' not in name:
                    raw = (self.root/'runs/t12-disabled-r1/ticktask_timings.csv').read_bytes()
                    artifact(self.root, self.doc, 'runs/t12-disabled-r1/'+name, raw,
                             kind='game', role='ticktask_csv')
                self.change_manifest(lambda m:m.update(ticktask_csv=name))
                self.bind_reviews()
                self.assert_blocked('invalid_runtime_manifest')

    def test_production_diagnostic_counters_block_and_keep_values(self):
        for mode in ('disabled', 'enabled'):
            for cid in (1, 3, 4):
                for value in (1, -1):
                    with self.subTest(mode=mode, counter_id=cid, value=value):
                        self.doc = runtime_bundle(self.root)
                        path = f'runs/t12-{mode}-r1/trace.v3pf'
                        p = self.root/path
                        p.write_bytes(p.read_bytes()+fmt.encode_event(dict(event_type=6,
                            counter_id=cid, value=value, target_id=0, thread_id=99,
                            sequence=0, timestamp_qpc=150)))
                        next(a for a in self.doc['artifacts'] if a['path']==path)['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
                        self.bind_reviews()
                        result = self.assert_blocked('native_capture_invalid')
                        row = next(i for i in result['issues'] if i['code']=='native_capture_invalid')
                        self.assertEqual(row['diagnostic_counters'][0]['counter_id'], cid)
                        self.assertEqual(row['diagnostic_counters'][0]['value'], value)

    def test_header_only_csv_cannot_certify_measured_workload_or_overhead(self):
        for a in self.doc['artifacts']:
            if a['role'] != 'ticktask_csv': continue
            (self.root/a['path']).write_bytes(b'frame,task,milliseconds,calls,longest_lock\n')
            a['sha256'] = hashlib.sha256((self.root/a['path']).read_bytes()).hexdigest()
            self.change_manifest(lambda m: m['capture'].update(ticktask_csv_sha256=a['sha256']),
                                 (Path(a['path']).parent/'manifest.json').as_posix())
        self.bind_reviews()
        result = self.assert_blocked('empty_measured_workload')
        self.assertIsNone(result['overhead'])
        self.assertEqual(result['requirements']['matched_workload']['status'], 'rejected')

    def test_missing_measured_repeat_is_explicit_matrix_failure(self):
        (self.root/self.manifest_path).unlink()
        self.assert_blocked('invalid_repeat_matrix')


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'index.json'; self.output = self.root/'report.json'

    def call(self):
        with contextlib.redirect_stderr(io.StringIO()):
            return gate.main([str(self.source), '--root', str(self.root), '--output', str(self.output)])

    def test_blocked_report_is_written_with_exit_one_and_no_fabricated_overhead(self):
        self.source.write_text(json.dumps(index()))
        self.assertEqual(self.call(), 1)
        result = json.loads(self.output.read_text())
        self.assertEqual(result['status'], 'blocked'); self.assertIsNone(result['overhead'])
        self.assertEqual(result['index_sha256'], hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_ready_owned_fixture_cli_exit_zero(self):
        self.source.write_text(json.dumps(runtime_bundle(self.root)))
        self.assertEqual(self.call(), 0)
        self.assertEqual(json.loads(self.output.read_text())['status'], 'ready_for_review')

    def test_invalid_duplicate_json_does_not_replace_previous_report(self):
        self.output.write_bytes(b'previous report')
        for raw in ('{"format_version":1,"format_version":1}', '[]', '{"format_version":NaN}'):
            self.source.write_text(raw)
            self.assertEqual(self.call(), 2)
            self.assertEqual(self.output.read_bytes(), b'previous report')

    def test_refuses_index_and_artifact_output_alias(self):
        doc = index(); artifact(self.root, doc, 'source.log')
        self.source.write_text(json.dumps(doc))
        original = self.source.read_bytes()
        for target in (self.source, self.root/'source.log'):
            self.output = target
            self.assertEqual(self.call(), 2)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual((self.root/'source.log').read_bytes(), b'evidence')

    def test_refuses_hardlink_output_alias(self):
        self.source.write_text(json.dumps(index()))
        original = self.source.read_bytes()
        alias = self.root/'alias.json'
        try:
            os.link(self.source, alias)
        except OSError as error:
            if getattr(error, 'winerror', None) in (5, 1314):
                self.skipTest(f'Windows hardlink creation unavailable: {error}')
            raise
        self.output = alias
        self.assertEqual(self.call(), 2)
        self.assertEqual(self.source.read_bytes(), original)

    def test_report_never_overwrites_unindexed_files_in_run_directory(self):
        doc = runtime_bundle(self.root)
        self.source.write_text(json.dumps(doc))
        self.output = self.root/'runs/operator-notes.txt'
        self.output.write_bytes(b'operator source')
        self.assertEqual(self.call(), 2)
        self.assertEqual(self.output.read_bytes(), b'operator source')

    def test_atomic_write_failure_preserves_old_report_and_cleans_temp(self):
        from unittest.mock import patch
        self.source.write_text(json.dumps(index())); self.output.write_bytes(b'old')
        with patch.object(gate.os, 'replace', side_effect=OSError('disk failure')):
            self.assertEqual(self.call(), 2)
        self.assertEqual(self.output.read_bytes(), b'old')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['index.json','report.json'])


if __name__ == '__main__':
    unittest.main()
