# Victoria 3 Native Performance Optimization — Design

Date: 2026-10-04
Target: Victoria 3 Windows 1.14.5

## 2026-10-13 route amendment

The user authorized completing the proposed external-measurement route until real measurement is the next prerequisite. [External CPU route design](2026-10-13-external-cpu-route-design.md) is the current investigation path: existing built-in TickTask CSV plus WPR/WPA, without requiring successful custom DLL attachment. Layer C / native Phase4 remains an independent, incomplete workstream. Its loader safety checks and runtime acceptance are unchanged. Evidence-backed candidate selection may proceed from external observations; native ABI, lifetimes, semantic equivalence, safe patch application and wall-clock A/B validation remain required for any eventual patch. This amendment does not authorize lookup bypass, scheduling changes or forced attachment.

## Problem

Victoria 3 can become simulation-bound while total CPU utilization remains low. The goal is not to maximize aggregate CPU utilization; it is to reduce simulation wall-clock time while preserving deterministic, stable game behavior.

The project explicitly avoids performance gains that primarily come from removing cultures, merging content, reducing countries, or otherwise simplifying the simulated world. Those approaches may remain useful controls, but they are not the primary objective.

## Evidence already available

Static analysis of the supplied 1.14.5 build shows that `victoria3.exe` retains unusually useful internal metadata:

- source-path strings including `pdx_task.cpp`, `pdx_graphjob.cpp`, `pdx_task_scheduler.cpp`, `pdx_workset.h`, `gamestatetick.cpp`, `employment_helper.cpp`, `pop.cpp`, `market.cpp`, `world_market.cpp`, and `modifier.cpp`
- more than 260 `CTickTask_*` class names
- `CPdxParallelForDescriptor`, `SPdxParallelFor`, `CNonBlockingJob`, and `MaybeRunRangeExecutionParallelWithHeuristic`
- built-in profiling commands and GUI paths

Relevant TickTasks include:

- `CTickTask_UpdateEmployment`
- `CTickTask_UpdateStatePopNeedCache`
- `CTickTask_UpdateMarketCachedPopNeedExpenses`
- `CTickTask_ProcessPopPurchases`
- `CTickTask_RecalculateModifierNodes`
- `CTickTask_UpdateWorldMarket`
- `CTickTask_UpdateAI`
- `CTickTask_UpdateStateTrades`
- `CTickTask_UpdatePopGrowth`
- `CTickTask_MergeSmallPops`

Built-in diagnostics include:

- `TickTask.List`
- `TickTask.Graph`
- `clear_ticktask_timings`
- `dump_ticktask_timings`
- `log_ticktask_performance`
- `Threading.TaskThreadCount`
- `Threading.EnableTaskThreads`
- Script Profiler
- GUI Data Profiler
- Clausewitz frame/thread profiler

`dump_ticktask_timings` emits `frame,task,milliseconds,calls,longest_lock`.

## Design principles

1. **Measure before patching.** Native modification begins only after reproducible profiling identifies an actual bottleneck.
2. **Wall-clock simulation speed is the primary metric.** CPU utilization is diagnostic, not a success criterion.
3. **Preserve game semantics.** Performance changes should avoid changing population, culture, economy, AI rules, or simulation frequency unless the user explicitly chooses such a mode.
4. **Determinism matters.** Parallelization that changes state-update ordering is treated as experimental until long-run tests prove save stability and multiplayer/determinism behavior.
5. **No fixed addresses.** Native hooks use build hash + signature scan + structural validation + fail-safe disable.
6. **Unsupported builds fail closed.** A signature mismatch must leave the game unmodified.
7. **Read-only instrumentation first.** The first native component only measures.
8. **Research inputs are explicit and fail-closed.** Keep the repository private. The approved combined research archive `input-data/Vic3_data.zip` is retained through Git LFS because exact-input availability improves reproducibility and offline analysis; unrelated/low-value large game assets remain outside the repository. Every retained raw input must be documented with provenance/hash, and executable-derived conclusions still require exact build/hash validation.

## Architecture

### Layer A — Benchmark harness

Responsibilities:

- launch or prepare a known save
- apply a fixed benchmark protocol
- clear built-in timing buffers
- run for a fixed in-game interval
- dump TickTask timing CSV
- record wall-clock duration
- record build and configuration metadata
- optionally collect WPR/WPA or AMD uProf traces

Outputs are immutable run directories with metadata and raw profiler artifacts.

### Layer B — Static analysis toolkit

Reusable scripts extract:

- PE metadata
- imports/exports
- source-path strings
- TickTask names
- RTTI/template names
- internal console/profiler command strings
- candidate byte/signature patterns
- build hashes

Ghidra/IDA projects remain local. Exported symbol maps and research notes may be committed.

### Layer C — Read-only native profiler

Only after Layers A/B are stable.

Responsibilities:

- identify validated target functions
- timestamp calls
- associate activity with threads/tasks where possible
- measure wait/lock/dispatch behavior
- expose no state mutation
- automatically disable on unsupported builds

### Layer D — Safe native patches

Candidates require direct benchmark evidence. Examples may include:

- redundant recalculation avoidance
- cache lifetime fixes
- unnecessary repeated GUI/data-binding work
- pathological alert/UI update loops
- task dispatch overhead where semantics are unchanged

Each patch is individually toggleable.

### Layer E — Experimental scheduler/simulation patches

Reserved for evidence-backed cases such as:

- poor task chunking
- scheduler heuristic under-utilization
- excessive barriers
- lock contention with a safe restructuring path
- read-only parallel work that can be isolated from state mutation

Experimental patches remain off by default.

## Benchmark protocol

Use one heavy save and a fixed camera/UI state. A benchmark run records:

- game build hashes
- save hash
- CPU/thread-count configuration
- graphics/UI state
- game speed
- start/end in-game date
- real elapsed time
- `ticktask_timings.csv`
- profiler logs
- per-thread CPU data when available

For `Threading.TaskThreadCount`, test a scaling set appropriate to the host CPU. Initial set: 1, 2, 4, 6, 8, 12, 16.

Repeat each configuration at least three times after one warm-up run. A result is actionable only if the variance is small enough to separate the proposed optimization from noise.

## Bottleneck classification

A hotspot is classified before remediation:

- **serial compute** — one critical task dominates and does not scale with TaskThreadCount
- **lock contention** — `longest_lock` and OS traces indicate waiting
- **barrier/dependency stall** — worker idle time increases while one dependency chain remains active
- **scheduler overhead** — many tiny jobs with dispatch overhead
- **memory/cache bound** — CPU execution remains stalled despite available workers
- **script bound** — Script Profiler dominates
- **GUI/GameState synchronization bound** — GUI/data-binding or render-side state access delays simulation

The fix must match the class; increasing worker count is not a generic remedy.

## Safety and compatibility

Every native patch must have:

- exact supported build IDs
- executable SHA-256
- byte/signature scan
- validation of nearby code/control-flow assumptions
- fail-safe disable
- separate feature flag
- benchmark before/after
- crash and long-run save test

No patch should silently apply to an unknown executable.

## Phase-1 completion criteria

Before native optimization begins, the project must be able to answer:

- Which TickTasks dominate the heavy save?
- Which tasks have meaningful lock time?
- How does throughput scale from 1 to 16 task threads?
- Are script or GUI costs material?
- Is the primary limitation serial compute, waiting, dispatch, or memory behavior?
- Which one to three native functions are the highest-value reverse-engineering targets?
