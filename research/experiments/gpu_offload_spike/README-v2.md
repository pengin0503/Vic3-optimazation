# GPU synthetic benchmark v2 — 9700X optimized CPU versus RX 7800 XT GPU

This is a **synthetic offline microbenchmark**, not a Victoria 3 code modification, profiler or in-game speedup measurement. Version 1's reported 3.72–9.46x synthetic gains compared only against NumPy and therefore are **not** appropriate evidence for GPU offloading.

## Why v2

- Independent CPU baselines: NumPy, **Numba JIT fused serial** and **Numba JIT fused parallel** loops, with the same synthetic integer operations as the OpenCL kernel.
- CPU and GPU each measured in **cold** (CPU pack/copy then process) and **resident** (reused already-prepared input) modes. Resident GPU inputs were preloaded and input upload cost is excluded, though its D2H remains; resident CPU input preparation is likewise excluded.
- CPU and GPU samples interleaved within each case; alternate backend and mode order. JIT compilation, device allocation and GPU preloading happen before timing.
- Strict per-iteration GPU/CPU result equality; independently report GPU output SHA-256, reference output SHA-256 and successful GPU validation iteration count. Hash computation happens outside the timed GPU processing interval.
- OpenCL H2D event time **zero when bytes >0 means invalid profiling**, not free transfer. The JSON retains measured host submit+wait wall timings and `h2d.event_status`; H2D device bandwidth stays `null` until **every** device event is positive.
- `session_id`, driver and software versions, per-run raw samples, numba thread count and comparison ratios for auditability. Schema v2, without changing v1's files or result format.

**Limitation:** A Numba JIT microbenchmark is a more credible CPU baseline than NumPy, **but is still not the optimized native C++ or real Victoria 3 CPU workload**. Kernel/dataset isolation, scheduling/dependencies, save determinism, critical path, game wall-time and actual PCIe bandwidth remain unmeasured. No assertions about gameplay speed are permitted.

## Windows PowerShell / RX 7800 XT

Run this in your existing clone. Until this branch is merged to main, first check it out:

```powershell
cd C:\Users\pengin0053\Desktop\Vic3-optimazation
git fetch origin research/gpu-numba-fair-baseline-20261008
git switch -c research/gpu-numba-fair-baseline-20261008 --track origin/research/gpu-numba-fair-baseline-20261008
cd research\experiments\gpu_offload_spike
.\.venv\Scripts\python.exe -m pip install --upgrade numpy numba pyopencl
.\.venv\Scripts\python.exe -m unittest discover -p "test_*.py" -v
```

If the local branch already exists, use `git switch research/gpu-numba-fair-baseline-20261008` instead.

Perform **three independent benchmark process sessions**. The GPU exposes `gfx1101` as its OpenCL device name on the user's machine; this is v2's default (override using `--device-substring` if needed):

```powershell
1..3 | ForEach-Object {
    .\.venv\Scripts\python.exe gpu_runtime_v2.py --sizes 100000 1000000 --repeats 9 --warmups 2 --numba-threads 8 --device-substring gfx1101 --session-id "session-$_" --output "gpu-results-v2-session-$_.json"
    if ($LASTEXITCODE -ne 0) { throw "GPU benchmark session $_ failed" }
}
```

Send back `gpu-results-v2-session-1.json`, `gpu-results-v2-session-2.json`, `gpu-results-v2-session-3.json`. No game logs, executable, save or other Victoria 3 data are needed.

## Interpreting output

Use matching **cold CPU / cold GPU** or **resident CPU / resident GPU** ratios:
- `modes.cold.ratio_vs_numba_serial_cpu_cold`
- `modes.cold.ratio_vs_numba_parallel_cpu_cold`
- `modes.resident.ratio_vs_numba_serial_cpu_resident`
- `modes.resident.ratio_vs_numba_parallel_cpu_resident`

Ratio = CPU median / GPU median. >1 means GPU faster on that *synthetic* case. `numba_threads: 8` is the requested number of Numba parallel worker threads; it does not change the CPU's physical core count.

`h2d.host_phase_median_ms` measures wall clock across enqueue+wait for the upload region; `h2d.zero_duration_events` records invalid zero GPU events with nonzero copy bytes. On AMD's prior v1 result, **all H2D device event durations were zero**; v2 does not pretend the root cause is fixed. This may arise from profiling event semantics or the driver's host-stage buffering and requires real GPU diagnostic follow-up. This host timing is *not* necessarily pure PCIe transfer time.

`gpu_output_sha256` is computed from the GPU-returned array in every iteration (after timing). Its expected value is the row's `reference_output_sha256`. If any GPU output differs in data, dtype or shape, the run fails with exit 2 and `status=error` rather than returning a success result.

The benchmark does not validate or accelerate Victoria 3. The next engineering gate remains independently reconstructing a genuinely GPU-safe, significant native task from the 1.14.5 critical path.
