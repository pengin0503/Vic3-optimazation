#!/usr/bin/env python3
"""RESEARCH SPIKE ONLY: synthetic Vic3-shaped CPU probes, not GPU execution.

Python >=3.10, NumPy, Numba. All byte counts assume inputs reside on the CPU
and final output is copied back; inputs are not real Victoria 3 state.
"""
import argparse
import hashlib
import json
import os
import platform
import statistics
import time

import numpy as np
from numba import njit

KINDS = ('pop_growth', 'group_sum', 'id_lookup')
GROUP_COUNT = 512


def transfer_floor_ms(bytes_total: int, gbps: float) -> float:
    if bytes_total < 0 or not (gbps > 0):
        raise ValueError('byte count must be nonnegative; GB/s must be positive')
    return bytes_total / (gbps * 1_000_000_000) * 1000.0


def optimistic_gpu_margin_ms(cpu_ms: float, bytes_total: int, gbps: float,
                             fixed_overhead_ms: float) -> float:
    if cpu_ms < 0 or fixed_overhead_ms < 0:
        raise ValueError('times must be nonnegative')
    return cpu_ms - transfer_floor_ms(bytes_total, gbps) - fixed_overhead_ms


def make_case(kind: str, n: int, seed: int) -> dict:
    if kind not in KINDS or n < 0:
        raise ValueError('unsupported kind or negative count')
    rng = np.random.default_rng(seed)
    if kind == 'pop_growth':
        base = rng.integers(0, 1_000_000, size=n, dtype=np.int32)
        rate = rng.integers(0, 101, size=n, dtype=np.int32)
        cap = base + rng.integers(0, 200_000, size=n, dtype=np.int32)
        inputs = (base, rate, cap)
        out_bytes = n * 4
    elif kind == 'group_sum':
        groups = rng.integers(0, GROUP_COUNT, size=n, dtype=np.int32)
        amounts = rng.integers(0, 1000, size=n, dtype=np.int32)
        inputs = (groups, amounts)
        out_bytes = GROUP_COUNT * 8
    else:
        ids = rng.integers(0, n, size=n, dtype=np.int32) if n else np.empty(0, np.int32)
        values = rng.integers(0, 1_000_000, size=n, dtype=np.int32)
        live = rng.integers(0, 2, size=n, dtype=np.uint8)
        inputs = (ids, values, live)
        out_bytes = n * 4
    return {'kind': kind, 'inputs': inputs, 'n': n,
            'transfer_bytes': sum(a.nbytes for a in inputs) + out_bytes}


@njit(cache=True)
def _pop_growth_cpu(base, rate, cap):
    out = np.empty(len(base), dtype=np.int32)
    for i in range(len(base)):
        grown = np.int64(base[i]) + np.int64(base[i]) * np.int64(rate[i]) // 1000
        out[i] = min(grown, np.int64(cap[i]))
    return out


@njit(cache=True)
def _group_sum_cpu(groups, amounts):
    out = np.zeros(GROUP_COUNT, dtype=np.int64)
    for i in range(len(groups)):
        out[groups[i]] += np.int64(amounts[i])
    return out


@njit(cache=True)
def _id_lookup_cpu(ids, values, live):
    out = np.empty(len(ids), dtype=np.int32)
    for i in range(len(ids)):
        id_ = ids[i]
        out[i] = values[id_] if live[id_] else -1
    return out


def run_numba(case: dict) -> np.ndarray:
    return {'pop_growth': _pop_growth_cpu, 'group_sum': _group_sum_cpu,
            'id_lookup': _id_lookup_cpu}[case['kind']](*case['inputs'])


def run_numpy(case: dict) -> np.ndarray:
    a = case['inputs']
    kind = case['kind']
    if kind == 'pop_growth':
        base = a[0].astype(np.int64)
        grown = base + base * a[1].astype(np.int64) // 1000
        return np.minimum(grown, a[2]).astype(np.int32)
    if kind == 'group_sum':
        out = np.zeros(GROUP_COUNT, np.int64)
        np.add.at(out, a[0], a[1].astype(np.int64))
        return out
    if kind == 'id_lookup':
        return np.where(a[2][a[0]] != 0, a[1][a[0]], -1).astype(np.int32)
    raise ValueError(kind)


def median_ms(fn, case, repeats: int) -> float:
    fn(case)  # JIT warm-up and allocator warm-up excluded from timings
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        result = fn(case)
        elapsed = time.perf_counter_ns() - start
        if result.shape[0] < 0:  # read result so it remains observable
            raise AssertionError
        samples.append(elapsed / 1_000_000)
    return statistics.median(samples)


def run_benchmark(sizes, repeats: int):
    rows = []
    for n in sizes:
        for kind in KINDS:
            case = make_case(kind, n, seed=1877)
            reference = run_numpy(case)
            actual = run_numba(case)
            if not np.array_equal(reference, actual):
                raise AssertionError(f'output mismatch: {kind}, {n}')
            cpu = median_ms(run_numba, case, repeats)
            numpy_ms = median_ms(run_numpy, case, repeats)
            encoded = hashlib.sha256(actual.tobytes()).hexdigest()
            rows.append({
                'workload': kind, 'records': n,
                'bytes_h2d_plus_d2h': case['transfer_bytes'],
                'correctness': 'numpy_int_reference_exact',
                'sha256_output': encoded,
                'cpu_numba_median_ms': round(cpu, 6),
                'cpu_numpy_median_ms': round(numpy_ms, 6),
                'gpu_executed': False,
                'scenarios': [{
                    'hypothetical_pcie_effective_gbps': b,
                    'hypothetical_fixed_ms': overhead,
                    'transfer_floor_ms': round(transfer_floor_ms(case['transfer_bytes'], b), 6),
                    'optimistic_budget_for_gpu_kernel_ms': round(
                        optimistic_gpu_margin_ms(cpu, case['transfer_bytes'], b, overhead), 6),
                } for b in (12, 24) for overhead in (0, 0.1)],
            })
    return {'schema_version': 1, 'purpose': 'CPU synthetic / hypothetical transfer only',
            'not_a_gpu_benchmark': True, 'not_a_vic3_speedup': True,
            'host': {'machine': platform.machine(), 'platform': platform.platform(),
                     'processor': platform.processor(), 'cpu_count': os.cpu_count(),
                     'numpy': np.__version__, 'gpu_device_used': False},
            'repeats': repeats, 'results': rows}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sizes', type=int, nargs='+', default=[100_000, 1_000_000])
    p.add_argument('--repeats', type=int, default=9)
    p.add_argument('--output', default='-')
    args = p.parse_args()
    if args.repeats < 1 or any(v < 0 for v in args.sizes):
        p.error('repeats must be positive, counts nonnegative')
    result = run_benchmark(args.sizes, args.repeats)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output == '-':
        print(output)
    else:
        with open(args.output, 'w', encoding='utf-8') as file:
            file.write(output + '\n')
