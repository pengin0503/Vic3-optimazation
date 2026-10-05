#!/usr/bin/env python3
"""Reproduce exact-build GameState/UI synchronization candidates; no hooks/writes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))

from analyze_vic3 import Error, PE, read_input
from map_hotspot_calls import verify_hash
from map_sync_callers import enumerate_sync_imports, map_sync_references
from map_ticktask_rtti import runtime_functions
from runtime_function_groups import RuntimeFunctionIndex

EXPECTED_SHA256='9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'
WARNING=(
    'Imported synchronization caller candidates are static evidence only. OS tracing is '
    'required to establish wait duration/causality and whether any candidate corresponds '
    'to a GameState release region. No CScopedGameStateRelease identity is asserted.'
)
ARTIFACT_NAMES=('sync-imports.json','sync-callers.json','artifact-index.json')


def json_bytes(doc):
    return (json.dumps(doc,indent=2,sort_keys=True)+'\n').encode('utf-8')


def file_sha256(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def build_sync_callers_document(mapping:dict, imports:list[dict], *, executable_sha256=EXPECTED_SHA256):
    return {
        'format_version':1,
        'executable_sha256':executable_sha256,
        'candidate_kind':'game_state_sync_candidate',
        'asserted_source_identity':None,
        'cscoped_game_state_release_identity_proven':False,
        'references':mapping.get('references',[]),
        'unresolved_indirect_sites':mapping.get('unresolved_indirect_sites',[]),
        'partial_groups':mapping.get('partial_groups',[]),
        'caller_groups':mapping.get('caller_groups',{}),
        'budgets':mapping.get('budgets',{}),
        'skipped_oversize_group_count':mapping.get('skipped_oversize_group_count',0),
        'sync_import_count':len(imports),
        'runtime_unverified':True,
        'warning':WARNING,
    }


def reproduce(input_path:Path, output_directory:Path):
    binary,logical=read_input(input_path,'victoria3.exe')
    actual=verify_hash(binary,EXPECTED_SHA256)
    pe=PE(binary)
    imports=enumerate_sync_imports(binary,pe)
    index=RuntimeFunctionIndex(binary,pe,runtime_functions(binary,pe))
    mapping=map_sync_references(binary,pe,index,imports)
    if mapping.get('executable_sha256')!=actual:raise Error('sync caller map executable hash mismatch')
    imports_doc={'format_version':1,'executable_sha256':actual,'imports':imports,
                 'runtime_unverified':True,'warning':WARNING}
    callers_doc=build_sync_callers_document(mapping,imports,executable_sha256=actual)
    raw_imports,raw_callers=json_bytes(imports_doc),json_bytes(callers_doc)
    index_doc={'format_version':1,'executable_sha256':actual,
               'artifacts':{'sync-imports.json':hashlib.sha256(raw_imports).hexdigest(),
                            'sync-callers.json':hashlib.sha256(raw_callers).hexdigest()},
               'provenance':{'input_logical_path':logical,
                             'input_container_sha256':file_sha256(input_path) if input_path.is_file() else None}}
    raw_index=json_bytes(index_doc)
    output_directory.mkdir(parents=True,exist_ok=True)
    (output_directory/'sync-imports.json').write_bytes(raw_imports)
    (output_directory/'sync-callers.json').write_bytes(raw_callers)
    (output_directory/'artifact-index.json').write_bytes(raw_index)
    return {'imports':imports_doc,'callers':callers_doc,'index':index_doc}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output_directory',type=Path);args=p.parse_args(argv)
    try:result=reproduce(args.input,args.output_directory)
    except (Error,OSError,ValueError,KeyError,json.JSONDecodeError) as exc:
        print(f'error: {exc}',file=sys.stderr);return 2
    print(f"Mapped {len(result['imports']['imports'])} synchronization imports and {len(result['callers']['references'])} validated static references.")
    return 0


if __name__=='__main__':raise SystemExit(main())
