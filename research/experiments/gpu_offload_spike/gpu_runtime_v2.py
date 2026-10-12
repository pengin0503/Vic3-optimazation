#!/usr/bin/env python3
"""Second-generation synthetic RX 7800 XT benchmark: NumPy/Numba CPU vs real OpenCL GPU.

Runs in a separate process; never touches a Victoria 3 executable or game state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numba import njit, prange, set_num_threads, get_num_threads, __version__ as numba_version
from offline_gpu_core import KINDS, SCENARIOS, make_case, pack_case, cpu_reference, exact_match

CPU_BACKENDS = ('numpy', 'numba-serial', 'numba-parallel')
MODES = ('cold', 'resident')

@njit(cache=True)
def _pop_serial(base, rate, cap):
    output = np.empty(len(base), np.int32)
    for i in range(len(base)):
        original = np.int64(base[i])
        grown = original + (original * np.int64(rate[i])) // 1000
        limit = np.int64(cap[i])
        output[i] = np.int32(grown if grown < limit else limit)
    return output

@njit(parallel=True, cache=True)
def _pop_parallel(base, rate, cap):
    output = np.empty(len(base), np.int32)
    for i in prange(len(base)):
        original = np.int64(base[i])
        grown = original + (original * np.int64(rate[i])) // 1000
        limit = np.int64(cap[i])
        output[i] = np.int32(grown if grown < limit else limit)
    return output

@njit(cache=True)
def _lookup_serial(ids, values, live):
    output = np.empty(len(ids), np.int32)
    for i in range(len(ids)):
        index = ids[i]
        output[i] = values[index] if 0 <= index < len(values) and live[index] != 0 else -1
    return output

@njit(parallel=True, cache=True)
def _lookup_parallel(ids, values, live):
    output = np.empty(len(ids), np.int32)
    for i in prange(len(ids)):
        index = ids[i]
        output[i] = values[index] if 0 <= index < len(values) and live[index] != 0 else -1
    return output


def optimized_cpu(case: dict, backend: str) -> np.ndarray:
    """Warm this call before timing; first invocation compiles JIT functions."""
    if backend == 'numpy':
        return cpu_reference(case)
    if backend not in CPU_BACKENDS:
        raise ValueError(f'unknown CPU backend: {backend}')
    a, b, c = case['inputs']
    if case['kind'] == 'pop_growth':
        return _pop_serial(a, b, c) if backend == 'numba-serial' else _pop_parallel(a, b, c)
    if case['kind'] == 'id_lookup':
        return _lookup_serial(a, b, c) if backend == 'numba-serial' else _lookup_parallel(a, b, c)
    raise ValueError('unknown synthetic workload')


def gpu_digest(values: np.ndarray) -> str:
    return hashlib.sha256(values.tobytes()).hexdigest()


def cpu_sample(case: dict, backend: str, mode: str) -> tuple[np.ndarray, dict]:
    if mode not in MODES:
        raise ValueError(f'invalid CPU mode: {mode}')
    t0 = time.perf_counter_ns()
    packed = pack_case(case) if mode == 'cold' else case
    t1 = time.perf_counter_ns()
    result = optimized_cpu(packed, backend)
    t2 = time.perf_counter_ns()
    applied = np.array(result, copy=True)
    t3 = time.perf_counter_ns()
    return applied, {
        'pack_ms': (t1-t0)/1e6 if mode == 'cold' else 0.0,
        'cpu_compute_ms': (t2-t1)/1e6,
        'apply_ms': (t3-t2)/1e6,
        'e2e_wall_ms': (t3-t0)/1e6,
    }


def summarize_h2d(samples: list[dict]) -> dict:
    """Do not turn zero-duration OpenCL events into infinite/unreal bandwidth."""
    if not samples:
        raise ValueError('empty samples')
    host = [s['h2d_host_submit_ms'] + s['h2d_host_wait_ms'] for s in samples]
    durations = [s['h2d_device_event_ms'] for s in samples]
    bytes_per = [s['h2d_bytes'] for s in samples]
    valid = all(d > 0 for d in durations) and all(n > 0 for n in bytes_per)
    no_transfer = all(n == 0 for n in bytes_per)
    return {
        'host_phase_median_ms': statistics.median(host),
        'zero_duration_events': sum(d == 0 and n > 0 for d,n in zip(durations, bytes_per)),
        'device_event_valid': valid,
        'event_status': 'not_applicable_resident' if no_transfer else ('valid' if valid else 'invalid_zero_or_mixed'),
        'observed_device_gb_per_s': (statistics.median(bytes_per) / (statistics.median(durations)*1e6)) if valid else None,
        'bytes_per_iteration': bytes_per[0],
    }


def _median(samples: list[dict]) -> float:
    return statistics.median(s['e2e_wall_ms'] for s in samples)


def run_v2(gpu, sizes, workloads, scenarios, *, repeats: int=9, warmups: int=2,
           seed: int=1877, numba_threads: int=8, session_id: str='') -> dict:
    if repeats < 3 or warmups < 1 or not sizes or any(n < 1 or n > 2_147_483_647 for n in sizes):
        raise ValueError('repeats >=3, warmups >=1 and positive record counts are required')
    if not workloads or not scenarios or any(k not in KINDS for k in workloads) or any(k not in SCENARIOS for k in scenarios):
        raise ValueError('unknown/empty workload or scenario')
    if numba_threads < 1:
        raise ValueError('Numba thread count must be positive')
    set_num_threads(numba_threads)
    rows=[]
    for n in sizes:
        for kind in workloads:
            for scenario in scenarios:
                case=make_case(kind, n, scenario, seed)
                expected=cpu_reference(case)
                expected_sha=gpu_digest(expected)
                input_digest=hashlib.sha256()
                for a in case['inputs']:
                    input_digest.update(a.tobytes())
                for b in CPU_BACKENDS:
                    exact_match(expected,optimized_cpu(case,b))
                bufs=gpu.allocate(case)
                gpu.preload(bufs,case)
                cpu_samples={b:{m:[] for m in MODES} for b in CPU_BACKENDS}
                gpu_samples={m:[] for m in MODES}
                verified={m:0 for m in MODES}
                result_hashes={m:set() for m in MODES}
                for rep in range(warmups+repeats):
                    order=MODES if rep%2==0 else tuple(reversed(MODES))
                    baselines=CPU_BACKENDS if rep%2==0 else tuple(reversed(CPU_BACKENDS))
                    for mode in order:
                        for backend in baselines:
                            output, times=cpu_sample(case,backend,mode)
                            exact_match(expected,output)
                            if rep>=warmups:
                                cpu_samples[backend][mode].append(times)
                        output, times=gpu.run_once(bufs,case,mode)
                        exact_match(expected,output)
                        result_hashes[mode].add(gpu_digest(output))
                        verified[mode]+=1
                        if rep>=warmups:
                            gpu_samples[mode].append(times)
                row={'workload':kind,'scenario':scenario,'records':n,'seed':seed,
                     'input_sha256':input_digest.hexdigest(),
                     'reference_output_sha256':expected_sha,'cpu':{},'modes':{}}
                for backend in CPU_BACKENDS:
                    row['cpu'][backend]={}
                    for mode in MODES:
                        samples=cpu_samples[backend][mode]
                        row['cpu'][backend][mode]={'count':len(samples),
                                    'e2e_median_ms':_median(samples),'samples':samples,
                                    'output_sha256':expected_sha}
                for mode in MODES:
                    samples=gpu_samples[mode]
                    gmedian=_median(samples)
                    hashes=result_hashes[mode]
                    if hashes != {expected_sha}:
                        raise ValueError('GPU digest differs from CPU reference')
                    entry={'count':len(samples),'e2e_median_ms':gmedian,
                           'samples':samples,'gpu_output_sha256':next(iter(hashes)),
                           'gpu_output_verified_iterations':verified[mode],
                           'h2d':summarize_h2d(samples),
                           'd2h_bytes_per_iteration':samples[0]['d2h_bytes'],
                           'observed_d2h_device_gb_per_s':(
                               samples[0]['d2h_bytes'] / (statistics.median(s['d2h_device_event_ms'] for s in samples)*1e6)
                               if all(s['d2h_device_event_ms']>0 for s in samples) else None)}
                    for backend,label in (('numpy','numpy'),('numba-serial','numba_serial'),('numba-parallel','numba_parallel')):
                        for cpu_mode in MODES:
                            entry[f'ratio_vs_{label}_cpu_{cpu_mode}']=row['cpu'][backend][cpu_mode]['e2e_median_ms']/gmedian if gmedian>0 else None
                    row['modes'][mode]=entry
                rows.append(row)
    return {'schema_version':2,'status':'measured','source':'synthetic_not_game',
            'gpu_executed':True,'not_a_vic3_speedup':True,
            'timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'session_id':session_id or str(uuid.uuid4()),
            'machine':platform.platform(), 'python_version':sys.version,
            'numpy_version':np.__version__,'numba_version':numba_version,
            'numba_threads':get_num_threads(), 'device':gpu.metadata,
            'repeats':repeats,'warmups':warmups,'results':rows}


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sizes',type=int,nargs='+',default=[100_000,1_000_000])
    p.add_argument('--workloads',nargs='+',choices=KINDS,default=list(KINDS))
    p.add_argument('--scenarios',nargs='+',choices=SCENARIOS,default=list(SCENARIOS))
    p.add_argument('--repeats',type=int,default=9)
    p.add_argument('--warmups',type=int,default=2)
    p.add_argument('--seed',type=int,default=1877)
    p.add_argument('--numba-threads',type=int,default=8)
    p.add_argument('--device-substring',default='gfx1101')
    p.add_argument('--session-id',default='')
    p.add_argument('--output',default='gpu-results-v2.json')
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        from gpu_opencl import OpenCLExecutor
        gpu=OpenCLExecutor(args.device_substring)
        report=run_v2(gpu,args.sizes,args.workloads,args.scenarios,repeats=args.repeats,
                      warmups=args.warmups,seed=args.seed,numba_threads=args.numba_threads,
                      session_id=args.session_id)
    except (ValueError,RuntimeError,ImportError,MemoryError) as exc:
        report={'schema_version':2,'status':'error','gpu_executed':False,
                'error':f'{type(exc).__name__}: {exc}'}
        code=2
    else:
        code=0
    payload=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.output=='-':
        print(payload,end='')
    else:
        Path(args.output).write_text(payload,encoding='utf-8')
    return code

if __name__=='__main__':sys.exit(main())
