# Victoria 3 GPU Offloading — standalone OpenCL benchmark

> **2026-10-08 update:** This describes archived **v1** NumPy comparison. For a more meaningful Numba-optimized CPU baseline and the RX 7800 XT three-session test, see [README-v2.md](README-v2.md). No game-performance gain is established.

**Synthetic experiment. Not Victoria 3 logic. No game, save, loader, injector, native patch or process attach.**

Issue #12: test whether running independent integer kernels on a **real RX 7800 XT** can outperform NumPy on the same Windows workstation **end-to-end**. This continues PR #13's CPU-only theoretical investigation. GPU compute uses OpenCL 1.2 as an equivalent to Vulkan compute; Vulkan SDK not required.

## Windows 11 / RX 7800 XT

1. Install current AMD Radeon GPU driver with OpenCL support and Python 3.11+ x64.
2. The v1 benchmark was merged to main in PRs #13 and #14. In an existing clone, use the latest main branch:

```powershell
git switch main
git pull --ff-only
```

3. In PowerShell from the repository root:

```powershell
cd research\experiments\gpu_offload_spike
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install numpy numba pyopencl
.\.venv\Scripts\python.exe -m unittest discover -p 'test_*.py' -v
.\.venv\Scripts\python.exe gpu_runtime.py --list-devices --output gpu-devices.json
.\.venv\Scripts\python.exe gpu_runtime.py --sizes 100000 1000000 --repeats 9 --warmups 2 --device-substring gfx1101 --output gpu-results-local.json
```

4. Share only `gpu-results-local.json` and `gpu-devices.json` if review is desired. They contain device/OS metadata and hashes/timing of synthetic input, **not game data**.

The tool requires exactly **one OpenCL GPU** whose device name includes `7800`, refusing CPU drivers, missing runtime, ambiguous devices, kernel build failures and unequal results. If the name differs, inspect `gpu-devices.json` and supply a unique substring. Installing PyOpenCL alone does not install the AMD driver or an OpenCL ICD.

To perform CPU-only unit tests on another system, `pip install numpy` suffices (the existing PR #13 CPU research tests additionally require `numba`). No GPU is necessary for the new tests. The GPU CLI returns code 2 and error JSON with `gpu_executed: false` when no eligible GPU is present.

## What is measured

- **Workloads:** synthetic integer elementwise `pop_growth` using 64-bit intermediate, and masked `id_lookup` using random table gathers. These are *not* the actual Victoria 3 formulas/objects.
- **Scenarios:** random, collision-heavy, masked, large integer boundary. Counts: 100,000 and 1,000,000; seed 1877.
- **Cold:** each iteration packs CPU inputs, uploads H2D, dispatches OpenCL, downloads D2H, applies result by synthetic CPU array copy.
- **Resident:** buffers are preloaded once outside timing, then dispatched and D2H output copied on every iteration. H2D **setup excluded**; CPU application is still included. This is an upper-bound opportunity scenario, not an end-to-end first-use performance claim.
- `*_host_submit_ms`, `*_host_wait_ms`: host-side wall time around OpenCL submit and completion; not pure device time.
- `*_device_event_ms`: OpenCL event profiling for H2D copies, GPU kernel, D2H. **Host and device figures overlap and must not be summed.**
- `e2e_wall_ms`: host wall from pack start through simulated apply completion; includes Python/driver/wait overhead but excludes fixture generation, program compilation, GPU allocation and result validation.
- `cpu_e2e_median_ms`: same fixture processed by a NumPy reference with pack and apply copy. **Not the native Victoria 3 CPU performance.**
- `observed_*_device_gb_per_s`: copied bytes divided by device event time, not a direct measurement of bare PCIe bandwidth.

All iterations verify output exactly against CPU reference, including dtype and shape; any mismatch stops the run with no valid benchmark JSON. Includes warmup and 9 alternating cold/resident repetitions per case, raw timing samples plus summary medians. Tests use a fake backend strictly for scheduler orchestration; `gpu_executed` in a real measured JSON is only possible by successfully running an actual OpenCL executor.

## Verification and limitations

Implementation environment did **not** provide an available OpenCL GPU. Validated new CPU/controller tests (12), Clang syntax-check of both OpenCL 1.2 kernels, and the missing-device error path. **No physical GPU throughput or execution has been measured here.**

Synthetic speedups are not evidence of Victoria 3 1.14.5 game improvement. Native substitution remains blocked by task critical-path evidence, input ownership, deterministic ordering, object lifetime, reproducibility and multiplayer state checks.

PyOpenCL installation reference: https://documen.tician.de/pyopencl/misc.html#installation
OpenCL event profiling reference: https://github.com/KhronosGroup/OpenCL-Docs
