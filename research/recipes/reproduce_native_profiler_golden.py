#!/usr/bin/env python3
"""Explicit regeneration of synthetic v1 cross-language vectors; no game trace."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import native_profiler_format as fmt
from parse_native_profiler_trace import parse_trace


def reproduce(out):
    metadata={'build_ids':fmt.BUILD_IDS,'profiler_build_id':'synthetic-reference-v1',
              'targets':[{'target_id':1,'name':'SyntheticFunction','kind':'synthetic','ranges':[{'begin_rva':'0x1000','end_rva':'0x1100'}]},
                         {'target_id':2,'name':'SyntheticWait','kind':'synthetic','ranges':[{'begin_rva':'0x2000','end_rva':'0x2100'}]}]}
    header=fmt.encode_header(metadata,qpc_frequency=1000,session_start_qpc=90,executable_sha256=fmt.EXPECTED_SHA256,signature_db_version=1)
    def event(kind,thread,seq,ts,target,**payload):
        return fmt.encode_event({'event_type':kind,'thread_id':thread,'sequence':seq,'timestamp_qpc':ts,'target_id':target,**payload})
    records=[event(1,7,1,100,1,correlation_id=11),
             event(3,7,2,105,1,correlation_id=11,range_begin=10,range_end=20,range_length=10,task_thread_count=16,decision=2,reason_flags=3,chunk_or_work_count=4),
             event(4,7,3,110,2,correlation_id=12,wait_kind=2,object_token=0xabc),
             event(1,8,1,102,1,correlation_id=21),
             event(5,7,4,115,2,correlation_id=12,result_flags=0),
             event(2,8,2,120,1,correlation_id=21,status_flags=0),
             event(2,7,5,130,1,correlation_id=11,status_flags=0),
             event(6,7,6,135,0,counter_id=1,value=0)]
    binary=fmt.encode_trace(header,records)
    parsed=parse_trace(binary)
    if not parsed['header_valid'] or not parsed['segment_complete'] or parsed['diagnostics']:raise ValueError('invalid primary golden trace')
    artifacts={'trace-v1.bin':binary,'trace-v1.json':(json.dumps(parsed,indent=2,sort_keys=True)+'\n').encode('utf-8')}
    out.mkdir(parents=True,exist_ok=True)
    for name,raw in artifacts.items():(out/name).write_bytes(raw)
    hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in artifacts.items()}
    (out/'artifact-index.json').write_text(json.dumps(hashes,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return hashes

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'research/generated/native-profiler-v1-golden')
    print(json.dumps(reproduce(p.parse_args().output),sort_keys=True))
