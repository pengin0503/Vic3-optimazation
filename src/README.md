# Native source

The repository is now ready to begin **Task 9 read-only native instrumentation** for Victoria 3 Windows 1.14.5.

The evidence gate for starting Task 9 was reached after the repeated benchmark baseline and PR #11 OS sampled/native execution evidence. The approved runtime plan is:

- docs/superpowers/plans/2026-10-05-read-only-native-profiler-runtime.md
- research/native-profiler-runtime-targets-1.14.5.json
- research/native-profiler-hook-abi-1.14.5.md
- research/native-profiler-event-format.md

The first native components are limited to an exact-build attach loader and observation-only profiler DLL. Unsupported builds must fail closed.

Do **not** add game-state-changing optimization patches, scheduler overrides, lock removal, cadence changes, or speculative parallelization here. Task 11/12 remain evidence-gated until Task 9 runtime overhead/correlation and the remaining CPU/wait/critical-path questions are resolved.

## Offline lookup reuse core (`src/lookup_reuse/`)

[`lookup_reuse/`](lookup_reuse/README.md) is a separate, platform-neutral C++20 static library with tests and an offline runner (Stage A of the [lookup reuse / shadow design](../docs/superpowers/specs/2026-10-07-employment-lookup-reuse-shadow-design.md)). It works only on owned, immutable synthetic tables, always calls the original lookup in shadow mode and has no optimizing mode. It does not build or touch the native loader, DLL, hooks, live memory or the V3PF v1 profiler format, and it is not part of the Task 9 runtime plan. Native shadow (Stage B) remains gated on the evidence conditions in §8 of that design.
