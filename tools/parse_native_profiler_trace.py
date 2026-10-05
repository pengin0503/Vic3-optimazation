#!/usr/bin/env python3
"""Strict offline v1 parser. File order retained; pairs are thread-local."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import native_profiler_format as fmt


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate JSON key')
        result[key]=value
    return result


def reject_constant(value):raise ValueError('nonfinite JSON number')


def parse_trace(data: bytes,*,expected_executable_sha256: str | None=None) -> dict:
    doc={'header':{},'metadata':{},'header_valid':False,'segment_complete':False,'events':[],
         'pairs':[],'diagnostics':[],'summary':{'record_count':0,'known_event_count':0,
         'paired_functions':0,'paired_waits':0,'dropped_events':0,'bytes_consumed':0}}
    diagnostics=doc['diagnostics'];summary=doc['summary']
    def report(kind,offset,**details):diagnostics.append({'kind':kind,'offset':offset,**details})
    if len(data)<112:
        report('truncated_header',0);return doc
    magic,version,hbytes,pointer,freq,start,digest,signature,target_hash,flags,drops=fmt.HEADER.unpack_from(data)
    doc['header']={'magic':magic.decode('ascii',errors='replace'),'format_version':version,'header_bytes':hbytes,
                   'pointer_size':pointer,'qpc_frequency':freq,'session_start_qpc':start,
                   'executable_sha256':digest.hex(),'signature_db_version':signature,
                   'target_table_hash':target_hash.hex(),'flags':flags,'total_dropped_events':drops}
    summary['dropped_events']=drops
    if magic!=fmt.MAGIC or pointer!=8 or data[9:16]!=b'\0'*7 or freq==0:
        report('invalid_header',0);return doc
    if version!=fmt.FORMAT_VERSION:
        report('unsupported_format_version',4,version=version);return doc
    if hbytes<112 or hbytes%8:
        report('invalid_header_bytes',6);return doc
    if hbytes>len(data):
        report('truncated_header',6);return doc
    if digest.hex()!=fmt.EXPECTED_SHA256 or (expected_executable_sha256 is not None and digest.hex()!=expected_executable_sha256) or signature!=fmt.SIGNATURE_DB_VERSION:
        report('build_mismatch',32);return doc
    extension=data[112:hbytes];raw=extension.rstrip(b'\0')
    try:
        if not raw or len(extension)-len(raw)>7:raise ValueError('invalid metadata padding')
        metadata=json.loads(raw.decode('utf-8'),object_pairs_hook=unique_object,parse_constant=reject_constant)
        if not isinstance(metadata,dict) or 'targets' not in metadata:raise ValueError('invalid metadata object')
        doc['metadata']=metadata
        if hashlib.sha256(fmt.canonical_target_bytes(metadata['targets'])).digest()!=target_hash:
            report('target_table_hash_mismatch',68);return doc
        target_ids=fmt.validate_metadata(metadata)
    except (UnicodeError,ValueError,TypeError,KeyError) as exc:
        kind='build_mismatch' if 'build ID mismatch' in str(exc) else 'invalid_target_metadata'
        report(kind,112,reason=str(exc));return doc
    doc['header_valid']=True;summary['bytes_consumed']=hbytes
    if drops:report('dropped_events',104,count=drops)
    previous_seq={};previous_time={};pending={};blocked=set();offset=hbytes
    while offset<len(data):
        if len(data)-offset<24:
            report('truncated_record',offset);break
        timestamp,thread,kind,size,target,sequence=fmt.EVENT_HEADER.unpack_from(data,offset)
        if size<24 or size%8 or (kind in fmt.PAYLOADS and size<24+fmt.PAYLOADS[kind].size):
            report('invalid_record_bytes',offset,record_bytes=size,event_type=kind);break
        if size>len(data)-offset:
            report('truncated_record',offset,record_bytes=size);break
        row={'timestamp_qpc':timestamp,'thread_id':thread,'event_type':kind,'record_bytes':size,
             'target_id':target,'sequence':sequence,'offset':offset}
        if thread in previous_seq and sequence!=(previous_seq[thread]+1)&0xffffffff:
            report('sequence_gap',offset,thread_id=thread,expected_sequence=(previous_seq[thread]+1)&0xffffffff,actual_sequence=sequence)
        previous_seq[thread]=sequence
        invalid_time=timestamp<start or timestamp<previous_time.get(thread,start)
        if invalid_time:report('invalid_timestamp',offset,thread_id=thread)
        previous_time[thread]=max(timestamp,previous_time.get(thread,start))
        summary['record_count']+=1
        if kind not in fmt.PAYLOADS:
            report('unknown_event_type',offset,event_type=kind,record_bytes=size)
        else:
            values=fmt.PAYLOADS[kind].unpack_from(data,offset+24)
            row.update(zip(fmt.FIELDS[kind],values))
            try:fmt.validate_event_values(row)
            except ValueError as exc:
                report('invalid_payload',offset,reason=str(exc));offset+=size;summary['bytes_consumed']=offset;continue
            target_valid=target in target_ids or (kind==fmt.COUNTER and target==0)
            if not target_valid:report('unknown_target',offset,target_id=target)
            row['target_valid']=target_valid
            doc['events'].append(row);summary['known_event_count']+=1
            if target_valid and kind in (1,2,4,5):
                family='function' if kind in (1,2) else 'wait'
                key=(thread,family,row['correlation_id'],target)
                if invalid_time:
                    # Malformed pair events invalidate this correlation, even a
                    # duplicate Begin that cannot be accepted as a timestamp.
                    pending.pop(key,None)
                    if kind in (1,4):blocked.add(key)
                    else:blocked.discard(key)
                    report('broken_begin_end',offset,reason='invalid_pair_timestamp',thread_id=thread,correlation_id=row['correlation_id'],target_id=target)
                elif kind in (1,4):
                    if key in pending or key in blocked:
                        pending.pop(key,None);blocked.add(key)
                        report('broken_begin_end',offset,reason='duplicate_begin',thread_id=thread,correlation_id=row['correlation_id'])
                    else:pending[key]=row
                else:
                    begin=pending.pop(key,None)
                    if key in blocked:
                        blocked.remove(key);begin=None
                    if begin is None or begin['target_id']!=target or timestamp<begin['timestamp_qpc']:
                        report('broken_begin_end',offset,reason='missing_or_mismatched_begin',thread_id=thread,correlation_id=row['correlation_id'])
                    else:
                        duration=timestamp-begin['timestamp_qpc']
                        doc['pairs'].append({'family':family,'thread_id':thread,'target_id':target,
                                             'correlation_id':row['correlation_id'],'begin_offset':begin['offset'],'end_offset':offset,
                                             'duration_qpc':duration,'duration_ns_floor':duration*1000000000//freq})
                        summary['paired_functions' if family=='function' else 'paired_waits']+=1
        offset+=size;summary['bytes_consumed']=offset
    doc['segment_complete']=offset==len(data)
    for key,begin in sorted(pending.items()):
        report('broken_begin_end',begin['offset'],reason='missing_end',thread_id=key[0],correlation_id=key[2])
    return doc


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path)
    p.add_argument('--expected-executable-sha256');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv)
    try:
        doc=parse_trace(a.input.read_bytes(),expected_executable_sha256=a.expected_executable_sha256)
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    except (OSError,ValueError) as exc:print(f'error: {exc}',file=sys.stderr);return 2
    return 0 if doc['header_valid'] and doc['segment_complete'] else 2

if __name__=='__main__':raise SystemExit(main())
