"""Dependency-free v1 reference codec for synthetic golden vectors only."""
import hashlib
import json
import struct

MAGIC=b'V3PF'
FORMAT_VERSION=1
SIGNATURE_DB_VERSION=1
FIXED_PREFIX_BYTES=112
EVENT_HEADER_BYTES=24
HEADER=struct.Struct('<4sHHB7xQQ32sI32sIQ')
EVENT_HEADER=struct.Struct('<QIHHII')
FUNCTION_BEGIN,FUNCTION_END,SCHEDULER_DECISION,WAIT_BEGIN,WAIT_END,COUNTER=range(1,7)
PAYLOADS={1:struct.Struct('<Q'),2:struct.Struct('<QI4x'),3:struct.Struct('<QQQQHBxII4x'),4:struct.Struct('<QH6xQ'),5:struct.Struct('<QI4x'),6:struct.Struct('<I4xq')}
FIELDS={1:('correlation_id',),2:('correlation_id','status_flags'),3:('correlation_id','range_begin','range_end','range_length','task_thread_count','decision','reason_flags','chunk_or_work_count'),4:('correlation_id','wait_kind','object_token'),5:('correlation_id','result_flags'),6:('counter_id','value')}
BITS={'timestamp_qpc':64,'thread_id':32,'event_type':16,'target_id':32,'sequence':32,
      'correlation_id':64,'status_flags':32,'range_begin':64,'range_end':64,'range_length':64,
      'task_thread_count':16,'decision':8,'reason_flags':32,'chunk_or_work_count':32,'wait_kind':16,
      'object_token':64,'result_flags':32,'counter_id':32}
EXPECTED_SHA256='9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'
BUILD_IDS={'caligula_branch':'release/1.14.5','caligula_rev':'9f8281a37e85639359b3b0c2c5df0196e975ca4b',
           'clausewitz_branch':'caligula/release/1.14.x','clausewitz_rev':'fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef'}


def uint(value,bits):
    if type(value) is not int or not 0<=value<1<<bits:raise ValueError(f'expected uint{bits}')
    return value


def canonical_json(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def canonical_target_bytes(targets: list[dict]) -> bytes:
    return canonical_json(targets)


def validate_metadata(metadata):
    if not isinstance(metadata,dict) or metadata.get('build_ids')!=BUILD_IDS:raise ValueError('build ID mismatch')
    if not isinstance(metadata.get('profiler_build_id'),str) or not metadata['profiler_build_id'].strip():raise ValueError('missing profiler build ID')
    targets=metadata.get('targets')
    if not isinstance(targets,list):raise ValueError('invalid target metadata')
    ids=set()
    for t in targets:
        if not isinstance(t,dict):raise ValueError('invalid target metadata')
        tid=uint(t.get('target_id'),32)
        if tid==0 or tid in ids:raise ValueError('duplicate/zero target ID')
        ids.add(tid)
        for key in ('name','kind'):
            if not isinstance(t.get(key),str) or not t[key].strip():raise ValueError('invalid target identity')
        ranges=t.get('ranges')
        if not isinstance(ranges,list) or not ranges:raise ValueError('empty target range')
        pairs=[]
        for r in ranges:
            if not isinstance(r,dict):raise ValueError('invalid target range')
            try:
                b,e=(int(r[k],16) for k in ('begin_rva','end_rva'))
                if not all(isinstance(r[k],str) and r[k].startswith('0x') for k in ('begin_rva','end_rva')) or not 0<=b<e<=1<<32:raise ValueError()
            except (KeyError,TypeError,ValueError) as exc:raise ValueError('invalid target range') from exc
            pairs.append((b,e))
        pairs.sort()
        if any(e>b2 for (_,e),(b2,_) in zip(pairs,pairs[1:])):raise ValueError('overlapping target ranges')
    canonical_json(metadata)
    return ids


def encode_header(metadata: dict, *,qpc_frequency: int,session_start_qpc: int,
                  executable_sha256: str,signature_db_version: int,flags: int=0,total_dropped_events: int=0) -> bytes:
    validate_metadata(metadata)
    if executable_sha256!=EXPECTED_SHA256:raise ValueError('unsupported executable build')
    if signature_db_version!=SIGNATURE_DB_VERSION:raise ValueError('unsupported signature DB')
    uint(signature_db_version,32)
    if uint(qpc_frequency,64)==0:raise ValueError('zero QPC frequency')
    uint(session_start_qpc,64);uint(flags,32);uint(total_dropped_events,64)
    raw=canonical_json(metadata)
    extension=raw+b'\0'*(-len(raw)%8)
    length=FIXED_PREFIX_BYTES+len(extension)
    if length>65528:raise ValueError('metadata exceeds uint16 aligned header')
    return HEADER.pack(MAGIC,FORMAT_VERSION,length,8,qpc_frequency,session_start_qpc,bytes.fromhex(executable_sha256),signature_db_version,
                       hashlib.sha256(canonical_target_bytes(metadata['targets'])).digest(),flags,total_dropped_events)+extension


def validate_event_values(event):
    kind=event['event_type']
    for k in ('timestamp_qpc','thread_id','event_type','target_id','sequence')+FIELDS[kind]:
        if k=='value':
            if type(event[k]) is not int or not -(1<<63)<=event[k]<1<<63:raise ValueError('expected int64 counter')
        else:uint(event[k],BITS[k])
    if event['thread_id']==0:raise ValueError('zero thread ID')
    if kind!=COUNTER and event['target_id']==0:raise ValueError('target zero reserved for Counter')
    if kind==SCHEDULER_DECISION:
        if event['decision'] not in (0,1,2):raise ValueError('invalid scheduler decision')
        if event['range_end']<event['range_begin'] or event['range_length']!=event['range_end']-event['range_begin']:
            raise ValueError('inconsistent scheduler range')


def encode_event(event: dict) -> bytes:
    kind=event.get('event_type')
    if type(kind) is not int or kind not in PAYLOADS:raise ValueError('encoder supports known event types only')
    try:validate_event_values(event)
    except KeyError as exc:raise ValueError(f'missing event field {exc}') from exc
    payload=PAYLOADS[kind].pack(*(event[k] for k in FIELDS[kind]))
    return EVENT_HEADER.pack(event['timestamp_qpc'],event['thread_id'],kind,EVENT_HEADER_BYTES+len(payload),event['target_id'],event['sequence'])+payload


def encode_trace(header: bytes,events: list[bytes]) -> bytes:
    if len(header)<112 or header[:4]!=MAGIC or len(header)%8 or struct.unpack_from('<H',header,6)[0]!=len(header):raise ValueError('invalid encoded header')
    for raw in events:
        if len(raw)<24 or len(raw)%8 or struct.unpack_from('<H',raw,14)[0]!=len(raw):raise ValueError('invalid encoded event size')
    return header+b''.join(events)
