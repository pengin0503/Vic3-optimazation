#!/usr/bin/env python3
"""Owned integer recurrence and hypothetical transfer bytes, not GPU timings."""
import argparse
import hashlib
import json
import numpy as np
from offline_gpu_core import make_case, cpu_reference, SCENARIOS


def probe(case: dict, stages: int, *, host_updates=False, intermediate_outputs=False) -> dict:
    if type(stages) is not int or not 1 <= stages <= 32:
        raise ValueError('stages must be integer 1..32')
    if type(host_updates) is not bool or type(intermediate_outputs) is not bool:
        raise ValueError('lifecycle flags must be booleans')
    if not isinstance(case, dict) or case.get('kind') != 'pop_growth':
        raise ValueError('only the owned pop_growth recurrence is supported')
    n = case.get('n')
    arrays = case.get('inputs')
    if type(n) is not int or not 0 <= n <= 1_000_000:
        raise ValueError('record count must be integer 0..1,000,000')
    if not isinstance(arrays, (tuple,list)) or len(arrays) != 3:
        raise ValueError('three owned input arrays required')
    if any(not isinstance(a,np.ndarray) or a.dtype != np.dtype('int32') or
           a.shape != (n,) or np.any(a < 0) for a in arrays):
        raise ValueError('nonnegative int32 arrays of declared length required')
    state, rate, cap = arrays
    for _ in range(stages):
        state = cpu_reference(dict(kind='pop_growth', inputs=(state,rate,cap)))
    reasons = []
    if host_updates:reasons.append('host input updates prevent this fixed-input batching proof')
    if intermediate_outputs:reasons.append('consumer requires intermediate host-visible outputs')
    eligible = not reasons
    initial_hash = hashlib.sha256(b''.join(a.astype('<i4',copy=False).tobytes() for a in arrays)).hexdigest()
    return dict(format_version=1, source='synthetic_lifecycle_model_not_gpu_or_game',
        gpu_executed=False, scenario=case.get('scenario'), records=n, stages=stages,
        initial_input_sha256=initial_hash,
        final_output_sha256=hashlib.sha256(state.astype('<i4',copy=False).tobytes()).hexdigest(),
        oracle_scope='fixed-input CPU recurrence only; host-updated result values are not simulated',
        host_updates=host_updates, intermediate_outputs=intermediate_outputs,
        batching_eligible=eligible, blocked_reasons=reasons,
        per_stage_roundtrip_transfer_bytes=16*n*stages,
        batched_h2d_bytes=12*n if eligible else None,
        batched_d2h_bytes=4*n if eligible else None,
        batched_transfer_bytes=16*n if eligible else None,
        resident_observed_transfer_bytes=12*n+4*n*stages if not host_updates else None,
        gpu_time_ms=None, bandwidth_gb_per_s=None, speedup=None,
        assumptions=['per-stage comparison uploads all three int32 inputs and downloads output each stage',
                     'batched route uploads all three inputs once, ping-pongs device state, downloads final output once',
                     'resident-observed route keeps fixed inputs/state on device but downloads each stage',
                     'byte counts do not include allocation, queue, synchronization, driver or application costs',
                     'no actual GPU, game formula, live state ownership or performance is verified'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', type=int, nargs='+', default=[0,17,1_000_000])
    parser.add_argument('--stages', type=int, nargs='+', default=[1,4,16])
    parser.add_argument('--seed', type=int, default=1877)
    args = parser.parse_args(argv)
    try:
        if any(not 0 <= n <= 1_000_000 for n in args.sizes) or any(not 1 <= s <= 32 for s in args.stages):
            raise ValueError('bounded sizes/stages required')
        results = []
        for scenario in SCENARIOS:
            for n in args.sizes:
                case = make_case('pop_growth', n, scenario, args.seed)
                for stages in args.stages:
                    results.append(probe(case,stages))
        print(json.dumps(dict(format_version=1, gpu_executed=False, seed=args.seed,
                              results=results),indent=2,sort_keys=True))
        return 0
    except ValueError as exc:
        parser.exit(2, f'error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
