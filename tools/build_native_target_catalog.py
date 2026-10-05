#!/usr/bin/env python3
"""Hash-gated static native ranges. Range hits do not establish causality."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from normalize_os_profile import address
from map_ticktask_dependencies import EXPECTED_SHA256, WARNING


def canonical_bytes(doc):
    return json.dumps(doc,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')


def validated_ranges(ranges):
    if not isinstance(ranges,list) or not ranges: raise ValueError('target has no ranges')
    pairs=sorted((address(r['begin_rva']),address(r['end_rva'])) for r in ranges)
    if any(b>=e or e > 1<<32 for b,e in pairs): raise ValueError('invalid RVA range')
    if any(e>b2 for (_,e),(b2,_) in zip(pairs,pairs[1:])): raise ValueError('overlapping ranges within target')
    return [{'begin_rva':hex(b),'end_rva':hex(e)} for b,e in pairs]


def build_catalog(rtti_doc: dict, overrides: dict, *, executable_sha256: str) -> dict:
    if executable_sha256!=EXPECTED_SHA256 or any(d.get('executable_sha256')!=executable_sha256 for d in (rtti_doc,overrides)):
        raise ValueError('executable hash mismatch in catalog inputs')
    entries=[];unresolved=[];names=set()
    identity_sorted_doc={**rtti_doc,'classes':sorted(rtti_doc.get('classes',[]),key=lambda x:x['name'])}
    rtti_hash=hashlib.sha256(canonical_bytes(identity_sorted_doc)).hexdigest()
    for c in sorted(rtti_doc.get('classes',[]),key=lambda x:x['name']):
        name=c['name']
        if name in names: raise ValueError('duplicate target name')
        names.add(name)
        group=c.get('tail_function_group') or {}
        if c.get('vtable_candidate_count')!=1 or group.get('status')!='resolved':
            unresolved.append({'name':name,'reason':'ambiguous_identity_or_unresolved_function_group'});continue
        entries.append({'name':name,'kind':'ticktask_tail','ranges':validated_ranges(group['ranges']),
                        'source_evidence':{'artifact':'research/generated/pc-evidence-2026-10-05/native/ticktask-rtti.json',
                                           'class':name,'rtti_identity_sorted_sha256':rtti_hash},'confidence':'confirmed-static'})
    for t in overrides.get('targets',[]):
        if t['name'] in names or t['name'].startswith('CTickTask_'): raise ValueError('duplicate name or prohibited TickTask override')
        names.add(t['name'])
        if not t.get('source_evidence'): raise ValueError('override requires source_evidence')
        entries.append({'name':t['name'],'kind':t['kind'],'ranges':validated_ranges(t['ranges']),
                        'source_evidence':t['source_evidence'],'confidence':'candidate'})
    entries.sort(key=lambda x:(x['name'],x['kind']))
    for i,t in enumerate(entries,1):t['target_id']=i
    spans=sorted((address(r['begin_rva']),address(r['end_rva']),t['target_id']) for t in entries for r in t['ranges'])
    conflicts=[]
    for i,(b,e,tid) in enumerate(spans):
        for b2,e2,tid2 in spans[i+1:]:
            if b2>=e:break
            if tid!=tid2:conflicts.append({'target_ids':sorted([tid,tid2]),'begin_rva':hex(max(b,b2)),'end_rva':hex(min(e,e2))})
    return {'format_version':1,'executable_sha256':executable_sha256,'module':'victoria3.exe',
            'targets':entries,'range_conflicts':conflicts,'unresolved':unresolved,'warning':WARNING}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rtti',required=True,type=Path);p.add_argument('--overrides',required=True,type=Path)
    p.add_argument('--executable-sha256',required=True);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args(argv)
    try:
        doc=build_catalog(json.loads(a.rtti.read_text(encoding='utf-8')),json.loads(a.overrides.read_text(encoding='utf-8')),executable_sha256=a.executable_sha256)
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    except (OSError,ValueError,KeyError) as exc:
        print(f'error: {exc}',file=sys.stderr);return 2
    return 0

if __name__=='__main__': raise SystemExit(main())
