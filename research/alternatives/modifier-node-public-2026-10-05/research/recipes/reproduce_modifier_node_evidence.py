#!/usr/bin/env python3
"""Reproduce bounded exact-build static evidence for ModifierNode recalculation.

This recipe is read-only. It resolves the target from MSVC RTTI/class identity,
keeps call/reference classes separate, and does not claim runtime reachability,
critical-path cost, wait causality, or performance benefit.
"""
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
TASK_NAME = 'CTickTask_RecalculateModifierNodes'
KNOWN_SHARED_HELPERS = {
    'dispatcher_candidate': 0x7DC160,
    'range_runner_candidate': 0x7DBAA0,
    'scheduler_heuristic_candidate': 0x7DB150,
}
WARNING = (
    'Exact-build static instruction/reference evidence only. Runtime reachability, '
    'critical-path cost, wait causality, dirty-propagation semantics, and optimization '
    'benefit are not proven.'
)


def json_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + '\n').encode('utf-8')


def resolve_target(rtti: dict, executable_sha256: str) -> dict:
    if rtti.get('executable_sha256') != executable_sha256:
        raise Error('RTTI map belongs to a different executable')
    matches = [c for c in rtti.get('classes', []) if c.get('name') == TASK_NAME]
    if len(matches) != 1 or matches[0].get('vtable_candidate_count') != 1:
        raise Error(f'unmapped/ambiguous TickTask {TASK_NAME}')
    item = matches[0]
    required = ('type_descriptor_rva', 'vtable_rva', 'task_specific_tail_vfunc_rva')
    if any(not item.get(key) for key in required):
        raise Error(f'incomplete RTTI mapping for {TASK_NAME}')
    return item


def edge_inventory(node: dict) -> dict:
    direct_calls, tail_jumps = [], []
    for edge in node.get('direct_edges', []):
        if edge.get('kind') == 'call':
            direct_calls.append(edge)
        elif edge.get('kind') == 'tail_jump_candidate':
            tail_jumps.append(edge)
        else:
            raise Error(f"unknown direct edge kind: {edge.get('kind')}")
    return {
        'direct_calls': direct_calls,
        'tail_jump_candidates': tail_jumps,
        'indirect_call_or_jump_sites': list(node.get('indirect_sites', [])),
        'code_address_references': list(node.get('code_address_references', [])),
        'rtti_vtable_references': list(node.get('vtable_address_references', [])),
    }


def _covered(nodes: list[dict], rva: int) -> bool:
    for node in nodes:
        for span in node.get('ranges', []):
            if int(span['begin_rva'], 16) <= rva < int(span['end_rva'], 16):
                return True
    return False


def unresolved_targets(nodes: list[dict]) -> list[dict]:
    unresolved = {}
    for node in nodes:
        source = node['entry_rva']
        inventory = edge_inventory(node)
        typed = (
            ('direct_call', inventory['direct_calls']),
            ('tail_jump_candidate', inventory['tail_jump_candidates']),
            ('code_address_reference', inventory['code_address_references']),
        )
        for edge_type, edges in typed:
            for edge in edges:
                target = int(edge['target_rva'], 16)
                if not _covered(nodes, target):
                    key = (source, edge['target_rva'], edge_type, edge['instruction_rva'])
                    unresolved[key] = {
                        'source_entry_rva': source,
                        'instruction_rva': edge['instruction_rva'],
                        'target_rva': edge['target_rva'],
                        'edge_type': edge_type,
                        'status': 'not_expanded_by_bounded_graph',
                    }
        for ref in inventory['rtti_vtable_references']:
            for slot in ref.get('slots', []):
                target = int(slot['target_rva'], 16)
                if not _covered(nodes, target):
                    key = (source, slot['target_rva'], 'rtti_vtable_reference', ref['instruction_rva'])
                    unresolved[key] = {
                        'source_entry_rva': source,
                        'instruction_rva': ref['instruction_rva'],
                        'target_rva': slot['target_rva'],
                        'edge_type': 'rtti_vtable_reference',
                        'status': 'not_expanded_by_bounded_graph',
                    }
    return [unresolved[key] for key in sorted(unresolved)]


def select_regions(nodes: list[dict], selected_rvas: list[int]) -> list[dict]:
    selected = []
    by_entry = {int(n['entry_rva'], 16): n for n in nodes}
    for rva in sorted(set(selected_rvas)):
        node = by_entry.get(rva)
        if node is None:
            raise Error(f'selected region 0x{rva:x} is not an expanded graph node')
        if not node.get('fully_decoded') or any(not span.get('fully_decoded') for span in node.get('ranges', [])):
            raise Error(f'selected region 0x{rva:x} is only partially decoded')
        selected.append({
            'entry_rva': node['entry_rva'],
            'depth': node['depth'],
            'metadata': node.get('metadata'),
            'ranges': node.get('ranges', []),
        })
    return selected


