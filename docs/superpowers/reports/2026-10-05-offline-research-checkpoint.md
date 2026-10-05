# Offline research checkpoint — 2026-10-05

> Historical checkpoint: real runtime benchmarks and measured hotspot mappings were added after this report. For current status and resume instructions, read [2026-10-05 runtime benchmark handoff](2026-10-05-runtime-benchmark-handoff-ja.md). The original research and verification history below is preserved.


Repository: `pengin0503/Vic3-optimazation`  
Branch: `main`  
Checkpoint base/head before this report: `696ae7029c04885c739228139a40c19221ca6b05`  
Target: Victoria 3 Windows 1.14.5  
Executable SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Purpose of this checkpoint

The user requested that work be stopped safely, progress be reported, and all current work be preserved in the repository.

This checkpoint records all meaningful work completed without requiring the Windows Victoria 3 runtime and identifies the remaining evidence gates.

## Current repository health

The latest GitHub Actions run for commit `696ae7029c04885c739228139a40c19221ca6b05` completed successfully.

The recent offline-analysis/tooling commits also completed successfully in CI, including:

- TickTask RTTI/vtable mapper
- exact-build signature generation/validation
- static xref mapper
- build migration comparator
- offline static pipeline
- performance-control extractor
- benchmark target triage
- TaskThreadCount scaling diagnostics
- Pop Consolidation benchmark metadata
- scheduler/range-parallel static analysis
- conservative TickTask vtable semantics notes

At this checkpoint there is no known failing repository test or CI failure.

## Work completed in the offline/non-Windows phase

### 1. Reproducible static-analysis pipeline

The project now has a dependency-free Python pipeline capable of analyzing a local Victoria 3 executable or research ZIP.

Core tools:

- `tools/analyze_vic3.py`
- `tools/map_static_xrefs.py`
- `tools/map_ticktask_rtti.py`
- `tools/generate_signatures.py`
- `tools/validate_exact_signatures.py`
- `tools/compare_static_analysis.py`
- `tools/extract_performance_controls.py`
- `tools/run_static_pipeline.py`

The one-command pipeline produces:

- PE/build metadata
- imports/exports
- embedded PDB path
- source-path strings
- TickTask names
- candidate code xrefs
- TickTask RTTI/vtable mappings
- exact-build signature validation
- summary metadata

The pipeline is designed to fail closed when validation does not match expectations.

### 2. TickTask RTTI and vtable recovery

The 1.14.5 executable contains:

- 260 distinct `CTickTask_*` names
- 258 matching concrete MSVC RTTI TypeDescriptors
- 258 validated Complete Object Locators
- 258 mapped vtables

Only these two TickTask names did not map to a matching concrete RTTI class:

- `CTickTask_CheckNonFulfillments`
- `CTickTask_MoveFormations`

Vtable shape:

- 189 classes use 7 slots
- 69 classes use 8 slots

A major static finding is that the **final virtual slot is unique for every mapped concrete TickTask class**.

The project intentionally calls this:

`task_specific_tail_vfunc`

It does not assign an unproven source-level method name such as `Execute`.

### 3. High-value TickTask native anchors

The project has deterministic native anchors for several likely runtime hotspots.

Examples:

| TickTask | Vtable RVA | Task-specific tail virtual |
| --- | ---: | ---: |
| `CTickTask_UpdateEmployment` | `0x4590800` | `0x13b8310` |
| `CTickTask_UpdateStatePopNeedCache` | `0x4590dd8` | `0x13b7e70` |
| `CTickTask_ProcessPopPurchases` | `0x4550fd8` | `0xee74b0` |
| `CTickTask_RecalculateModifierNodes` | `0x44d8f58` | `0x7da740` |
| `CTickTask_UpdateWorldMarket` | `0x4551108` | `0xedf260` |
| `CTickTask_UpdateAI` | `0x459f140` | `0x1575530` |
| `CTickTask_UpdateStateTrades` | `0x4590c80` | `0x13b7bd0` |
| `CTickTask_UpdatePopGrowth` | `0x458efd0` | `0x13a3020` |
| `CTickTask_MergeSmallPops` | `0x458ee90` | `0x13aacd0` |

