"""Synthetic integer fixtures / CPU baseline, NEVER a model of Victoria 3 mechanics."""
from __future__ import annotations
import time
import numpy as np

KINDS = ('pop_growth', 'id_lookup')
SCENARIOS = ('random', 'colliding', 'masked', 'large-int')

def make_case(kind: str, n: int, scenario: str, seed: int = 1877) -> dict:
    if kind not in KINDS or scenario not in SCENARIOS or not 0 <= n <= 2_147_483_647:
        raise ValueError('invalid workload/scenario/record count')
    rng = np.random.default_rng(seed)
    if kind == 'pop_growth':
        if scenario == 'large-int':
            base = rng.integers(2_000_000_000, 2_100_000_000, n, dtype=np.int32)
            rate = rng.integers(500, 1001, n, dtype=np.int32)
            cap = rng.integers(2_100_000_000, 2_147_483_647, n, dtype=np.int32)
        else:
            base = rng.integers(0, 1_000_000, n, dtype=np.int32)
            rate = rng.integers(0, 101, n, dtype=np.int32)
            cap = base + rng.integers(0, 200_000, n, dtype=np.int32)
            if scenario == 'colliding' and n:
                base[:] = base[0]
            if scenario == 'masked':
                cap[:] = base
        arrays = (base, rate, cap)
    else:
        ids = rng.integers(0, n, n, dtype=np.int32) if n else np.empty(0, np.int32)
        if scenario == 'colliding' and n:
            ids[:] = rng.integers(0, min(n, 16), n, dtype=np.int32)
        if scenario == 'large-int':
            values = rng.integers(2_050_000_000, 2_147_483_647, n, dtype=np.int32)
        else:
            values = rng.integers(0, 1_000_000, n, dtype=np.int32)
        live = rng.integers(0, 2, n, dtype=np.uint8)
        if scenario == 'masked':
            live[:] = 0
            live[::16] = 1
        if scenario == 'large-int':
            live[:] = 1
        arrays = (ids, values, live)
    return {'kind': kind, 'scenario': scenario, 'n': n, 'seed': seed, 'inputs': arrays}

def pack_case(case: dict) -> dict:
    return {**case, 'inputs': tuple(np.array(x, copy=True, order='C') for x in case['inputs'])}

def transfer_bytes(case: dict) -> int:
    return sum(arr.nbytes for arr in case['inputs']) + case['n'] * 4

def cpu_reference(case: dict) -> np.ndarray:
    a, b, c = case['inputs']
    if case['kind'] == 'pop_growth':
        base = a.astype(np.int64)
        grown = base + base * b.astype(np.int64) // 1000
        return np.minimum(grown, c.astype(np.int64)).astype(np.int32)
    if case['kind'] == 'id_lookup':
        return np.where(c[a] != 0, b[a], -1).astype(np.int32)
    raise ValueError('unsupported kind')

def exact_match(reference: np.ndarray, result: np.ndarray) -> None:
    if reference.dtype != result.dtype or reference.shape != result.shape:
        raise ValueError(f'dtype or shape mismatch: {reference.dtype,reference.shape} != {result.dtype,result.shape}')
    wrong = np.flatnonzero(reference != result)
    if len(wrong):
        i = int(wrong[0])
        raise ValueError(f'output mismatch: count={len(wrong)}, first={i}, expected={reference[i]}, actual={result[i]}')

def cpu_pipeline(case: dict) -> tuple[np.ndarray, dict]:
    t0 = time.perf_counter_ns()
    packed = pack_case(case)
    t1 = time.perf_counter_ns()
    result = cpu_reference(packed)
    t2 = time.perf_counter_ns()
    applied = np.array(result, copy=True)
    t3 = time.perf_counter_ns()
    return applied, {'pack_ms': (t1-t0)/1e6, 'cpu_compute_ms': (t2-t1)/1e6,
                     'apply_ms': (t3-t2)/1e6, 'e2e_wall_ms': (t3-t0)/1e6}
