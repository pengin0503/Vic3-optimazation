#!/usr/bin/env python3
"""Address-range correlation only, never bottleneck or wait-cause inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from build_native_target_catalog import canonical_bytes, validated_ranges
from map_ticktask_dependencies import EXPECTED_SHA256
from normalize_os_profile import address, EVENT_TYPES

METRICS=('cpu_time_ns','wait_time_ns','duration_ns','context_switches')


def module_name(value):
    return value.replace('\\','/').rsplit('/',1)[-1].casefold() if isinstance(value,str) else ''


def correlate(profile: dict,catalog: dict,*,expected_run_id: str | None=None) -> dict:
    if profile.get('format_version')!=1 or catalog.get('format_version')!=1:raise ValueError('unsupported format')
    if (profile.get('executable_sha256')!=EXPECTED_SHA256 or catalog.get('executable_sha256')!=EXPECTED_SHA256):
        raise ValueError('build mismatch')
    if not isinstance(profile.get('run_id'),str) or not profile['run_id'] or (expected_run_id is not None and profile['run_id']!=expected_run_id):
        raise ValueError('run mismatch')
    if module_name(catalog.get('module'))!='victoria3.exe':raise ValueError('wrong catalog module')
    targets={};spans=[]
    for t in catalog['targets']:
        tid=t['target_id']
        if type(tid) is not int or tid<1 or tid in targets:raise ValueError('invalid/duplicate target_id')
        targets[tid]=t
        for r in validated_ranges(t['ranges']):spans.append((address(r['begin_rva']),address(r['end_rva']),tid))
    groups={};unmatched=[];invalid=ambiguous=matched=0
    for i,row in enumerate(profile['rows']):
        if not isinstance(row.get('thread_id'),str) or not row['thread_id'].strip() or row.get('event_type') not in EVENT_TYPES:
            raise ValueError('invalid normalized thread/event identity')
        if type(row.get('timestamp_ns')) is not int or row['timestamp_ns']<0:raise ValueError('invalid timestamp')
        if row.get('run_id',profile['run_id'])!=profile['run_id']:raise ValueError('row run mismatch')
        for k in METRICS:
            if k in row and (type(row[k]) is not int or row[k]<0):raise ValueError('invalid normalized metric')
        reason=None;hits=[]
        if module_name(row.get('module'))!='victoria3.exe':reason='wrong_module'
        elif 'instruction_va' not in row or 'module_base' not in row:reason='missing_address'
        else:
            try:
                va,base=address(row['instruction_va']),address(row['module_base'])
                if va<base or va-base>=1<<32:raise ValueError('impossible RVA')
                rva=va-base
                hits=sorted({tid for b,e,tid in spans if b<=rva<e})
            except ValueError:
                reason='invalid_address';invalid+=1
            if reason is None:
                if not hits:reason='no_range'
                elif len(hits)>1:reason='ambiguous_range';ambiguous+=1
        if reason:
            item={'row_index':i,'reason':reason,'thread_id':row['thread_id'],'event_type':row['event_type']}
            if hits:item['target_ids']=hits
            unmatched.append(item);continue
        tid=hits[0];key=(tid,row['thread_id'],row['event_type'],row.get('process',''))
        g=groups.setdefault(key,{'target_id':tid,'name':targets[tid]['name'],'thread_id':row['thread_id'],'event_type':row['event_type'],'count':0})
        if 'process' in row:g['process']=row['process']
        g['count']+=1;matched+=1
        for k in METRICS:
            if k in row:
                g[k]=g.get(k,0)+row[k]
                counts=g.setdefault('metric_observations',{});counts[k]=counts.get(k,0)+1
    return {'format_version':1,'run_id':profile['run_id'],'executable_sha256':EXPECTED_SHA256,
            'source':profile.get('source'),'source_filename':profile.get('source_filename'),
            'profile_canonical_sha256':hashlib.sha256(canonical_bytes(profile)).hexdigest(),
            'catalog_canonical_sha256':hashlib.sha256(canonical_bytes(catalog)).hexdigest(),
            'matched_rows':matched,'unmatched_rows':len(unmatched),'invalid_address_rows':invalid,
            'ambiguous_rows':ambiguous,'unmatched':unmatched,'aggregates':[groups[k] for k in sorted(groups)],
            'warning':'A static range hit is address correlation only; no critical path or wait causality is established.'}


def render_markdown(doc):
    lines=['# OS profile correlation','',f"Run: {doc['run_id']}", '',
           f"Matched: {doc['matched_rows']}; unmatched: {doc['unmatched_rows']}; invalid addresses: {doc['invalid_address_rows']}; ambiguous: {doc['ambiguous_rows']}.",'',doc['warning'],'',
           '| Target | Thread | Event | Rows |','| --- | --- | --- | --- |']
    def clean(s):return str(s).replace('|','\\|').replace('\n',' ').replace('\r',' ')
    lines += [f"| {clean(g['name'])} | {clean(g['thread_id'])} | {g['event_type']} | {g['count']} |" for g in doc['aggregates']]
    return '\n'.join(lines)+'\n'


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('profile',type=Path);p.add_argument('--catalog',required=True,type=Path)
    p.add_argument('--expected-run-id');p.add_argument('--output',required=True,type=Path);p.add_argument('--markdown',type=Path)
    a=p.parse_args(argv)
    try:
        doc=correlate(json.loads(a.profile.read_text(encoding='utf-8')),json.loads(a.catalog.read_text(encoding='utf-8')),expected_run_id=a.expected_run_id)
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        if a.markdown:a.markdown.write_text(render_markdown(doc),encoding='utf-8')
    except (OSError,ValueError,KeyError) as exc:
        print(f'error: {exc}',file=sys.stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