This means that once a runtime CSV identifies a hot TickTask, the project no longer needs broad string hunting to find its first native code anchor.

### 4. Conservative vtable semantics analysis

Shared TickTask interface slots were inspected without inventing source method names.

Observed common structure includes:

- slot 1: shared wrapper at `0x3bf7200`
- slot 3: shared wrapper at `0x3bf7270`
- `0x62d680`: minimal return/no-op style stub used by common slots
- most classes share slot 4 at `0x1808250`
- all 69 eight-slot classes share slot 6 at `0x7d76b0`
- final slot is class-specific

For `CTickTask_UpdateEmployment`, the tail function `0x13b8310–0x13b853b` clearly performs nontrivial task-specific setup/work-dispatch activity.

However, the project deliberately does **not** assume this direct function contains the entire Employment cost. It may prepare child/range work that executes elsewhere.

### 5. Scheduler / range-parallel heuristic mapping

The string `MaybeRunRangeExecutionParallelWithHeuristic` maps to native function:

`0x7db150–0x7dba91`

One validated caller is:

`0x7dbaa0–0x7dc13e`

That caller also references:

`RunRangeExecutionParallel`

Static analysis shows the heuristic is substantially more sophisticated than a fixed threshold.

It visibly computes/uses:

- range size
- task-system/global counts
- historical per-range values
- minimum
- maximum
- arithmetic mean
- variance
- square root / standard deviation
- an approximate `mean + 2 * standard_deviation` threshold
- a true/false decision for constructing parallel work

This matters because low total CPU utilization can result from intentional heuristic rejection, poor granularity, dependency stalls, locking, or memory behavior. Increasing worker count alone is not a justified fix.

The scheduler remains an **experimental target only after runtime scaling evidence**.

### 6. Exact-build fail-closed signatures

The repository contains exact 1.14.5 byte-window validators for selected high-value anchors.

Examples include:

- TickTask CSV writer
- TaskThreadCount handler
- TaskThreadCount thunk
- EnableTaskThreads thunk
- range-parallel heuristic
- GUI Data Profiler handler
- Clausewitz profiler CSV handler
- game-timer writer
- scripted-tests registration

These signatures are explicitly restricted to the exact executable hash.

They are not treated as cross-version signatures.

### 7. Build-update migration tooling

`tools/compare_static_analysis.py` compares two Victoria 3 builds.

Any executable hash change produces:

`revalidate-all-native-targets-before-enabling-hooks`

even when strings or RTTI appear unchanged.

This establishes the intended safety model for future game updates.

### 8. Built-in profiling / runtime interfaces mapped

Confirmed useful interfaces include:

- `TickTask.List`
- `TickTask.Graph`
- `clear_ticktask_timings`
- `dump_ticktask_timings`
- `log_ticktask_performance`
- `Threading.TaskThreadCount`
- `Threading.EnableTaskThreads`
- Script Profiler commands
- GUI Data Profiler
- Clausewitz frame/thread profiler
- scripted-test framework
- Jomini game-timer writer lead

The project has validated static code anchors for several of these handlers.

### 9. Benchmark workflow is ready

Repository-side benchmark workflow is implemented.

Preparation:

- `tools/prepare_benchmark_matrix.py`

Finalization:

- `tools/finalize_benchmark_run.py`

Analysis:

- `tools/analyze_benchmarks.py`
- `tools/analyze_thread_scaling.py`
- `tools/triage_benchmark_targets.py`

Default full matrix:

- TaskThreadCount: 1, 2, 4, 6, 8, 12, 16
- one warm-up per setting
- three measured runs per setting
- 28 planned runs total

The benchmark manifest now records the Pop Consolidation setting so Pop-object workload differences cannot silently contaminate results.

### 10. Performance-sensitive shipped controls catalogued

The project now records performance-related first-party controls from the shipped data, including:

- Journal Entry update cadence
- trade-potential refresh cadence
- AI goal update budgets
- government-alternative combinatorial limits
- autonomous investment cadence
- autonomous trade failure budgets
- Trade Center construction thresholds
- Pop Consolidation game rule / merge thresholds
- GUI/map update amortization controls
- battle-condition cadence

