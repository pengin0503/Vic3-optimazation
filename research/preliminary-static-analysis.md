# Victoria 3 1.14.5 Native Performance Research — Preliminary Static Analysis

## Input

- Archive: `Vic3_data.zip`
- Archive SHA-256: `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`
- Files in archive: 8,104 including macOS metadata entries
- Compressed size: 122,267,140 bytes
- Uncompressed size: 323,589,511 bytes

## Build identification

- `caligula_branch.txt`: `release/1.14.5`
- `caligula_rev.txt`: `9f8281a37e85639359b3b0c2c5df0196e975ca4b`
- `clausewitz_branch.txt`: `caligula/release/1.14.x`
- `clausewitz_rev.txt`: `fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef`
- `binaries/checksum.txt`: `d114f329e3bb6371cea63ab4e39a5efb`

## Main binary

- `victoria3.exe`: 97,774,200 bytes
- SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`
- PE32+ x86-64 GUI executable
- linker version: MSVC 14.44
- PE timestamp: 2026-09-29 07:49:45 UTC as stored in the PE header
- sections: `.text`, `.rdata`, `.data`, `.pdata`, `.rsrc`, `.reloc`
- ASLR/NX enabled
- embedded PDB path: `C:\mnt\gsg\caligula\caligula\outputdir_windows\binaries\victoria3.pdb`
- exports observed: `AmdPowerXpressRequestHighPerformance`, `NvOptimusEnablement`

## Internal names retained

At least 910 unique internal source-path strings are recoverable. Relevant examples:

- `cw/clausewitz/pdx_core/thread/pdx_task.cpp`
- `cw/clausewitz/pdx_core/thread/pdx_graphjob.cpp`
- `cw/clausewitz/pdx_core/thread/pdx_task_scheduler.cpp`
- `cw/clausewitz/pdx_core/thread/pdx_workset.h`
- `source/logic/gamestatetick.cpp`
- `source/logic/ingameidler.cpp`
- `source/logic/employment_helper.cpp`
- `source/logic/employment_utils.cpp`
- `source/logic/pop.cpp`
- `source/logic/popmanager.cpp`
- `source/logic/market.cpp`
- `source/logic/market_goods.cpp`
- `source/logic/world_market.cpp`
- `source/logic/modifier.cpp`
- `source/ai/ai_manager.cpp`
- `source/ai/country_ai.cpp`

RTTI/template strings expose `CPdxParallelForDescriptor`, `SPdxParallelFor`, `CNonBlockingJob`, and `MaybeRunRangeExecutionParallelWithHeuristic`. This confirms an internal parallel-for/job system with runtime heuristics.

## TickTask inventory

At least 260 distinct `CTickTask_*` names are recoverable. Examples:

- `CTickTask_UpdateEmployment`
- `CTickTask_UpdateStatePopNeedCache`
- `CTickTask_UpdateMarketCachedPopNeedExpenses`
- `CTickTask_ProcessPopPurchases`
- `CTickTask_RecalculateModifierNodes`
- `CTickTask_UpdateWorldMarket`
- `CTickTask_UpdateAI`
- `CTickTask_UpdateAIGoals`
- `CTickTask_UpdateAIStrategies`
- `CTickTask_UpdateStateTrades`
- `CTickTask_UpdatePriceReports`
- `CTickTask_UpdatePopGrowth`
- `CTickTask_MergeSmallPops`

## Built-in profiling discovered

### TickTask debugger

`game/gui/ticktask_debugger.gui` exposes task name/index, execution rate, priority, highest lock time, average execution time, execution count, dependency graph, and task details. The GUI directly references accessors equivalent to highest-lock-time, average-time, and execution-count fields, reinforcing that the built-in TickTask data is intended for per-task timing and lock diagnosis rather than only aggregate frame timing.

Console/UI paths include:

- `TickTask.List`
- `TickTask.Graph`
- `clear_ticktask_timings`
- `dump_ticktask_timings`
- `log_ticktask_performance`

The CSV header for dumped timings is:

`frame,task,milliseconds,calls,longest_lock`

Default output filename observed in the executable: `ticktask_timings.csv`.

Neighboring strings confirm the semantics:

- `dump_ticktask_timings`: writes the TickTask timings already recorded to a file
- `clear_ticktask_timings`: discards timings recorded so far so the next dump covers only what follows
- `log_ticktask_performance`: enables continuous TickTask performance output to `profiling.log`

The executable also contains `Could not write %s` and `Wrote %d rows to %s`, which should make first-run path verification straightforward.

### Thread controls

- `Threading.TaskThreadCount`
- `Threading.EnableTaskThreads`
- worker-thread related internal strings
- `AddPredefinedTaskThread`

Windows imports show SRW locks, condition variables, semaphores, `SwitchToThread`, `SetThreadPriority`, `CreateThread`, and `QueryPerformanceCounter`.

### Script profiler

Interfaces/commands include:

- `Script.Profiling.Gui`
- `Script.Profiling.Start`
- `Script.Profiling.Stop`
- `Script.Profiling.Restart`
- `ScriptProfiling.Enable`
- `ScriptProfiling.Dump`

Output path observed: `logs/script_profiling.txt`.

### GUI and frame/thread profilers

- `jomini/gui/gui_data_profiler/gui_data_profiler.gui`
- `Tools.GuiDataProfiler`
- `clausewitz/gui/profiler.gui`
- profiler selection and CSV-output functions are referenced

### Optick

`optick_capture` exists, but the retail build contains:

`This build was compiled without an instrumented profiler`

Do not depend on Optick for this build.

### Other hooks

`goods_pool_performance_test` exists and is described as running CGoodsPool tests for profiler evaluation.

## Design consequence

Do not start by injecting a DLL or rewriting Employment.

Correct order:

1. deterministic heavy-save benchmark
2. built-in TickTask timing and lock data
3. TaskThreadCount scaling test
4. Script/GUI profiling
5. OS-level wait/lock/cache profiling
6. reverse-engineer only measured hotspots
7. read-only native instrumentation
8. safe patch candidates
9. experimental scheduler/simulation work only if evidence justifies it

The 1.14.5 executable is favorable for reverse engineering because source paths, RTTI/template names, TickTask names, internal profiler interfaces, and console commands remain present.
