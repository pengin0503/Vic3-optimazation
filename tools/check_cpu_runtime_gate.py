#!/usr/bin/env python3
"""Read-only Phase 4 evidence audit; completeness is not runtime acceptance."""
from __future__ import annotations

import copy
import argparse
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import statistics
import sys
import tempfile

from native_profiler_format import EXPECTED_SHA256
import check_benchmark_quality as quality
from parse_native_profiler_trace import parse_trace, unique_object, reject_constant
import render_native_profiler_targets as renderer

KINDS = {'static', 'historical', 'synthetic', 'game'}
ROLES = {'source', 'run_manifest', 'ticktask_csv', 'native_trace', 'attach_log',
         'stop_log', 'identity_log', 'loader_binary', 'profiler_binary',
         'os_trace', 'boundary_log', 'review'}
REVIEW_KEYS = {'native_csv_relationship', 'observer_overhead',
               'os_running_ready_waiting', 'save_stability'}
REQUIREMENTS = ('runtime_capture_matrix', 'matched_workload',
                'native_capture_validation', 'os_thread_states', 'runtime_reviews')


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label}: nonempty string required')
    return value


def digest(value, label):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError(f'{label}: lowercase SHA-256 required')
    return value


def confined(root, value):
    text(value, 'path')
    posix, windows = PurePosixPath(value), PureWindowsPath(value)
    if posix.is_absolute() or windows.drive or windows.is_absolute() or '\\' in value or '..' in posix.parts:
        raise ValueError('path must be root-relative without parent traversal')
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError('path escapes evidence root or names the root')
    return path


def file_sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _validate_index(document, root):
    if not isinstance(document, dict) or type(document.get('format_version')) is not int or document['format_version'] != 1:
        raise ValueError('unsupported index format')
    if document.get('executable_sha256') != EXPECTED_SHA256:
        raise ValueError('unsupported executable hash')
    for key, cls in [('artifacts', list), ('reviews', dict), ('hypotheses', list)]:
        if not isinstance(document.get(key), cls):
            raise ValueError(f'{key}: {cls.__name__} required')
    if set(document['reviews']) - REVIEW_KEYS:
        raise ValueError('unknown review requirement')
    if document.get('runs_root') is not None:
        confined(root, document['runs_root'])
    by_id, paths = {}, set()
    for entry in document['artifacts']:
        if not isinstance(entry, dict):
            raise ValueError('artifact object required')
        aid = text(entry.get('id'), 'artifact id')
        path = confined(root, entry.get('path'))
        if aid in by_id or path in paths:
            raise ValueError('duplicate artifact id/path')
        digest(entry.get('sha256'), aid)
        if not isinstance(entry.get('kind'), str) or not isinstance(entry.get('role'), str) or entry['kind'] not in KINDS or entry['role'] not in ROLES:
            raise ValueError('unsupported artifact kind/role')
        text(entry.get('notes'), 'artifact notes')
        by_id[aid] = entry
        paths.add(path)
    hypotheses = set()
    for hypothesis in document['hypotheses']:
        if not isinstance(hypothesis, dict):
            raise ValueError('hypothesis object required')
        hid = text(hypothesis.get('id'), 'hypothesis id')
        if hid in hypotheses:
            raise ValueError('duplicate hypothesis id')
        hypotheses.add(hid)
        for key in ('claim', 'falsification'):
            text(hypothesis.get(key), key)
        refs = hypothesis.get('artifact_ids')
        if not isinstance(refs, list) or not refs or any(not isinstance(a, str) or a not in by_id for a in refs):
            raise ValueError('invalid hypothesis artifact reference')
        if hypothesis.get('runtime_verified') is not False:
            raise ValueError('hypotheses must remain runtime-unverified')
    return by_id


