# Native source

The **Task 9 read-only native instrumentation prototype** for Victoria 3 Windows 1.14.5 is implemented. Real-game attach, overhead and stability validation remain pending; see the operator guide and loader diagnostics below.

The evidence gate for starting Task 9 was reached after the repeated benchmark baseline and PR #11 OS sampled/native execution evidence. The approved runtime plan is:

- docs/superpowers/plans/2026-10-05-read-only-native-profiler-runtime.md
- research/native-profiler-runtime-targets-1.14.5.json
- research/native-profiler-hook-abi-1.14.5.md
- research/native-profiler-event-format.md

The first native components are limited to an exact-build attach loader and observation-only profiler DLL. Unsupported builds must fail closed.

## Layout

- `native/CMakeLists.txt` — Windows x64 only (configuration fails with a clear message elsewhere). C++20, shared CRT. MinHook is fetched by CMake `FetchContent` at exact commit `c3fcafdc10146beb5919319d0683e44e3c30d537` and compiled from source; no third-party binary is vendored. License: `third_party/licenses/MinHook.txt`.
- `native/generated/targets_1_14_5.inc` — generated, never hand-edited. Regenerate with `python tools/render_native_profiler_targets.py`; `--check` fails if the committed include is stale. The single maintained source is `research/native-profiler-runtime-targets-1.14.5.json`; the renderer rejects anything other than the three pinned tail anchors, a slot other than 6, a non-unique declared match count, malformed hex ranges, or an inconsistent signature offset.

Do **not** add game-state-changing optimization patches, scheduler overrides, lock removal, cadence changes, or speculative parallelization here. Task 11/12 remain evidence-gated until Task 9 runtime overhead/correlation and the remaining CPU/wait/critical-path questions are resolved.

## Offline lookup reuse core (`src/lookup_reuse/`)

[`lookup_reuse/`](lookup_reuse/README.md) is a separate, platform-neutral C++20 static library with tests and an offline runner (Stage A of the [lookup reuse / shadow design](../docs/superpowers/specs/2026-10-07-employment-lookup-reuse-shadow-design.md)). It works only on owned, immutable synthetic tables, always calls the original lookup in shadow mode and has no optimizing mode. It does not build or touch the native loader, DLL, hooks, live memory or the V3PF v1 profiler format, and it is not part of the Task 9 runtime plan. Native shadow (Stage B) remains gated on the evidence conditions in §8 of that design.

## Read-only native runtime (`src/native/`)

`native/` に exact Victoria 3 1.14.5 用の read-only prototype を実装しています。
Visual Studio 2022 / x64 / Release で configure・build・CTest を実施してください。
shared CRT のため Visual C++ 2022 x64 runtime が必要です。
loader は `--pid` 必須で、未知 build を injection 前に拒否します。
DLL は independent validation 後のみ 3 つの tail anchors を観測し、`--disabled` では 0 hooks。
終了は `--stop --pid`。DLL/trampoline はプロセス終了まで保持し、再計測はゲーム再起動から行います。
[operator guide](../docs/superpowers/guides/2026-10-05-native-profiler-runtime-validation-ja.md)
と [handoff](../docs/superpowers/reports/2026-10-05-native-profiler-runtime-implementation-handoff-ja.md) を参照。

Latest loader diagnosis: [module-resolution diagnostics](../docs/superpowers/reports/2026-10-06-loader-module-resolution-diagnostics-ja.md). Synthetic-host success does not establish real-game attach success.
