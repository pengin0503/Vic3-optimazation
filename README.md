# Vic3-optimazation

Private research project for improving Victoria 3 simulation performance beyond ordinary script/define tuning.

## Current status / resume

Latest handoff:

- [2026-10-05 Offline benchmark quality gate and profiler telemetry design](docs/superpowers/reports/2026-10-05-offline-quality-profiler-continuation-ja.md)

Current state:

- no native performance patch, DLL injection, scheduler override, or simulation-state modification has been implemented
- benchmark/static-analysis tooling is established
- the Phase 4 read-only profiler telemetry format is designed but not implemented
- the immediate evidence gate is repeatability plus one synchronized OS-level profile

Useful earlier checkpoints:

- [PC evidence preservation and nine-task analysis](docs/superpowers/reports/2026-10-05-pc-evidence-preservation-ja.md)
- [Dispatcher and Employment callback follow-up](docs/superpowers/reports/2026-10-05-dispatch-continuation-ja.md)
- [Source-backed native mapping continuation](docs/superpowers/reports/2026-10-05-source-backed-continuation-ja.md)
- [Runtime benchmark handoff](docs/superpowers/reports/2026-10-05-runtime-benchmark-handoff-ja.md)

Historical reports remain in the repository for provenance; use the latest handoff above for current decisions.

## Current target

- Victoria 3 Windows 1.14.5
- Caligula: `release/1.14.5` / `9f8281a37e85639359b3b0c2c5df0196e975ca4b`
- Clausewitz: `caligula/release/1.14.x` / `fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef`
- `victoria3.exe` SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Research rules

- measure first; do not start by forcing more worker threads or patching Employment
- correlate built-in TickTask data with repeatable wall-clock measurements and OS-level CPU/wait evidence
- do not infer a scheduler or lock bottleneck from low aggregate CPU utilization alone
- fail closed on unsupported executable builds
- do not introduce a native optimization until its expected benefit is larger than benchmark noise and its semantics/risk are understood

## Repository inputs

This repository is private.

The combined research archive is intentionally retained at `input-data/Vic3_data.zip` through Git LFS because direct access to the exact research input makes repeated offline analysis and cross-device continuation more efficient.

- LFS object SHA-256: `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`
- LFS object size: 124,462,636 bytes

Smaller extracted inputs remain available for lightweight work:

- `input-data/jomini.zip`
- `input-data/clausewitz.zip`
- `input-data/game.zip`
- `input-data/build-info/`

Additional logs, benchmark material, inventories, sensor data, and a recoverable benchmark save are under `input-data/pc-evidence-2026-10-05/` with provenance documented in the PC-evidence report.

Keep unrelated/low-value large game assets out of the repository. Treat third-party game data as private research material and review the applicable license/copyright terms before any redistribution.

See [research/input-data-manifest.md](research/input-data-manifest.md) for the authoritative input inventory and storage policy.

## Source of truth

For current work, read in this order:

1. [approved design](docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md)
2. [implementation plan](docs/superpowers/plans/2026-10-04-native-performance-optimization-implementation.md)
3. [latest handoff](docs/superpowers/reports/2026-10-05-offline-quality-profiler-continuation-ja.md)
4. [input-data manifest](research/input-data-manifest.md)

## Immediate evidence gate

Use the same benchmark save and three-month interval:

1. add two measured runs each for TaskThreadCount 8, 12, and 16 so each condition has three observations
2. run `tools/check_benchmark_quality.py`
3. rerun benchmark/scaling analysis
4. synchronize one 16-thread run with WPR/WPA or AMD uProf
5. classify the dominant limitation as compute, dependency/barrier, lock, scheduler/granularity, or memory/cache
6. only then select the first 1-3 Phase 4 read-only instrumentation targets

The full 1/2/4/6/8/12/16 matrix remains useful, but it is not required before this shorter evidence gate.