def audit(document: dict, root: Path) -> dict:
    root = Path(root).resolve()
    by_id = _validate_index(document, root)
    inventory, issues = [], []
    for aid, entry in by_id.items():
        item = copy.deepcopy(entry)
        path = confined(root, entry['path'])
        if not path.is_file():
            item['status'] = 'missing'
            issues.append({'code': 'missing_artifact', 'artifact_id': aid})
        else:
            actual = file_sha256(path)
            item.update(actual_sha256=actual, size_bytes=path.stat().st_size)
            item['status'] = 'verified' if actual == entry['sha256'] else 'rejected'
            if item['status'] == 'rejected':
                issues.append({'code': 'artifact_hash_mismatch', 'artifact_id': aid})
        inventory.append(item)
    report = {
        'format_version': 1, 'executable_sha256': EXPECTED_SHA256,
        'index_canonical_sha256': hashlib.sha256(json.dumps(document, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest(),
        'inventory': inventory, 'issues': issues,
        'provenance_valid': bool(inventory) and all(a['status'] == 'verified' for a in inventory),
        'requirements': {k: {'status': 'missing', 'details': []} for k in REQUIREMENTS},
        'runtime_capture_count': 0, 'benchmark_quality': None, 'overhead': None,
        'hypotheses': copy.deepcopy(document['hypotheses']),
        'status': 'blocked', 'performance_patch_authorized': False,
        'interpretation': 'Verified bytes and operator declarations are not proof of game execution or causality; readiness requires runtime review.'}
    _audit_runtime(document, root, report)
    return report


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{label}: integer >= {minimum} required')
    return value


def _manifest_identity(manifest):
    if not isinstance(manifest, dict) or type(manifest.get('format_version')) is not int or manifest['format_version'] != 1:
        raise ValueError('invalid runtime manifest format')
    rid = text(manifest.get('run_id'), 'run_id')
    if type(manifest.get('warmup')) is not bool:
        raise ValueError('warmup must be explicit boolean')
    if manifest['warmup']:
        return rid, None
    if manifest.get('task_thread_count') not in (12, 16) or type(manifest.get('task_thread_count')) is not int:
        raise ValueError('runtime matrix requires 12/16 threads')
    mode = manifest.get('variant')
    if mode not in ('profiler-disabled', 'profiler-enabled'):
        raise ValueError('runtime variant must identify disabled/enabled')
    for key in ('repeat', 'execution_order'):
        integer(manifest.get(key), key, 1)
    if manifest.get('warmup_performed') is not True:
        raise ValueError('warmup_performed must be known true')
    wall = manifest.get('wall_clock_seconds')
    if type(wall) not in (int, float) or not 0 < wall < float('inf'):
        raise ValueError('positive finite wall clock required')
    if manifest.get('build', {}).get('victoria3_exe_sha256') != EXPECTED_SHA256:
        raise ValueError('fresh build identity missing/mismatched')
    save_hash = digest(manifest.get('save', {}).get('sha256'), 'save hash')
    start = date.fromisoformat(text(manifest.get('start_date'), 'start_date'))
    end = date.fromisoformat(text(manifest.get('end_date'), 'end_date'))
    if end <= start:
        raise ValueError('game date interval must be positive')
    speed = integer(manifest.get('game_speed'), 'game_speed', 1)
    if speed > 5:
        raise ValueError('unsupported game_speed')
    pop = text(manifest.get('game_rules', {}).get('pop_consolidation'), 'pop consolidation')
    environment = manifest.get('environment', {})
    camera, ui = (text(environment.get(k), k) for k in ('camera_state', 'ui_state'))
    capture = manifest.get('capture', {})
    if capture.get('identity_verified_at_start') is not True:
        raise ValueError('fresh identity verification required')
    digest(capture.get('ticktask_csv_sha256'), 'TickTask CSV hash')
    native = manifest.get('native_profiler')
    if not isinstance(native, dict) or native.get('capture_kind') != 'game' or native.get('fresh_process') is not True:
        raise ValueError('fresh game process declaration required')
    if native.get('mode') != mode.removeprefix('profiler-'):
        raise ValueError('manifest and native mode differ')
    pid = integer(native.get('pid'), 'PID', 1)
    if pid >= 1 << 32:
        raise ValueError('PID outside uint32')
    launched = datetime.fromisoformat(text(native.get('process_start_utc'), 'process_start_utc'))
    if launched.tzinfo is None or launched.utcoffset() != timedelta(0):
        raise ValueError('UTC process start timestamp required')
    commit = native.get('source_commit')
    if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('profiler source commit required')
    return rid, (save_hash, str(start), str(end), speed, pop, camera, ui, commit, pid, launched.isoformat())


def runtime_csv_path(manifest_path, manifest):
    # Validate the CSV field before joining; Path joining must agree with quality.
    return confined(manifest_path.parent, text(manifest.get('ticktask_csv'), 'CSV path'))


class NativeCounterError(ValueError):
    def __init__(self, counters):
        self.counters = counters
        super().__init__('nonzero native diagnostic counters')


class NativeTraceError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = copy.deepcopy(diagnostics)
        super().__init__('V3PF has incomplete segment or diagnostics')


def _native_check(manifest, ref, expected_table_hash):
    native = manifest['native_profiler']
    for key in ('attach_exit_code', 'stop_exit_code'):
        if type(native.get(key)) is not int or native[key] != 0:
            raise ValueError(f'{key}: successful exit required')
    expected_mask = 0 if native['mode'] == 'disabled' else 7
    attach = ref(native.get('attach_log_artifact_id'), 'attach_log').read_text(encoding='utf-8-sig')
    stop = ref(native.get('stop_log_artifact_id'), 'stop_log').read_text(encoding='utf-8-sig')
    if not re.search(rf'^Profiler ready; enabled mask={expected_mask}; output=.+$', attach, re.MULTILINE):
        raise ValueError('attach log does not confirm ready/mask')
    if 'Profiler stopped and capture finalized. DLL remains loaded and inert.' not in stop:
        raise ValueError('stop log does not confirm finalization')
    if any(marker in attach+stop for marker in ('Attach failed', 'DLL rejected', 'Gate code:', 'Stop/capture finalization failed')):
        raise ValueError('logs contain a failed attach/stop')
    identity = ref(native.get('identity_log_artifact_id'), 'identity_log').read_text(encoding='utf-8-sig').lower()
    if EXPECTED_SHA256 not in identity or manifest['save']['sha256'] not in identity:
        raise ValueError('identity log does not contain initial build/save hashes')
    trace = parse_trace(ref(native.get('trace_artifact_id'), 'native_trace').read_bytes(),
                        expected_executable_sha256=EXPECTED_SHA256)
    if not trace['header_valid'] or not trace['segment_complete'] or trace['diagnostics']:
        raise NativeTraceError(trace['diagnostics'])
    if trace['header']['target_table_hash'] != expected_table_hash:
        raise ValueError('trace target table differs from exact production table')
    # These IDs are emitted by ProfilerRuntime.cpp, independently of parser errors.
    names = {1: 'dropped_events', 3: 'signature_validation_failures', 4: 'thread_buffer_exhaustion'}
    counters = [{'counter_id': e['counter_id'], 'name': names[e['counter_id']], 'value': e['value']}
                for e in trace['events'] if e['event_type'] == 6 and e['counter_id'] in names and e['value'] != 0]
    if counters:
        raise NativeCounterError(counters)
    meta = trace['metadata']
    if type(meta.get('enabled_target_mask')) is not int or meta['enabled_target_mask'] != expected_mask or meta.get('disabled') is not (expected_mask == 0):
        raise ValueError('trace mode/mask differs from requested mode')
    paired = {p['target_id'] for p in trace['pairs'] if p['family'] == 'function'}
    if expected_mask == 7 and paired != {1, 2, 3}:
        raise ValueError('enabled trace lacks one or more target pairs')
    if expected_mask == 0 and any(e['event_type'] in (1, 2, 4, 5) for e in trace['events']):
        raise ValueError('disabled trace contains hook events')
    return trace['summary']


def _os_check(manifest, ref):
    capture = manifest.get('os_capture')
    if not isinstance(capture, dict) or capture.get('exact_boundaries') is not True or capture.get('clock_alignment_verified') is not True:
        raise ValueError('exact synchronized OS boundaries not recorded')
    states = capture.get('states')
    if not isinstance(states, list) or any(not isinstance(s, str) for s in states) or len(states) != 3 or set(states) != {'Running', 'Ready', 'Waiting'}:
        raise ValueError('all three per-thread states required')
    for key in ('dropped_events', 'lost_buffers'):
        if type(capture.get(key)) is not int or capture[key] != 0:
            raise ValueError('OS capture loss must be known zero')
    if integer(capture.get('end_ns'), 'OS end') <= integer(capture.get('begin_ns'), 'OS begin'):
        raise ValueError('positive OS interval required')
    ref(capture.get('trace_artifact_id'), 'os_trace')
    ref(capture.get('boundary_artifact_id'), 'boundary_log')


def _audit_runtime(document, root, report):
    if document.get('runs_root') is None:
        return
    run_root = confined(root, document['runs_root'])
    inventory = {a['id']: a for a in report['inventory']}
    by_path = {confined(root, a['path']): a for a in report['inventory']}
    def issue(code, requirement, **details):
        report['issues'].append({'code': code, 'requirement': requirement, **details})
    def ref(aid, role, *, game=True):
        if not isinstance(aid, str) or aid not in inventory:
            raise ValueError(f'{role}: indexed artifact reference required')
        a = inventory[aid]
        if a['status'] != 'verified' or a['role'] != role or (game and a['kind'] != 'game') or not a.get('size_bytes'):
            raise ValueError(f'{role}: verified nonempty game evidence required')
        return confined(root, a['path'])
    manifests = sorted(run_root.rglob('manifest.json')) if run_root.is_dir() else []
    if not manifests:
        issue('missing_runtime_runs', 'runtime_capture_matrix')
        return
    db = renderer.validate_database(read_json(Path(__file__).resolve().parents[1] / renderer.DEFAULT_INPUT))
    expected_table_hash = hashlib.sha256(renderer.canonical_target_bytes(db)).hexdigest()
    measured, contexts, processes, orders, run_ids = [], set(), set(), set(), set()
    native_ok = os_ok = 0
    quality_safe = True
    for path in manifests:
        a = by_path.get(path.resolve())
        if not a or a['role'] != 'run_manifest':
            issue('unindexed_runtime_manifest', 'runtime_capture_matrix', path=path.relative_to(root).as_posix())
            quality_safe = False; continue
        if a['kind'] != 'game' or a['status'] != 'verified':
            issue('non_game_evidence', 'runtime_capture_matrix', artifact_id=a['id'])
            quality_safe = False; continue
        try:
            manifest = read_json(path)
            rid, context = _manifest_identity(manifest)
            csv_path = runtime_csv_path(path, manifest)
            csv_record = by_path.get(csv_path)
            if not csv_record or csv_record['kind'] != 'game' or csv_record['role'] != 'ticktask_csv' or csv_record['status'] != 'verified':
                raise ValueError('indexed verified game TickTask CSV required')
            if rid in run_ids:
                raise ValueError('duplicate run_id')
            run_ids.add(rid)
            if context is None:
                continue
            native = manifest['native_profiler']
            loader = ref(native.get('loader_artifact_id'), 'loader_binary', game=False)
            dll = ref(native.get('dll_artifact_id'), 'profiler_binary', game=False)
            contexts.add(context[:8]+(file_sha256(loader), file_sha256(dll)))
            process = context[8:]
            if process in processes:
                issue('reused_process_instance', 'runtime_capture_matrix', run_id=rid)
            processes.add(process)
            if manifest['execution_order'] in orders:
                issue('duplicate_execution_order', 'runtime_capture_matrix', run_id=rid)
            orders.add(manifest['execution_order'])
            measured.append(manifest)
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
            issue('invalid_runtime_manifest', 'runtime_capture_matrix', artifact_id=a['id'], message=str(exc))
            quality_safe = False; continue
        try:
            _native_check(manifest, ref, expected_table_hash)
            native_ok += 1
        except (OSError, ValueError, TypeError, KeyError) as exc:
            details = {'diagnostic_counters': exc.counters} if isinstance(exc, NativeCounterError) else {}
            if isinstance(exc, NativeTraceError):
                details['parser_diagnostics'] = exc.diagnostics
            issue('native_capture_invalid', 'native_capture_validation', run_id=rid, message=str(exc), **details)
        try:
            _os_check(manifest, ref)
            os_ok += 1
        except (OSError, ValueError, TypeError, KeyError) as exc:
            issue('os_evidence_incomplete', 'os_thread_states', run_id=rid, message=str(exc))
    report['runtime_capture_count'] = len(measured)
    if len(contexts) > 1:
        issue('comparison_context_mismatch', 'matched_workload')
    grouped = {}
    for m in measured:
        grouped.setdefault((m['task_thread_count'], m['variant']), []).append(m)
    for threads in (12, 16):
        sets = []
        for mode in ('profiler-disabled', 'profiler-enabled'):
            rows = grouped.get((threads, mode), [])
            repeats = [m['repeat'] for m in rows]
            if len(repeats) < 3 or len(set(repeats)) != len(repeats) or set(repeats) != set(range(1, len(repeats)+1)):
                issue('invalid_repeat_matrix', 'runtime_capture_matrix', threads=threads, mode=mode)
            sets.append(set(repeats))
        if sets[0] != sets[1]:
            issue('unmatched_repeat_matrix', 'runtime_capture_matrix', threads=threads)
        ordered = sorted((m for m in measured if m['task_thread_count'] == threads), key=lambda m: m['execution_order'])
        if any(a['variant'] == b['variant'] for a, b in zip(ordered, ordered[1:])):
            issue('non_alternating_modes', 'runtime_capture_matrix', threads=threads)
    if quality_safe:
        try:
            q = quality.check(run_root)
            # Root-relative paths keep reports portable and reproducible.
            for row in q['errors']+q['warnings']:
                if 'path' in row:
                    row['path'] = Path(row['path']).relative_to(root).as_posix()
                issue(row['code'], 'matched_workload', quality_issue=copy.deepcopy(row))
            for boundary in q['workload_boundaries']:
                if not boundary['warmup'] and (boundary['row_count'] == 0 or boundary['frame_count'] == 0):
                    issue('empty_measured_workload', 'matched_workload', run_id=boundary['run_id'])
            report['benchmark_quality'] = q
        except (quality.Error, OSError, ValueError, TypeError, KeyError) as exc:
            issue('benchmark_quality_invalid', 'matched_workload', message=str(exc))
    else:
        issue('benchmark_quality_unavailable', 'matched_workload')
    comparable = (native_ok == len(measured) and len(contexts) == 1 and
                  report['benchmark_quality'] is not None and report['benchmark_quality']['valid_for_performance_claim'] and
                  not any(i.get('requirement') in ('runtime_capture_matrix', 'matched_workload', 'native_capture_validation') for i in report['issues']))
    if comparable and all(len(grouped.get((t, mode), [])) >= 3 for t in (12, 16) for mode in ('profiler-disabled', 'profiler-enabled')):
        report['overhead'] = []
        for threads in (12, 16):
            disabled = [m['wall_clock_seconds'] for m in grouped[(threads, 'profiler-disabled')]]
            enabled = [m['wall_clock_seconds'] for m in grouped[(threads, 'profiler-enabled')]]
            dm, em = statistics.median(disabled), statistics.median(enabled)
            report['overhead'].append({'threads': threads, 'disabled_median_seconds': dm,
                'enabled_median_seconds': em, 'median_overhead_fraction': (em-dm)/dm,
                'disabled_wall_clock_cv': statistics.stdev(disabled)/statistics.mean(disabled),
                'interpretation': 'Descriptive only; review noise, ordering and matched boundaries before acceptance.'})
    expected_ids = {m['run_id'] for m in measured}
    for key in sorted(REVIEW_KEYS):
        review = document['reviews'].get(key)
        if review is None:
            issue('runtime_review_incomplete', 'runtime_reviews', review=key, message='missing review')
            continue
        try:
            if not isinstance(review, dict) or review.get('accepted') is not True:
                raise ValueError('explicit accepted review required')
            ref(review.get('artifact_id'), 'review')
            text(review.get('notes'), 'review notes')
            ids = review.get('run_ids')
            if not isinstance(ids, list) or any(not isinstance(r, str) for r in ids) or len(ids) != len(set(ids)) or not expected_ids or set(ids) != expected_ids:
                raise ValueError('review must cover exactly every measured run ID')
            scope = {a['id']: a['sha256'] for a in report['inventory'] if a['role'] != 'review'}
            if review.get('evidence_sha256') != scope:
                raise ValueError('review must bind the exact non-review evidence bytes')
        except (OSError, ValueError, TypeError) as exc:
            issue('runtime_review_incomplete', 'runtime_reviews', review=key, message=str(exc))
    for key in REQUIREMENTS:
        failures = [i['code'] for i in report['issues'] if i.get('requirement') == key]
        complete = bool(measured)
        if key == 'native_capture_validation':complete = complete and native_ok == len(measured)
        if key == 'os_thread_states':complete = complete and os_ok == len(measured)
        if key == 'matched_workload':complete = complete and report['benchmark_quality'] is not None
        report['requirements'][key] = {'status': 'rejected' if failures else 'satisfied' if complete else 'missing', 'details': failures}
    if report['provenance_valid'] and not report['issues'] and all(r['status'] == 'satisfied' for r in report['requirements'].values()):
        report['status'] = 'ready_for_review'


def _check_output_alias(output, source, document, root):
    sources = [source.resolve()] + [confined(root, a['path']) for a in document['artifacts']]
    # Protect the same per-run CSVs quality would consume, before any output write.
    # Unsafe raw CSV fields are invalid CLI input, even if an indexed shadow exists.
    for entry in document['artifacts']:
        if entry['role'] != 'run_manifest':
            continue
        path = confined(root, entry['path'])
        if not path.is_file():
            continue
        try:
            manifest = read_json(path)
        except ValueError:
            continue  # audit reports malformed runtime JSON as blocked.
        if isinstance(manifest, dict) and isinstance(manifest.get('ticktask_csv'), str):
            sources.append(runtime_csv_path(path, manifest))
    resolved = output.resolve()
    if any(resolved == p or (output.exists() and p.exists() and output.samefile(p)) for p in sources):
        raise ValueError('output aliases an evidence input')
    if document.get('runs_root') is not None and resolved.is_relative_to(confined(root, document['runs_root'])):
        raise ValueError('output may not be inside the source run directory')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    temporary = None
    try:
        document = read_json(args.index)
        _validate_index(document, args.root)
        _check_output_alias(args.output, args.index, document, args.root)
        report = audit(document, args.root)
        report['index_sha256'] = file_sha256(args.index)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=args.output.parent,
                                         prefix='.phase4-', suffix='.tmp', delete=False) as f:
            temporary = Path(f.name)
            f.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n')
        os.replace(temporary, args.output)
        return 0 if report['status'] == 'ready_for_review' else 1
    except (OSError, ValueError, TypeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
