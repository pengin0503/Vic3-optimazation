#!/usr/bin/env python3
"""Offline triage of unresolved TickTask static evidence; never infer dependencies."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

EXPECTED_SHA256 = '9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'
WARNING = ('Offline static-evidence triage only: categories and owner ranges do not '
           'prove runtime reachability, TickTask dependencies, critical-path cost, '
           'CPU utilization, lock contention, or performance improvement.')

CATEGORIES = {
    'indirect_call_or_jump': 'indirect_dispatch',
    'no_unwind_metadata': 'metadata_or_decode',
    'incomplete_decode': 'metadata_or_decode',
    'depth_budget': 'bounded_expansion',
    'function_budget': 'bounded_expansion',
    'byte_budget': 'bounded_expansion',
    'ambiguous_ticktask_identity': 'identity',
    'unmapped_ticktask_identity': 'identity',
    'parent_child_dataflow_not_reconstructed': 'structural_dataflow',
}


def _rva(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]+', value):
        raise ValueError(f'invalid RVA: {value!r}')
    result = int(value, 16)
    if result >= (1 << 64):
        raise ValueError('RVA exceeds 64-bit range')
    return result


def build_triage(document: dict) -> dict:
    """Validate versioned exact-build evidence and conservatively annotate gaps."""
    if not isinstance(document, dict):
        raise ValueError('expected JSON object')
    if type(document.get('format_version')) is not int or document['format_version'] != 1:
        raise ValueError('unsupported evidence format')
    if document.get('executable_sha256') != EXPECTED_SHA256:
        raise ValueError('unsupported executable SHA-256')
    for field in ('functions', 'unresolved', 'candidate_dependency_edges'):
        if not isinstance(document.get(field), list):
            raise ValueError(f'{field} must be a list')
    ranges = []
    for function in document['functions']:
        if not isinstance(function, dict) or not isinstance(function.get('ranges'), list):
            raise ValueError('invalid function/ranges record')
        entry = function.get('entry_rva')
        _rva(entry)
        for item in function['ranges']:
            if not isinstance(item, dict):
                raise ValueError('invalid range')
            begin, end = _rva(item.get('begin_rva')), _rva(item.get('end_rva'))
            if begin >= end:
                raise ValueError('invalid half-open function range')
            ranges.append((begin, end, entry))
    for edge in document['candidate_dependency_edges']:
        if not isinstance(edge, dict):
            raise ValueError('invalid dependency evidence record')
    work = []
    counts = Counter()
    for ordinal, record in enumerate(document['unresolved']):
        if not isinstance(record, dict) or not isinstance(record.get('reason'), str) or not record['reason']:
            raise ValueError('invalid unresolved record/reason')
        address = _rva(record['rva']) if 'rva' in record else None
        owners = {entry for begin, end, entry in ranges if address is not None and begin <= address < end}
        item = dict(record)
        item.update(analysis_category=CATEGORIES.get(record['reason'], 'other'),
                    owner_function_rva=next(iter(owners)) if len(owners) == 1 else None,
                    ownership_ambiguous=len(owners) > 1,
                    runtime_verified=False)
        work.append((item, ordinal, address))
        counts[record['reason']] += 1
    work.sort(key=lambda row: (row[0]['analysis_category'],
                               row[2] if row[2] is not None else (1 << 64),
                               row[0]['reason'], row[1]))
    return {
        'format_version': 1,
        'executable_sha256': EXPECTED_SHA256,
        'source_unresolved_count': len(document['unresolved']),
        'input_dependency_edges': len(document['candidate_dependency_edges']),
        'by_reason': dict(sorted(counts.items())),
        'work_items': [item for item, _, _ in work],
        'warning': WARNING,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError('input and output paths must differ')
        raw = args.input.read_bytes()
        doc = json.loads(raw.decode('utf-8'))
        triage = build_triage(doc)
        triage['source_json_sha256'] = hashlib.sha256(raw).hexdigest()
        encoded = (json.dumps(triage, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replacement: a failed write cannot leave truncated evidence.
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode='wb', dir=args.output.parent,
                                             prefix='.ticktask-triage-', delete=False) as tmp:
                tmp_name = tmp.name
                tmp.write(encoded)
            os.replace(tmp_name, args.output)
        finally:
            if tmp_name is not None and os.path.exists(tmp_name):
                os.unlink(tmp_name)
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
