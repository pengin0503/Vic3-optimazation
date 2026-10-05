#!/usr/bin/env python3
"""Reproduce bounded exact-build ModifierNode static evidence; no hooks/writes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

from analyze_vic3 import Error, PE, read_input
from map_hotspot_calls import build_graph, verify_hash
from map_native_callers import map_callers
from map_ticktask_rtti import analyze_rtti, runtime_functions
from runtime_function_groups import RuntimeFunctionIndex

EXPECTED_SHA256 = '9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'
TASK_CLASS = 'CTickTask_RecalculateModifierNodes'
GRAPH_BUDGETS = {'max_depth': 2, 'max_functions': 80, 'max_function_bytes': 65536}
KNOWN_HELPERS = {
    'heuristic_candidate': 0x7DB150,
    'range_runner_candidate': 0x7DBAA0,
    'dispatcher_candidate': 0x7DC160,
}
WARNING = (
    'Exact-build static instruction/reference evidence only. Direct calls/tail jumps, '
    'indirect sites, code-address references and validated RTTI/vtable references remain '
    'separate. Runtime reachability, critical-path cost, wait causality and optimization '
    'benefit are unproven.'
)
ARTIFACT_NAMES = (
    'modifier-node-callgraph.json',
    'modifier-node-selected-regions.json',
    'artifact-index.json',
)


def json_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + '\n').encode('utf-8')


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_modifier_node_seed(rtti: dict) -> dict:
    matches = [item for item in rtti.get('classes', []) if item.get('name') == TASK_CLASS]
    if len(matches) != 1:
        raise Error(f'expected exactly one RTTI class for {TASK_CLASS}, got {len(matches)}')
    item = matches[0]
    if item.get('vtable_candidate_count') != 1:
        raise Error(f'ambiguous vtable mapping for {TASK_CLASS}')
    tail = item.get('task_specific_tail_vfunc_rva')
    if not isinstance(tail, str) or not tail.startswith('0x'):
        raise Error(f'missing task_specific_tail_vfunc for {TASK_CLASS}')
    return {
        'class_name': TASK_CLASS,
        'resolution': 'rtti_type_name_unique_vtable_task_specific_tail_vfunc',
        'type_descriptor_rva': item.get('type_descriptor_rva'),
        'complete_object_locator_rva': item.get('complete_object_locator_rva'),
        'vtable_rva': item.get('vtable_rva'),
        'task_specific_tail_vfunc_rva': tail,
        'source_method_name': None,
        'runtime_unverified': True,
    }


def validate_graph(graph: dict) -> None:
    required = ('direct_edges', 'indirect_sites', 'code_address_references', 'vtable_address_references')
    for node in graph.get('nodes', []):
        for key in required:
            if key not in node or not isinstance(node[key], list):
                raise Error(f"missing edge class {key} in graph node {node.get('entry_rva')}")
        if any(edge.get('kind') not in ('call', 'tail_jump_candidate') for edge in node['direct_edges']):
            raise Error('direct_edges contains a non-direct edge class')
        if any(site.get('kind') not in ('call', 'jmp') for site in node['indirect_sites']):
            raise Error('indirect_sites contains an invalid transfer class')
        if any(ref.get('kind') != 'code_address_candidate' for ref in node['code_address_references']):
            raise Error('code_address_references contains an invalid evidence class')
        for ref in node['vtable_address_references']:
            if any(slot.get('kind') != 'vtable_slot_candidate' for slot in ref.get('slots', [])):
                raise Error('vtable_address_references contains an invalid slot class')


def select_regions(graph: dict, entry_rvas: set[str]) -> list[dict]:
    by_entry = {node.get('entry_rva'): node for node in graph.get('nodes', [])}
    selected = []
    for entry in sorted(entry_rvas, key=lambda value: int(value, 16)):
        node = by_entry.get(entry)
        if node is None:
            raise Error(f'selected region {entry} is not present in bounded graph')
        if not node.get('fully_decoded') or any(not span.get('fully_decoded') for span in node.get('ranges', [])):
            raise Error(f'partial decode in selected region {entry}')
        selected.append({
            'entry_rva': node['entry_rva'], 'depth': node['depth'],
            'metadata': node['metadata'], 'ranges': node['ranges'],
        })
    return selected


def unresolved_graph_nodes(graph: dict) -> list[dict]:
    out = []
    for node in graph.get('nodes', []):
        if not node.get('fully_decoded') or any(not span.get('fully_decoded') for span in node.get('ranges', [])):
            out.append({'entry_rva': node.get('entry_rva'), 'reason': 'partial_decode',
                        'decoded_bytes': node.get('decoded_bytes'),
                        'metadata_size_bytes': node.get('metadata', {}).get('size_bytes')})
    return out


def classify_known_helper_evidence(graph: dict) -> dict:
    wanted = {rva: name for name, rva in KNOWN_HELPERS.items()}
    found = {name: [] for name in KNOWN_HELPERS}
    for node in graph.get('nodes', []):
        source = node.get('entry_rva')
        node_rva = int(source, 16)
        if node_rva in wanted:
            found[wanted[node_rva]].append({'edge_class': 'decoded_group', 'entry_rva': source})
        for edge in node.get('direct_edges', []):
            target = int(edge['target_rva'], 16)
            if target in wanted:
                found[wanted[target]].append({
                    'edge_class': 'direct_call' if edge['kind'] == 'call' else 'tail_jump',
                    'instruction_rva': edge['instruction_rva'], 'from_entry_rva': source,
                })
        for ref in node.get('code_address_references', []):
            target = int(ref['target_rva'], 16)
            if target in wanted:
                found[wanted[target]].append({
                    'edge_class': 'code_address_reference',
                    'instruction_rva': ref['instruction_rva'], 'from_entry_rva': source,
                })
        for ref in node.get('vtable_address_references', []):
            for slot in ref.get('slots', []):
                target = int(slot['target_rva'], 16)
                if target in wanted:
                    found[wanted[target]].append({
                        'edge_class': 'rtti_vtable_reference',
                        'instruction_rva': ref['instruction_rva'], 'from_entry_rva': source,
                        'vtable_rva': ref.get('vtable_rva'), 'slot': slot.get('slot'),
                    })
    return {
        name: {
            'rva': f'0x{KNOWN_HELPERS[name]:x}',
            'observed_in_bounded_graph': bool(found[name]),
            'evidence': found[name],
        }
        for name in sorted(KNOWN_HELPERS)
    }


def _load_rtti(binary: bytes, logical: str, actual_sha256: str, rtti_path: Path | None):
    if rtti_path is not None and rtti_path.exists():
        loaded = json.loads(rtti_path.read_text(encoding='utf-8'))
        if loaded.get('executable_sha256') != actual_sha256:
            raise Error('RTTI map belongs to a different executable')
        return loaded, 'reused_matching_exact_build'
    regenerated = analyze_rtti(binary, logical)
    if regenerated.get('executable_sha256') != actual_sha256:
        raise Error('regenerated RTTI hash mismatch')
    return regenerated, 'regenerated_exact_build'


def reproduce(input_path: Path, output_directory: Path, *, rtti_path: Path | None = None) -> dict:
    binary, logical = read_input(input_path, 'victoria3.exe')
    actual = verify_hash(binary, EXPECTED_SHA256)
    rtti, rtti_mode = _load_rtti(binary, logical, actual, rtti_path)
    seed = resolve_modifier_node_seed(rtti)
    seed_rva = int(seed['task_specific_tail_vfunc_rva'], 16)

    pe = PE(binary)
    index = RuntimeFunctionIndex(binary, pe, runtime_functions(binary, pe))
    graph = build_graph(binary, pe, index, {TASK_CLASS: seed_rva}, **GRAPH_BUDGETS)
    if graph.get('executable_sha256') != actual:
        raise Error('call graph executable hash mismatch')
    validate_graph(graph)
    callers = map_callers(binary, pe, index, {'modifier_node_task_tail': seed_rva})
    if callers.get('executable_sha256') != actual:
        raise Error('caller map executable hash mismatch')

    graph_doc = dict(graph)
    graph_doc['seed_provenance'] = seed
    graph_doc['known_shared_helper_evidence'] = classify_known_helper_evidence(graph)
    graph_doc['warning'] = WARNING

    selected = {
        'format_version': 1,
        'executable_sha256': actual,
        'seed': seed,
        'graph_budgets': GRAPH_BUDGETS,
        'decoded_group_count': len(graph.get('nodes', [])),
        'decoded_bytes': sum(node.get('decoded_bytes', 0) for node in graph.get('nodes', [])),
        'selected_regions': select_regions(graph, {seed['task_specific_tail_vfunc_rva']}),
        'unresolved_graph_nodes': unresolved_graph_nodes(graph),
        'edge_classes': {
            'direct_calls_and_tail_jumps': 'graph.nodes[].direct_edges',
            'indirect_sites': 'graph.nodes[].indirect_sites',
            'code_address_references': 'graph.nodes[].code_address_references',
            'rtti_vtable_references': 'graph.nodes[].vtable_address_references',
        },
        'known_shared_helper_evidence': classify_known_helper_evidence(graph),
        'direct_caller_evidence': callers,
        'not_expanded': graph.get('not_expanded', {}),
        'runtime_unverified': True,
        'warning': WARNING,
    }

    callgraph_bytes = json_bytes(graph_doc)
    selected_bytes = json_bytes(selected)
    source_container_hash = file_sha256(input_path) if input_path.is_file() else None
    index_doc = {
        'format_version': 1,
        'executable_sha256': actual,
        'artifacts': {
            'modifier-node-callgraph.json': hashlib.sha256(callgraph_bytes).hexdigest(),
            'modifier-node-selected-regions.json': hashlib.sha256(selected_bytes).hexdigest(),
        },
        'provenance': {
            'input_logical_path': logical,
            'input_container_sha256': source_container_hash,
            'rtti_mode': rtti_mode,
            'rtti_sha256': hashlib.sha256(json_bytes(rtti)).hexdigest(),
            'seed_class': TASK_CLASS,
        },
    }
    index_bytes = json_bytes(index_doc)

    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / 'modifier-node-callgraph.json').write_bytes(callgraph_bytes)
    (output_directory / 'modifier-node-selected-regions.json').write_bytes(selected_bytes)
    (output_directory / 'artifact-index.json').write_bytes(index_bytes)
    return {'graph': graph_doc, 'selected': selected, 'index': index_doc}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('output_directory', type=Path)
    p.add_argument('--rtti', type=Path, default=ROOT/'research/generated/pc-evidence-2026-10-05/native/ticktask-rtti.json')
    args = p.parse_args(argv)
    try:
        result = reproduce(args.input, args.output_directory, rtti_path=args.rtti)
    except (Error, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    graph = result['graph']
    print(f"Resolved {TASK_CLASS} from RTTI; {len(graph['nodes'])} decoded groups, {len(graph['not_expanded'])} targets unexpanded.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
