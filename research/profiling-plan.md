# Phase 1 profiling plan

Target build: Victoria 3 Windows 1.14.5

This protocol exists to answer one question before native patching begins: **what actually limits simulation wall-clock throughput on a reproducible heavy save?**

The primary metric is elapsed real time for a fixed in-game interval. CPU utilization is diagnostic only.

## 1. Benchmark save

Choose one late-game save where speed 5 is clearly CPU/simulation limited.

Record:

- save filename and SHA-256
- in-game date
- country being observed/played
- DLC state
- mod playset; use vanilla/no third-party mods for the primary baseline unless the test explicitly targets a modded configuration
- graphics preset/resolution
- VSync/frame cap state
- camera position and zoom
- open UI panel, if any

Do not change these between measured runs.

A second, early-game control save is useful later, but it is not required for the first Phase 1 pass.

## 2. Host controls

For all runs:

- use the same Windows power plan
- avoid Windows Update, game downloads, browser video, compilation, and other heavy background work
- keep the same CPU firmware/BIOS settings
- do not change processor affinity or priority unless a test explicitly studies it
- allow the machine to reach a stable idle/thermal state before starting
- record whether the run follows a cold game launch or is repeated in the same process

The first run after launch is a warm-up and is not used in the primary averages.

## 3. Fixed simulation interval

Prefer exactly one in-game year if the save is slow enough to give a useful measurement. If one year is impractically long, use a fixed six-month interval.

Example:

- start: `1900-01-01`
- end: `1901-01-01`
- speed: 5

The interval must be identical for every TaskThreadCount tested.

Do not use a variable "run for 60 real seconds" interval for the primary benchmark because it changes the amount of simulation work completed.

## 4. Built-in TickTask capture

Before each measured run:

1. load the benchmark save
2. pause the game
3. set the requested task-thread count with `Threading.TaskThreadCount <count>`
4. confirm the console accepted the value
5. return to the fixed camera/UI state
6. run `clear_ticktask_timings`
7. start the wall-clock timer and unpause at speed 5
8. stop when the fixed end date is reached
9. pause immediately
10. record elapsed wall-clock seconds
11. run `dump_ticktask_timings`
12. copy the resulting TickTask CSV into that run directory as `ticktask_timings.csv`

The 1.14.5 executable contains the command help string:

`Use Threading.TaskThreadCount [count].`

Static analysis of 1.14.5 confirms the default output filename is `ticktask_timings.csv`. The executable also contains `Could not write %s` and `Wrote %d rows to %s`, so the first real run should still record the actual resolved output path rather than assuming the working directory.

The nearby command/help strings also suggest a file-name argument may exist, but its exact console syntax has not yet been runtime-verified; do not depend on it for the first benchmark.

## 5. TaskThreadCount matrix

Initial values:

`1, 2, 4, 6, 8, 12, 16`

For each value:

- 1 warm-up run
- at least 3 measured runs

Recommended order for the first pass is ascending thread count. If thermal drift appears material, repeat the matrix in a different order and compare.

Do not infer a scheduler defect merely because 16 is not faster than 8. A serial dependency chain, lock, memory stall, or poor task granularity can all produce that result.

## 6. Run directory layout

Use one immutable directory per run:

```text
benchmarks/runs/
  vanilla-t01-r01/
    manifest.json
    ticktask_timings.csv
  vanilla-t01-r02/
    manifest.json
    ticktask_timings.csv
  ...
```

Do not edit a measured run in place. If a metadata error is found, create a corrected run and mark the old run excluded in notes or move it outside the measured dataset.

## 7. Manifest

Create each `manifest.json` from `benchmarks/manifest.example.json`.

Required fields used by `tools/analyze_benchmarks.py`:

- `run_id`
- `variant`
- `task_thread_count`
- `wall_clock_seconds`
- `ticktask_csv`

Also record:

- `repeat`
- `warmup`
- build identifiers
- executable hash
- save hash
- start/end date
- game speed
- DLC/mod state
- graphics/UI/camera state
- host CPU
- notes

`variant` should be `vanilla` for the baseline. Future patches receive distinct names such as `patch-cache-v1`.

## 8. Script profiler pass

After the TaskThreadCount matrix, use the same save/interval for a separate script-profiling run.

Relevant 1.14.5 interfaces discovered in the executable:

- `Script.Profiling.Gui`
- `Script.Profiling.Start`
- `Script.Profiling.Stop`
- `Script.Profiling.Restart`
- `ScriptProfiling.Enable`
- `ScriptProfiling.Dump`

Do not run script profiling during the primary throughput matrix unless its overhead has been measured. Treat it as a diagnostic pass.

Store the resulting report with the corresponding run metadata.

## 9. GUI data profiler pass

Relevant interfaces:

- `Tools.GuiDataProfiler`
- `GuiDataProfiler`

Use this only after the primary simulation baseline. Compare at least:

- fixed map view with no large panel open
- the exact UI state used by the benchmark

This is intended to detect meaningful GUI/data-binding work or GameState synchronization cost, not to optimize visual fidelity.

## 10. Analysis

Run:

```text
python tools/analyze_benchmarks.py benchmarks/runs \
  --json benchmarks/report.json \
  --markdown benchmarks/report.md
```

The report ranks:

- TickTasks by cumulative milliseconds
- TickTasks by longest observed lock
- run-to-run coefficient of variation
- TaskThreadCount scaling
- variant-to-vanilla changes when later patches are tested

Default noise flag: coefficient of variation > 3%.

A 3% threshold is a screening rule, not statistical proof. If an optimization is close to noise, collect more runs.

## 11. Phase 1 evidence gates

Do not choose a native patch until all of the following are known:

- the top TickTasks by cumulative cost
- the top TickTasks by lock time
- wall-clock scaling from 1 to 16 task threads
- whether the benchmark is stable enough to compare changes
- whether Script Profiler or GUI Data Profiler identifies a material non-native bottleneck

Examples of evidence patterns:

| Observation | Working hypothesis | Next evidence |
| --- | --- | --- |
| Wall-clock improves to 8 threads then plateaus; one TickTask dominates | serial or dependency-bound hotspot | OS-level sampling + binary map |
| High `longest_lock` on top tasks | lock contention | WPR/WPA waits + stacks |
| Many tiny tasks, low lock, weak scaling | dispatch/granularity overhead | scheduler/job profiling |
| Script profiler dominates | script-bound | optimize script first, not native scheduler |
| Large GUI delta between UI states | GUI/GameState synchronization | GUI profiler + frame/thread trace |

These are hypotheses, not conclusions.

## 12. Completion state

Phase 1 tooling can be implemented without running the game, but Issue #1 must remain open until real benchmark data from the target machine has been collected and analyzed.
