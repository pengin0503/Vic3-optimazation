# Vic3-optimazation

Private research project for improving Victoria 3 simulation performance beyond ordinary script/define tuning.

## Current target

- Victoria 3 Windows 1.14.5
- Caligula: `release/1.14.5` / `9f8281a37e85639359b3b0c2c5df0196e975ca4b`
- Clausewitz: `caligula/release/1.14.x` / `fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef`
- `victoria3.exe` SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Project rule

Do not start by patching Employment or forcing more worker threads. First establish reproducible measurements, use Victoria 3's built-in TickTask/Script/GUI profilers, and identify the actual serial, locking, scheduling, or task-cost bottleneck.

## Repository boundary

This repository stores only original source code, scripts, signatures/hashes, plans, and research results. Paradox binaries/assets are kept out of this repository.

See:

- `docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md`
- `docs/superpowers/plans/2026-10-04-native-performance-optimization-implementation.md`
- `research/preliminary-static-analysis.md`

## Initial completion criterion

Phase 1 is complete only when the same heavy save can be benchmarked repeatedly and produces comparable:

- simulation wall-clock throughput
- TickTask timing CSV
- longest-lock data
- TaskThreadCount scaling results
- script/UI profiler results where relevant

No native performance patch is considered justified until that baseline exists.
