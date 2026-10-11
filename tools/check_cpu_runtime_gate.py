#!/usr/bin/env python3
"""Read-only Phase 4 evidence audit; completeness is not runtime acceptance."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

from native_profiler_format import EXPECTED_SHA256

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
    return {
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
