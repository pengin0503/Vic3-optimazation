#!/usr/bin/env python3
"""Deterministically reproduce exact-build TickTask evidence; no game access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from analyze_vic3 import Error, read_input
from map_hotspot_calls import verify_hash
import map_ticktask_dependencies as dep
from map_ticktask_rtti import analyze_rtti


def json_bytes(doc):
    return (json.dumps(doc,indent=2,sort_keys=True)+'\n').encode('utf-8')


def reproduce(input_path: Path, output_directory: Path, *, rtti_path: Path | None=None, **budgets):
    binary, logical = read_input(input_path,'victoria3.exe')
    actual = verify_hash(binary,dep.EXPECTED_SHA256)
    dep.require_capstone()
    rtti = None
    if rtti_path is not None and rtti_path.exists():
        loaded = json.loads(rtti_path.read_text(encoding='utf-8'))
        if loaded.get('executable_sha256') == actual:
            rtti = loaded
    if rtti is None:
        rtti = analyze_rtti(binary,logical)
    result = dep.analyze_dependency_evidence(binary,logical,rtti,**budgets)
    result['provenance'] = {'input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),
                            'rtti_sha256':hashlib.sha256(json_bytes(rtti)).hexdigest(),
                            'rtti_mode':'reused-matching' if rtti_path is not None and rtti_path.exists() and loaded.get('executable_sha256')==actual else 'regenerated'}
    content = json_bytes(result)
    note = dep.render_markdown(result).encode('utf-8')
    output_directory.mkdir(parents=True,exist_ok=True)
    artifacts = {'ticktask-dependencies-1.14.5.json':content,'ticktask-dependency-static-map.md':note}
    for name,raw in artifacts.items(): (output_directory/name).write_bytes(raw)
    index = {'format_version':1,'executable_sha256':actual,
             'artifacts':{name:hashlib.sha256(raw).hexdigest() for name,raw in artifacts.items()},'provenance':result['provenance']}
    (output_directory/'artifact-index.json').write_bytes(json_bytes(index))
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',nargs='?',type=Path,default=Path(os.environ.get('VIC3_DATA',str(ROOT/'input-data/Vic3_data.zip'))))
    p.add_argument('--output',type=Path,default=ROOT/'research/generated/ticktask-dependency-reproduction')
    p.add_argument('--rtti',type=Path,default=ROOT/'research/generated/pc-evidence-2026-10-05/native/ticktask-rtti.json')
    args=p.parse_args(argv)
    try:
        doc=reproduce(args.input,args.output,rtti_path=args.rtti)
    except (Error,OSError,ValueError) as exc:
        print(f'error: {exc}',file=sys.stderr);return 2
    print(f"{len(doc['functions'])} decoded groups; {len(doc['candidate_dependency_edges'])} relationships; {len(doc['unresolved'])} unresolved records.")
    return 0

if __name__=='__main__': raise SystemExit(main())
