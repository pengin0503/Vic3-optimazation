# Vic3-optimazation

Private research project for improving Victoria 3 simulation performance beyond ordinary script/define tuning.

## Current state

Start here: [latest repeated benchmark analysis — 2026-10-05](docs/superpowers/reports/2026-10-05-repeated-benchmark-analysis-ja.md).
The [offline implementation handoff](docs/superpowers/reports/2026-10-05-offline-three-plan-handoff-ja.md) remains the entry point for the prepared static/OS/profiler tools.

No native performance patch, DLL injection, scheduler override, or simulation-state modification has been implemented. Measurement/static-analysis tooling and the offline profiler reference codec/parser are prepared; the new nine-run batch has low observed timing variation. Mean wall times are 37.043 / 34.517 / 34.777 seconds for 8 / 12 / 16 task threads. Use 12 as the diagnostic baseline and 16 as the comparison; this does not establish an optimum. One 12-thread CSV has three extra trailing frames, so strict equal-boundary repeatability still needs that boundary checked. Synchronized OS-level profiling remains required before selecting a native optimization.

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

1. use the [preserved nine runs](benchmarks/measured-2026-10-05-3month-repeats/) and [verified analysis](research/generated/repeats-2026-10-05/repeat-evidence.json); keep historical single observations separate
2. check the 12_r2 end boundary: common-frame task/call workload matches, but the raw CSV has three extra frames; the current quality gate does not check this
3. synchronize matched 12- and 16-thread runs with WPR/WPA or AMD uProf, using automatic boundary timestamps and alternating execution order
4. classify CPU work, scheduling and waiting; prioritize HandleAutonomousInvestment, ProcessEconomicMigration and UpdateEmployment for read-only investigation

## Source of truth

- [design](docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md)
- [implementation plan](docs/superpowers/plans/2026-10-04-native-performance-optimization-implementation.md)
- [latest measurements and development decision](docs/superpowers/reports/2026-10-05-repeated-benchmark-analysis-ja.md)
- [offline tooling handoff](docs/superpowers/reports/2026-10-05-offline-three-plan-handoff-ja.md)
- [input-data manifest](research/input-data-manifest.md)
