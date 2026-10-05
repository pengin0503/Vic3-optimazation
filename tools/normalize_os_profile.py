#!/usr/bin/env python3
"""Explicit-mapping CSV import. No unverified vendor column names."""
import argparse
import csv
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
import re
import sys

UNITS={'ns':1,'us':1000,'ms':1000000,'s':1000000000}
EVENT_TYPES={'cpu_sample','wait','context_switch'}
TEXT_FIELDS=('process','module','stack')
TIME_FIELDS=('duration','cpu_time','wait_time')
ADDRESS_FIELDS=('module_base','instruction_va')


def address(value):
    if isinstance(value,bool): raise ValueError('boolean address')
    if isinstance(value,int): n=value
    elif isinstance(value,str) and re.fullmatch(r'(?:0[xX][0-9a-fA-F]+|[0-9]+)',value.strip()):
        s=value.strip();n=int(s,16 if s.lower().startswith('0x') else 10)
    else: raise ValueError('invalid address')
    if not 0 <= n < 1 << 64: raise ValueError('address outside uint64')
    return n


def nanoseconds(value,unit,separator='.'):
    if unit not in UNITS: raise ValueError('invalid time unit')
    s=value.strip()
    if separator==',':
        if '.' in s: raise ValueError('unexpected decimal/grouping separator')
        s=s.replace(',','.')
    elif separator!='.': raise ValueError('invalid decimal separator')
    if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',s):
        raise ValueError('invalid numeric field')
    with localcontext() as ctx:
        ctx.prec=max(50,len(s)+12)
        n=Decimal(s)*UNITS[unit]
        if not n.is_finite() or n<0 or n!=n.to_integral_value() or n >= 1 << 64:
            raise ValueError('time must be finite, nonnegative integral nanoseconds within uint64')
        return int(n)


def normalize_csv(path: Path,mapping: dict,*,run_id: str,source: str) -> dict:
    if not isinstance(run_id,str) or not run_id.strip() or not isinstance(source,str) or not source.strip():
        raise ValueError('run_id and source required')
    digest=mapping.get('executable_sha256','')
    if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):
        raise ValueError('executable_sha256 required in mapping')
    event_type=mapping.get('event_type')
    if event_type not in EVENT_TYPES: raise ValueError('invalid event_type')
    for field in ('timestamp_column','thread_id_column'):
        if not isinstance(mapping.get(field),str) or not mapping[field]: raise ValueError(f'{field} required')
    units={field:mapping.get(field+'_unit') for field in ('timestamp',)+TIME_FIELDS if field=='timestamp' or field+'_column' in mapping}
    if any(u not in UNITS for u in units.values()): raise ValueError('explicit valid unit required for every time field')
    separator=mapping.get('decimal_separator','.')
    if separator not in ('.',','): raise ValueError('invalid decimal_separator')
    columns={key[:-7]:value for key,value in mapping.items() if key.endswith('_column')}
    allowed={'timestamp','thread_id',*TEXT_FIELDS,*TIME_FIELDS,*ADDRESS_FIELDS,'context_switches'}
    if set(columns)-allowed or any(not isinstance(c,str) or not c for c in columns.values()):
        raise ValueError('unsupported or empty mapped field')
    rows=[]
    with path.open(encoding=mapping.get('encoding','utf-8-sig'),newline='') as f:
        reader=csv.DictReader(f,delimiter=mapping.get('delimiter',','),strict=True)
        headers=reader.fieldnames or []
        if len(headers)!=len(set(headers)): raise ValueError('duplicate CSV column')
        if set(columns.values())-set(headers): raise ValueError('missing mapped column')
        unmapped=sorted(set(headers)-set(columns.values()))
        for line,raw in enumerate(reader,start=2):
            if None in raw or any(v is None for v in raw.values()): raise ValueError(f'malformed row {line}')
            row={'event_type':event_type,'source_row':line,'thread_id':raw[columns['thread_id']],
                 'timestamp_ns':nanoseconds(raw[columns['timestamp']],units['timestamp'],separator)}
            if not row['thread_id'].strip(): raise ValueError(f'empty thread_id at row {line}')
            for field in TEXT_FIELDS:
                if field in columns: row[field]=raw[columns[field]]
            for field in TIME_FIELDS:
                if field in columns and raw[columns[field]].strip():
                    row[field+'_ns']=nanoseconds(raw[columns[field]],units[field],separator)
            for field in ADDRESS_FIELDS:
                if field in columns and raw[columns[field]].strip(): row[field]=hex(address(raw[columns[field]]))
            if all(k in row for k in ADDRESS_FIELDS) and address(row['instruction_va'])<address(row['module_base']):
                raise ValueError(f'VA below module base at row {line}')
            if 'context_switches' in columns and raw[columns['context_switches']].strip():
                s=raw[columns['context_switches']].strip()
                if not re.fullmatch('[0-9]+',s): raise ValueError('context_switches must be nonnegative integer')
                row['context_switches']=int(s)
            if mapping.get('include_raw_source_row',False): row['raw_source_row']=raw
            rows.append(row)
    return {'format_version':1,'run_id':run_id,'source':source,'source_filename':path.name,
            'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'executable_sha256':digest,'unmapped_columns':unmapped,'rows':rows}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path)
    p.add_argument('--mapping',type=Path,required=True);p.add_argument('--run-id',required=True)
    p.add_argument('--source',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv)
    try:
        doc=normalize_csv(a.input,json.loads(a.mapping.read_text(encoding='utf-8')),run_id=a.run_id,source=a.source)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    except (OSError,ValueError,csv.Error,InvalidOperation) as exc:
        print(f'error: {exc}',file=sys.stderr);return 2
    return 0

if __name__=='__main__': raise SystemExit(main())