These are treated as:

- workload metadata,
- causal A/B controls,
- optional later compatibility presets,

not as the primary native optimization strategy.

### 11. Read-only native architecture is selected but intentionally not implemented

Selected future architecture:

`Vic3OptimizationLoader.exe -> explicit attach/injection -> Vic3OptimizationProfiler.dll`

Safety requirements already documented:

- executable SHA-256 gate
- independent DLL-side validation
- section-aware signature scan
- surrounding-code validation
- optional RTTI/vtable validation
- unsupported build fails closed
- no raw absolute address as primary locator
- read-only instrumentation first
- hot hooks avoid allocation, file I/O, and locking

Native implementation remains intentionally blocked until runtime evidence identifies the actual target functions.

## Important repository files at checkpoint

Research:

- `research/preliminary-static-analysis.md`
- `research/binary-map.md`
- `research/static-xref-map.md`
- `research/ticktask-map.md`
- `research/ticktask-rtti-findings.md`
- `research/ticktask-vtable-semantics.md`
- `research/scheduler-heuristic-static-analysis.md`
- `research/performance-controls.md`
- `research/runtime-automation-findings.md`
- `research/os-profiling-plan.md`
- `research/hook-feasibility.md`

Generated/reference metadata:

- `research/generated/ticktasks-1.14.5.txt`
- `research/generated/profiler-commands-1.14.5.txt`
- `research/generated/imports-1.14.5.txt`
- `research/generated/exact-signatures-1.14.5.json`
- `research/generated/ticktask-vtable-high-value-1.14.5.json`

Tools:

- `tools/analyze_vic3.py`
- `tools/map_static_xrefs.py`
- `tools/map_ticktask_rtti.py`
- `tools/generate_signatures.py`
- `tools/validate_exact_signatures.py`
- `tools/compare_static_analysis.py`
- `tools/extract_performance_controls.py`
- `tools/run_static_pipeline.py`
- `tools/prepare_benchmark_matrix.py`
- `tools/finalize_benchmark_run.py`
- `tools/analyze_benchmarks.py`
- `tools/analyze_thread_scaling.py`
- `tools/triage_benchmark_targets.py`

## What is still blocked on Windows/runtime evidence

The project cannot responsibly progress to performance-changing native code without these measurements:

1. a heavy late-game save,
2. fixed-date Speed 5 wall-clock timings,
3. `ticktask_timings.csv`,
4. TaskThreadCount scaling,
5. at least one matching WPR/WPA or AMD uProf capture,
6. Script Profiler / GUI Profiler pass where relevant.

After those exist, the current tooling can immediately:

- rank hot TickTasks,
- identify lock-heavy tasks,
- diagnose weak/strong thread scaling,
- map runtime hotspot names to RTTI/vtable native anchors,
- reduce reverse engineering to the top 1–3 actual targets.

## Current issue status

### Issue #1 — Phase 1 benchmark pipeline

Repository/tooling portion is effectively complete.

Issue remains open because real runtime benchmark data has not yet been collected.

### Issue #2 — OS-level profiling

Documentation is complete.

Issue remains open pending a real WPR/WPA or AMD uProf capture.

### Issue #3 — Native mapping

Static foundation is now substantially ahead of the original plan:

- 258 concrete TickTask vtables mapped,
- high-value native tail anchors recorded,
- scheduler heuristic mapped,
- exact validators available.

Issue remains open because it specifically requires mapping the **measured** top hotspots after Phase 1/2.

### Issue #4 — Read-only native instrumentation

Architecture and safety model are complete.

Implementation remains intentionally blocked by the evidence gate.

### Issues #5–#6

Not started, correctly.

They require evidence from the earlier phases.

## Safe resume point

A future session should treat commit `696ae7029c04885c739228139a40c19221ca6b05` plus this checkpoint commit as the saved source of truth.

The next highest-value action is no longer broad static reverse engineering.

It is to collect the first real Windows benchmark dataset and feed it through the existing analysis/triage pipeline.

If Windows is still unavailable, further offline work should be limited to targeted call-graph/dependency analysis of already-mapped anchors and tooling hardening, not speculative performance patches.