def build_documents(rtti_item: dict, graph: dict, callers: dict, *, logical_input: str) -> tuple[dict, dict]:
    nodes = sorted(graph.get('nodes', []), key=lambda n: int(n['entry_rva'], 16))
    seed = int(rtti_item['task_specific_tail_vfunc_rva'], 16)
    normalized_nodes = [{
        'entry_rva': n['entry_rva'],
        'depth': n['depth'],
        'metadata': n.get('metadata'),
        'ranges': n.get('ranges', []),
        'fully_decoded': bool(n.get('fully_decoded')),
        'edges': edge_inventory(n),
    } for n in nodes]
    all_edge_targets = {
        int(e['target_rva'], 16)
        for n in nodes
        for group in (n.get('direct_edges', []), n.get('code_address_references', []))
        for e in group
    }
    helper_status = []
    for name, rva in sorted(KNOWN_SHARED_HELPERS.items()):
        helper_status.append({
            'name': name,
            'rva': f'0x{rva:x}',
            'expanded_in_bounded_graph': _covered(nodes, rva),
            'referenced_by_expanded_edge': rva in all_edge_targets,
        })
    partial = [{
        'entry_rva': n['entry_rva'], 'depth': n['depth'], 'ranges': n.get('ranges', []),
        'status': 'partial_decode_not_selected'
    } for n in nodes if not n.get('fully_decoded')]
    target = {
        'class_name': TASK_NAME,
        'resolution': 'unique_msvc_rtti_vtable',
        'type_descriptor_rva': rtti_item['type_descriptor_rva'],
        'vtable_rva': rtti_item['vtable_rva'],
        'task_specific_tail_vfunc_rva': rtti_item['task_specific_tail_vfunc_rva'],
        'confidence': 'confirmed_static',
        'runtime_unverified': True,
    }
    callgraph = {
        'format_version': 1,
        'executable_sha256': graph['executable_sha256'],
        'logical_input': Path(logical_input).name,
        'target': target,
        'budgets': graph.get('budgets', {}),
        'nodes': normalized_nodes,
        'unresolved_paths': unresolved_targets(nodes),
        'partial_decode_nodes': partial,
        'known_shared_helpers': helper_status,
        'direct_caller_evidence': {
            'scan_scope': callers.get('scan_scope'),
            'raw_candidate_count': callers.get('raw_candidate_count', 0),
            'confirmed_calls': callers.get('confirmed_calls', []),
            'rejected_candidates': callers.get('rejected_candidates', []),
            'unresolved_candidates': callers.get('unresolved_candidates', []),
        },
        'edge_classification': [
            'direct_call', 'tail_jump_candidate', 'indirect_call_or_jump_site',
            'code_address_reference', 'rtti_vtable_reference'
        ],
        'warning': WARNING,
    }
    selected_rvas = [seed] + [
        rva for rva in KNOWN_SHARED_HELPERS.values() if _covered(nodes, rva)
    ]
    selected = {
        'format_version': 1,
        'executable_sha256': graph['executable_sha256'],
        'target': target,
        'selection_rule': 'RTTI-resolved seed plus known shared helpers only when expanded by the bounded graph; partial decodes fail closed.',
        'selected_regions': select_regions(nodes, selected_rvas),
        'partial_decode_nodes_not_selected': partial,
        'warning': WARNING,
    }
    return callgraph, selected


def reproduce(input_path: Path, output_directory: Path, *, rtti_path: Path | None = None) -> tuple[dict, dict]:
    binary, logical = read_input(input_path, 'victoria3.exe')
    actual = verify_hash(binary, EXPECTED_SHA256)  # fail before output creation
    rtti = None
    if rtti_path is not None and rtti_path.exists():
        candidate = json.loads(rtti_path.read_text(encoding='utf-8'))
        if candidate.get('executable_sha256') == actual:
            rtti = candidate
    if rtti is None:
        rtti = analyze_rtti(binary, logical)
    target = resolve_target(rtti, actual)
    seed = int(target['task_specific_tail_vfunc_rva'], 16)
    pe = PE(binary)
    index = RuntimeFunctionIndex(binary, pe, runtime_functions(binary, pe))
    graph = build_graph(binary, pe, index, {TASK_NAME: seed}, max_depth=2,
                        max_functions=80, max_function_bytes=65536)
    callers = map_callers(binary, pe, index, {'modifier_node_seed': seed})
    callgraph, selected = build_documents(target, graph, callers, logical_input=logical)
    artifacts = {
        'modifier-node-callgraph.json': json_bytes(callgraph),
        'modifier-node-selected-regions.json': json_bytes(selected),
    }
    index_doc = {
        'format_version': 1,
        'executable_sha256': actual,
        'artifacts': {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(artifacts.items())},
        'warning': WARNING,
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    for name, raw in artifacts.items():
        (output_directory / name).write_bytes(raw)
    (output_directory / 'artifact-index.json').write_bytes(json_bytes(index_doc))
    return callgraph, selected


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output_directory', type=Path)
    parser.add_argument('--rtti', type=Path,
                        default=ROOT / 'research/generated/pc-evidence-2026-10-05/native/ticktask-rtti.json')
    args = parser.parse_args(argv)
    try:
        callgraph, selected = reproduce(args.input, args.output_directory, rtti_path=args.rtti)
    except (Error, OSError, ValueError, KeyError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    print(f"Resolved {callgraph['target']['class_name']} at {callgraph['target']['task_specific_tail_vfunc_rva']}; "
          f"{len(callgraph['nodes'])} bounded nodes, {len(selected['selected_regions'])} selected fully-decoded regions.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
