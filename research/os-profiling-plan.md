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

## Offline import workflow (implemented 2026-10-05)

1. Export the desired CPU sample / wait / context-switch table as CSV from WPA
   or AMD uProf. Keep the raw trace outside Git and retain the run manifest.
2. Inspect the real header, quoting/delimiter, units, module bases and thread
   identities. Create a mapping using the template in
   `os-profile-normalized-schema.md`, replacing every placeholder.
   The template is **not a verified vendor schema**. Make a separate import for
   each event type. Do not derive a module base from unrelated stack addresses.
3. Supply the run manifest's executable hash and run ID. Normalize with
   `python tools/normalize_os_profile.py EXPORT.csv --mapping mapping.json --run-id RUN --source WPA --output local-data/os-profile.json`.
4. Reproduce the exact-build catalog:
   `python tools/build_native_target_catalog.py --rtti research/generated/pc-evidence-2026-10-05/native/ticktask-rtti.json --overrides research/native-target-overrides-1.14.5.json --executable-sha256 9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54 --output local-data/native-catalog.json`.
5. Correlate:
   `python tools/correlate_os_profile.py local-data/os-profile.json --catalog local-data/native-catalog.json --expected-run-id RUN --output local-data/os-correlation.json --markdown local-data/os-correlation.md`.
6. Inspect unmatched/invalid/ambiguous rows and metric coverage before comparing
   with TickTask rankings. Correct a mapping only against the real export.
   Range hits alone do not classify a bottleneck or establish wait causality.

The committed catalog has 230 targets (224 resolved TickTask tail groups and
6 documented scheduler/callback candidates); 34 classes remain unresolved.
Non-TickTask overrides cite the existing dispatch-region artifact. No speculative
ranges, ETL parser or uProf database parser have been added. Numeric units cannot
be inferred safely from a column name alone.
