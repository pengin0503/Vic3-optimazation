# OS-level profiling plan

Target: Victoria 3 Windows 1.14.5

Purpose: correlate built-in TickTask timings with operating-system evidence for execution, waiting, synchronization, context switching, and CPU/memory behavior. This is diagnostic work; it does not modify the game.

## 1. Correlation rule

Use the same heavy save, start/end dates, camera/UI state, game speed and TaskThreadCount as the Phase 1 benchmark.

For every OS-level capture, record the matching benchmark `run_id`.

Do not compare a WPR/uProf trace captured from one simulation interval against TickTask CSV from a different interval.

## 2. Windows Performance Recorder / Analyzer

Microsoft WPR supports built-in recording profiles and command-line start/stop capture. Start by enumerating the profiles present on the machine:

```powershell
wpr -profiles
```

For the first correlation pass, use the built-in GeneralProfile in file mode:

```powershell
wpr -start GeneralProfile -filemode
```

Then run exactly the fixed benchmark interval. Immediately after pausing at the end date:

```powershell
wpr -stop C:\Temp\vic3-<run-id>.etl
```

Open the ETL in Windows Performance Analyzer.

Primary views:

- CPU Usage (Sampled), grouped by process/thread
- CPU Usage (Precise), where available for scheduling/wait analysis
- thread lifetime / context switches
- wait/synchronization stacks
- process/thread names
- disk/file I/O only if a simulation stall coincides with storage activity

Filter to `victoria3.exe` before drawing conclusions.

### WPR evidence to record

For the benchmark interval:

- hottest Victoria 3 thread(s)
- whether one thread remains saturated while workers go idle
- ready/running/waiting behavior of task threads
- long blocked intervals
- frequent context switches
- wait stacks that repeat during slow ticks
- sampled stacks for the dominant CPU consumers when symbolization is usable

If Microsoft/public symbols resolve only Windows modules, the trace is still useful for thread-state and wait evidence. Native Victoria 3 function naming will come from the separate binary map.

## 3. AMD uProf

Current AMD uProf supports Windows CPU profiling with timer/PMC sampling, IBS, call-stack sampling, and Windows thread-concurrency data. Use the GUI for the first pass so the capture configuration is explicit and version drift in CLI flags does not invalidate the procedure.

Recommended first capture:

- CPU Profile
- scope: system-wide or attach/select the already running Victoria 3 process
- call-stack sampling enabled where practical
- thread concurrency enabled on Windows when running with the required administrator privilege
- capture only the fixed benchmark interval

Run a second, separate microarchitecture-oriented capture only if the first pass suggests the main limitation is execution/memory rather than waiting.

Do not combine every available event set into one capture. In particular, keep IBS investigation separate from timer/PMC experiments when necessary so collection quality can be checked independently.

### uProf evidence to record

- samples by thread
- top instruction/module regions
- thread concurrency over time
- IPC where collected
- branch/cache/memory indicators only when the selected profile supports them
- whether the hot thread is compute-bound while worker threads are underutilized
- whether the workload is memory/cache limited rather than scheduler limited

## 4. Interpretation matrix

| TickTask + OS observation | Working classification | Next step |
| --- | --- | --- |
| one expensive TickTask; one hot thread; workers frequently idle | serial/dependency bound | Phase 3 binary mapping of that task |
| high `longest_lock`; blocked workers; repeating wait stacks | lock contention | map lock owner/call path |
| many short TickTasks; high context-switch/dispatch activity | task granularity/scheduler overhead | map graph-job/parallel-for dispatch |
| worker concurrency is high but IPC/cache behavior is poor | memory/cache bound | data-layout/cache investigation |
| low native CPU but Script Profiler dominates | script bound | optimize script layer first |
| UI state changes simulation throughput materially | GUI/GameState synchronization | GUI/data-binding mapping |

These are hypotheses. Confirm with at least two independent measurements before implementing a native patch.

## 5. Artifacts

Do not commit large raw ETL or uProf databases to Git.

For each capture commit only a small Markdown/JSON summary containing:

- matching benchmark `run_id`
- capture tool/version
- capture configuration
- target TaskThreadCount
- important thread IDs/names
- measured observations
- screenshots only if necessary and license/privacy-safe
- path/hash of the local raw capture if needed for provenance

## 6. Completion criterion for Issue #2

Issue #2 is complete only when at least one real heavy-save benchmark has:

1. TickTask CSV
2. wall-clock result
3. WPR/WPA or AMD uProf capture from the same interval
4. a written classification of the dominant limitation with supporting evidence

The documentation portion is complete now; runtime evidence requires the Windows game machine.
