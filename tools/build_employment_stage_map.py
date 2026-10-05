#!/usr/bin/env python3
"""Build a deterministic exact-build Employment/static scheduler target map."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

EXPECTED_SHA256 = '9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'
WARNING = (
    'Static correlation targets only. Stage labels preserve their evidence provenance and '
    'runtime_unverified=true. A target range is not measured inclusive Employment cost, '
    'runtime reachability, a critical path, wait causality, or optimization benefit.'
)

STAGE_SPECS = {
    'employment.prepare': {
        'name': 'Employment Prepare', 'region': 'employment_prepare',
        'confidence': 'confirmed_static',
        'semantic_evidence': ['rtti_type_name', 'static_control_flow'],
    },
    'employment.collect_continuation': {
        'name': 'CollectEmployment candidate/continuation', 'region': 'employment_collect_continuation',
        'confidence': 'candidate_static',
        'semantic_evidence': ['rtti_type_name', 'static_control_flow'],
    },
    'employment.sort_callback': {
        'name': 'SortEmployment callback', 'region': 'employment_sort_callback',
        'confidence': 'confirmed_static',
        'semantic_evidence': ['rtti_type_name', 'static_control_flow'],
    },
    'employment.item_processing_candidate': {
        'name': 'Employment item-processing candidate', 'region': 'employment_work_item_candidate',
        'confidence': 'candidate_static',
        'semantic_evidence': ['static_control_flow'],
    },
    'shared.dispatcher_candidate': {
        'name': 'Common dispatcher candidate', 'region': 'dispatcher_candidate',
        'confidence': 'candidate_static',
        'semantic_evidence': ['existing_exact_build_recipe', 'static_control_flow'],
    },
    'shared.range_runner_candidate': {
        'name': 'Range runner candidate', 'region': 'range_runner_candidate',
        'confidence': 'candidate_static',
        'semantic_evidence': ['existing_exact_build_recipe', 'static_control_flow'],
    },
    'shared.scheduler_heuristic_candidate': {
        'name': 'Scheduler heuristic candidate', 'region': 'heuristic_candidate',
        'confidence': 'confirmed_static',
        'semantic_evidence': ['source_string', 'static_control_flow'],
    },
}


def render(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + '\n').encode('utf-8')


def _require_exact_build(doc: dict, label: str) -> None:
    if doc.get('format_version') != 1:
        raise ValueError(f'{label}: unsupported format_version')
    if doc.get('executable_sha256') != EXPECTED_SHA256:
        raise ValueError(f'{label}: executable hash mismatch')


def _locations(region: dict) -> list[dict]:
    if not region.get('fully_decoded', True):
        raise ValueError(f"partial region decode: {region.get('entry_rva')}")
    ranges = region.get('metadata', {}).get('ranges') or []
    if not ranges:
        raise ValueError(f"missing selected ranges for {region.get('entry_rva')}")
    out = []
    for span in ranges:
        begin, end = span.get('begin_rva'), span.get('end_rva')
        if not begin or not end or int(begin, 16) >= int(end, 16):
            raise ValueError('invalid region range')
        out.append({'kind': 'range', 'begin_rva': begin, 'end_rva': end})
    return out


def _caller_evidence(callers: dict, entry_rva: str) -> list[dict]:
    return [
        {
            'type': 'static_control_flow',
            'artifact': 'research/generated/dispatch-followup-2026-10-05/scheduler-callers.json',
            'kind': call.get('kind'),
            'caller_root_rva': call.get('caller_root_rva'),
            'instruction_rva': call.get('instruction_rva'),
            'target_rva': call.get('target_rva'),
        }
        for call in callers.get('confirmed_calls', [])
        if call.get('target_rva') == entry_rva
    ]


def validate_stage_map(doc: dict) -> None:
    if doc.get('executable_sha256') != EXPECTED_SHA256 or doc.get('runtime_unverified') is not True:
        raise ValueError('stage map exact-build/runtime-unverified contract violated')
    targets = doc.get('targets', [])
    ids = [item.get('target_id') for item in targets]
    if set(ids) != set(STAGE_SPECS) or len(ids) != len(set(ids)):
        raise ValueError('stage map target set mismatch')
    for item in targets:
        if item.get('confidence') not in {'confirmed_static', 'candidate_static'}:
            raise ValueError('unsupported confidence')
        if item.get('runtime_unverified') is not True:
            raise ValueError('target must remain runtime_unverified')
        if item.get('claims_inclusive_ticktask_cost') is not False:
            raise ValueError('static target must not claim inclusive TickTask cost')
        if not item.get('locations') or not item.get('evidence'):
            raise ValueError('target lacks location/evidence provenance')
        for ev in item['evidence']:
            if ev.get('type') not in {
                'rtti_type_name',
                'static_control_flow',
                'source_string',
                'existing_exact_build_recipe',
            }:
                raise ValueError('unapproved evidence type')


def build_stage_map(dispatch: dict, callers: dict) -> dict:
    _require_exact_build(dispatch, 'dispatch')
    _require_exact_build(callers, 'callers')
    regions = dispatch.get('regions') or {}
    targets = []
    for target_id, spec in sorted(STAGE_SPECS.items()):
        key = spec['region']
        region = regions.get(key)
        if region is None:
            raise ValueError(f'missing source dispatch region: {key}')
        entry = region.get('entry_rva')
        if not entry:
            raise ValueError(f'missing entry RVA for source dispatch region: {key}')
        evidence = [{
            'type': 'existing_exact_build_recipe',
            'artifact': 'research/generated/dispatch-followup-2026-10-05/dispatch-regions.json',
            'region': key,
            'entry_rva': entry,
        }]
        for ev_type in spec['semantic_evidence']:
            if ev_type != 'existing_exact_build_recipe':
                evidence.append({'type': ev_type, 'source_region': key})
        evidence.extend(_caller_evidence(callers, entry))
        targets.append({
            'target_id': target_id,
            'name': spec['name'],
            'source_region': key,
            'confidence': spec['confidence'],
            'locations': _locations(region),
            'evidence': evidence,
            'runtime_unverified': True,
            'claims_inclusive_ticktask_cost': False,
        })
    doc = {
        'format_version': 1,
        'game_version': '1.14.5',
        'executable_sha256': EXPECTED_SHA256,
        'runtime_unverified': True,
        'targets': targets,
        'warning': WARNING,
    }
    validate_stage_map(doc)
    return doc


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dispatch', type=Path, required=True)
    p.add_argument('--callers', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        dispatch = json.loads(args.dispatch.read_text(encoding='utf-8'))
        callers = json.loads(args.callers.read_text(encoding='utf-8'))
        content = render(build_stage_map(dispatch, callers))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(content)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
