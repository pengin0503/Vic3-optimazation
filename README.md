# Vic3-optimazation

Private research project for improving Victoria 3 simulation performance beyond ordinary script/define tuning.

## Current state

Start here: [latest handoff — 2026-10-05](docs/superpowers/reports/2026-10-05-offline-quality-profiler-continuation-ja.md).

No native performance patch, DLL injection, scheduler override, or simulation-state modification has been implemented. Measurement/static-analysis tooling and the read-only profiler telemetry design are prepared; the remaining gate is repeatable runtime data plus synchronized OS-level profiling.

Earlier checkpoints remain under `docs/superpowers/reports/` for provenance and should not be treated as the current status when they conflict with the latest handoff.

## Target

- Victoria 3 Windows 1.14.5
- Caligula: `release/1.14.5` / `9f8281a37e85639359b3b0c2c5df0196e975ca4b`
- Clausewitz: `caligula/release/1.14.x` / `fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef`
- `victoria3.exe` SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Data policy

The private repository intentionally retains `input-data/Vic3_data.zip` through Git LFS because the exact combined input improves offline-analysis efficiency and reproducibility.

- LFS SHA-256: `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`
- size: 124,462,636 bytes

Smaller extracted inputs and preserved PC evidence remain under `input-data/`. The authoritative inventory and storage rules are in [research/input-data-manifest.md](research/input-data-manifest.md). Keep unrelated/low-value large game assets out of the repository and do not redistribute third-party game data without checking the applicable terms.

## Research rule

Measure first. Do not infer scheduler/lock causes from low aggregate CPU use alone, and do not introduce a native optimization until repeatability, OS-level evidence, exact-build validation, expected benefit, and semantic risk are understood.

## Next evidence gate

1. add two more measured runs each for TaskThreadCount 8, 12, and 16
2. validate the run set with `tools/check_benchmark_quality.py` and rerun scaling analysis
3. synchronize one 16-thread run with WPR/WPA or AMD uProf
4. classify the dominant bottleneck, then select only 1-3 Phase 4 read-only instrumentation targets

## Source of truth

- [design](docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md)
- [implementation plan](docs/superpowers/plans/2026-10-04-native-performance-optimization-implementation.md)
- [latest handoff](docs/superpowers/reports/2026-10-05-offline-quality-profiler-continuation-ja.md)
- [input-data manifest](research/input-data-manifest.md)
