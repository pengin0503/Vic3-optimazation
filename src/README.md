# Native source

The repository is now ready to begin **Task 9 read-only native instrumentation** for Victoria 3 Windows 1.14.5.

The evidence gate for starting Task 9 was reached after the repeated benchmark baseline and PR #11 OS sampled/native execution evidence. The approved runtime plan is:

- docs/superpowers/plans/2026-10-05-read-only-native-profiler-runtime.md
- research/native-profiler-runtime-targets-1.14.5.json
- research/native-profiler-hook-abi-1.14.5.md
- research/native-profiler-event-format.md

The first native components are limited to an exact-build attach loader and observation-only profiler DLL. Unsupported builds must fail closed.

Do **not** add game-state-changing optimization patches, scheduler overrides, lock removal, cadence changes, or speculative parallelization here. Task 11/12 remain evidence-gated until Task 9 runtime overhead/correlation and the remaining CPU/wait/critical-path questions are resolved.
