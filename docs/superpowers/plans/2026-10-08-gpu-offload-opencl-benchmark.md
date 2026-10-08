# GPU Offload OpenCL Offline Benchmark — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task, with test-driven-development and verification-before-completion.

**Goal:** Produce a standalone OpenCL 1.2 GPU feasibility benchmark for the user's Windows 11 / RX 7800 XT without opening Victoria 3 or modifying its state.

**Architecture:** Extend the already-approved offline feasibility project in PR #13 with a NumPy-only synthetic reference, an optional OpenCL GPU backend that fails closed, and a measured runner with raw timings. Host and device profiling are reported separately; CPU OpenCL may not silently masquerade as GPU. The user requested Native/in-line execution; no subagent is used.

**Tech Stack:** Python 3.11+, NumPy, optional PyOpenCL, OpenCL 1.2, unittest, Windows/Linux CPU-only CI.

**Spec:** [Issue #12](https://github.com/pengin0503/Vic3-optimazation/issues/12). The preceding [2026-10-08 feasibility report](../../research/gpu-offload-feasibility-2026-10-08-ja.md) is research context, not evidence of GPU execution.

## Global Constraints
- No game process attachment, native patch, hook, MOD installation, DLL injection or actual Victoria 3 simulation state mutation.
- Only exact integer result match qualifies; no speedup inference on non-GPU systems.
- Report host submit, host wait and OpenCL event duration without adding overlapping clocks.
- CPU OpenCL driver is **not** a GPU. Require one matching GPU.
- No user hardware is present in the implementation container. Real Radeon execution remains pending.

## Review Focus
- GPU driver missing / CPU-only platform: nonzero exit with error JSON, never measurement success.
- Input zero/one and high integer range: exact results and no 32-bit intermediate overflow.
- Misleading throughput metric: report observed command bandwidth, never nominal PCIe speed.
- Warmup and cold/resident workload pollution: explicit phase choice and alternated order.
- GPU failure/mismatch: stop before writing any successful result file.

### Task 1: Deterministic synthetic reference
**Files:** `research/experiments/gpu_offload_spike/offline_gpu_core.py`, `test_offline_gpu.py`
- [x] RED: missing reference module fails test import.
- [x] GREEN: 5 unit tests pass for two workloads, four scenarios, boundary counts, copy isolation and exact dtype/shape.
- [x] Preserve measured CPU reference interface: `make_case(kind,n,scenario,seed)`, `cpu_pipeline(case)`, `cpu_reference(case)`.

### Task 2: Optional GPU backend
**Files:** `gpu_opencl.py`, `test_gpu_backend.py`
- [x] RED: missing GPU backend module fails test import.
- [x] GREEN: four tests verify OpenCL kernels are present and CPU/nonmatching device is rejected.
- [x] Implement OpenCL 1.2 integer kernels with explicit device filter; log GPU event timing.
- [x] Compile extracted OpenCL source through Clang syntax checker (no GPU execution).

### Task 3: Repeated benchmark orchestration
**Files:** `gpu_runtime.py`, `test_gpu_runtime.py`
- [x] RED: missing runtime module fails test import.
- [x] GREEN: three tests verify cold/resident alternating order, required repeat counts and fail-closed error JSON.
- [x] Emit synthetic provenance, per-iteration raw time samples, device/driver metadata, CPU reference, cold vs resident comparison.
- [x] Validate GPU output on every iteration before reporting success.

### Task 4: Windows runbook, CI and handoff
**Files:** `README-opencl.md`, `.github/workflows/gpu-offload-offline.yml`
- [x] Provide PowerShell exact commands, result JSON paths, driver missing diagnostics and limitations.
- [x] Add Windows/Linux CPU-only CI.
- [ ] **Windows Actions actual verdict**: pending PR run; do not imply pass before GitHub reports it.
- [ ] **Real RX 7800 XT compute execution**: needs one user-side local run; current host has no eligible device.
- [ ] **Native game result equivalence and actual wall-time improvement**: separate future gate, not part of this phase.

## Commands and local evidence
```sh
cd research/experiments/gpu_offload_spike
python -m unittest discover -p 'test_*.py' -v
python gpu_runtime.py --sizes 8 --output no-device.json
# expected missing GPU: exit 2; status=error; gpu_executed=false
```

Local on implementation host: 12 new tests pass. Clang OpenCL 1.2 syntax checker exit=0. No device available; no GPU throughput or Windows executable claimed to have been tested. Full repository test suite and Windows job must be checked separately through CI; results are not part of this report.
