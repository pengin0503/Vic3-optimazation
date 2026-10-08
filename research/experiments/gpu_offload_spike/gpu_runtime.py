#!/usr/bin/env python3
"""Standalone offline OpenCL GPU feasibility benchmark; no Victoria 3 integration."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
from datetime import datetime, timezone
from offline_gpu_core import KINDS, SCENARIOS, make_case, cpu_reference, cpu_pipeline, exact_match
from gpu_opencl import OpenCLExecutor, NoGpuAvailable, device_catalog

def build_parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sizes', type=int, nargs='+', default=[100_000, 1_000_000])
    p.add_argument('--workloads', nargs='+', choices=KINDS, default=list(KINDS))
    p.add_argument('--scenarios', nargs='+', choices=SCENARIOS, default=list(SCENARIOS))
    p.add_argument('--repeats', type=int, default=9)
    p.add_argument('--warmups', type=int, default=2)
    p.add_argument('--seed', type=int, default=1877)
    p.add_argument('--device-substring', default='7800', help='Require exactly one GPU whose name matches this substring')
    p.add_argument('--output', default='gpu-results.json')
    p.add_argument('--list-devices', action='store_true')
    return p

def median(items, key):
    return statistics.median(x[key] for x in items)

def conduct(executor, sizes, workloads, scenarios, *, repeats=9, warmups=2, seed=1877):
    if repeats < 3 or warmups < 1 or not sizes or any(n < 1 or n > 2_147_483_647 for n in sizes):
        raise ValueError('repeats>=3, warmups>=1, 1 <= n <= INT_MAX are required')
    rows=[]
    for n in sizes:
        for kind in workloads:
            for scenario in scenarios:
                case=make_case(kind, n, scenario, seed)
                reference=cpu_reference(case)
                digest=hashlib.sha256()
                for arr in case['inputs']:
                    digest.update(arr.tobytes())
                cpu=[]
                for _ in range(warmups):
                    result,_=cpu_pipeline(case)
                    exact_match(reference,result)
                for _ in range(repeats):
                    result,wall=cpu_pipeline(case)
                    exact_match(reference,result)
                    cpu.append(wall)
                allocated=executor.allocate(case)  # create and compile outside timed iterations
                executor.preload(allocated,case)   # resident inputs before both modes
                for _ in range(warmups):
                    for mode in ('cold','resident'):
                        result, _=executor.run_once(allocated,case,mode)
                        exact_match(reference,result)
                measurements={'cold':[], 'resident':[]}
                for rep in range(repeats):
                    for mode in (('cold','resident') if rep%2==0 else ('resident','cold')):
                        result, times=executor.run_once(allocated,case,mode)
                        exact_match(reference,result)
                        measurements[mode].append(times)
                row={'workload':kind,'scenario':scenario,'records':n,'seed':seed,
                     'input_sha256':digest.hexdigest(),
                     'output_sha256':hashlib.sha256(reference.tobytes()).hexdigest(),
                     'cpu_samples':cpu,'cpu_e2e_median_ms':median(cpu,'e2e_wall_ms'),
                     'modes':{}}
                for mode,samples in measurements.items():
                    m=median(samples,'e2e_wall_ms')
                    h2d_bytes=samples[0]['h2d_bytes']
                    d2h_bytes=samples[0]['d2h_bytes']
                    transfer_event=median(samples,'h2d_device_event_ms')
                    download_event=median(samples,'d2h_device_event_ms')
                    row['modes'][mode]={
                        'count':len(samples), 'e2e_median_ms':m,
                        'synthetic_cpu_over_gpu_ratio':row['cpu_e2e_median_ms']/m if m > 0 else None,
                        'h2d_bytes_per_iteration':h2d_bytes,'d2h_bytes_per_iteration':d2h_bytes,
                        'observed_h2d_device_gb_per_s': h2d_bytes/(transfer_event*1e6) if transfer_event>0 and h2d_bytes else None,
                        'observed_d2h_device_gb_per_s': d2h_bytes/(download_event*1e6) if download_event>0 and d2h_bytes else None,
                        'samples':samples}
                rows.append(row)
    return {'schema_version':1, 'status':'measured','source':'synthetic_not_game',
            'gpu_executed':True,'not_a_vic3_speedup':True,
            'timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'machine':platform.platform(), 'device':executor.metadata,
            'repeats':repeats,'warmups':warmups,'results':rows}

def write_json(destination, payload):
    text=json.dumps(payload, ensure_ascii=False, indent=2)+'\n'
    if destination=='-':
        sys.stdout.write(text)
    else:
        Path(destination).write_text(text,encoding='utf-8')

def main(argv=None):
    args=build_parser().parse_args(argv)
    if args.list_devices:
        try:
            devices=device_catalog()
            write_json(args.output,{'status':'enumerated','gpu_executed':False,'devices':devices})
            return 0
        except Exception as ex:
            write_json(args.output,{'status':'error','gpu_executed':False,'error':str(ex)})
            return 2
    try:
        gpu=OpenCLExecutor(args.device_substring)
        output=conduct(gpu,args.sizes,args.workloads,args.scenarios,repeats=args.repeats,
                       warmups=args.warmups,seed=args.seed)
    except (NoGpuAvailable,ValueError,RuntimeError,ImportError,MemoryError) as ex:
        # An incomplete run never produces a success result. Errors are not throughput samples.
        write_json(args.output, {'schema_version':1,'status':'error','gpu_executed':False,
                                 'error':f'{type(ex).__name__}: {ex}'})
        return 2
    write_json(args.output,output)
    return 0

if __name__=='__main__':
    sys.exit(main())
