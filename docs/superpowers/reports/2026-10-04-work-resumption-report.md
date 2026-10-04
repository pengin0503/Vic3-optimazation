# Work resumption report

Date: 2026-10-04
Repository: pengin0503/Vic3-optimazation
Branch: main

## Request

Resume the interrupted work from the current repository state, continue the approved measurement-first plan, and preserve a detailed record of the work in the repository.

## Starting state

The repository had already progressed beyond the initial design phase.

Existing completed repository-side work included:

- approved native-performance design
- implementation plan
- preliminary 1.14.5 static analysis
- reproducible static analyzer
- TickTask benchmark analyzer
- unit tests and GitHub Actions workflow
- generated TickTask/profiler/import inventories
- Windows and AMD OS-level profiling plan
- initial binary map
- initial TickTask family map
- hook-feasibility study selecting an attach-loader plus injected DLL architecture for future read-only instrumentation
- refined evidence that dump_ticktask_timings writes ticktask_timings.csv and log_ticktask_performance writes profiling.log

The latest completed GitHub Actions run before this resumption was successful for commit 09c7a54db5747178a7ae8ea18f5c318a2fe239c5.

## Work performed after resumption

### 1. Re-read the repository instead of restarting

The current main tree and recent commit history were inspected first.

This avoided re-implementing work that had already been completed during the prior run.

The plan remains measurement-first. Native patching is still blocked intentionally until runtime benchmark evidence exists.

### 2. Re-examined the supplied Vic3_data.zip

The attached archive was inspected again from the chat environment.

Relevant confirmed contents include:

- victoria3.exe
- game/common
- game/gui
- game/tools/scripted_tests
- clausewitz/gui/profiler.gui
- jomini GUI/tooling data
- build revision files

Additional useful runtime infrastructure was found and documented separately in research/runtime-automation-findings.md.

### 3. Confirmed the retail scripted-test framework

The shipped game data contains game/tools/scripted_tests/scripted_tests.md and example test suites.

The framework supports date-based pass/fail triggers and test-suite last dates. It can be enabled by command-line options or by the in-game scripted_tests console command.

Executable strings also expose the Jomini test manager and output names tests.txt and {}_testoutput.xml.

Conclusion: this may later automate benchmark end-date handling, but it is not used for the first baseline because its runtime overhead and behavior on an already-loaded heavy save are not yet measured.

### 4. Identified a Jomini game-timer lead

The executable contains:

- Game Date
- Time Unit
- Seconds
- gametimer_%04d%02d%02d_%02d%02d%02d
- .tsv

This suggests a built-in timer output path that may already map simulation date to elapsed seconds.

The activation path has not yet been mapped with sufficient confidence. It is recorded as a future lead, not treated as a verified benchmark interface.

### 5. Refined profiler interpretation

The GUI Data Profiler includes embedded semantic help:

- Only Script measures GUI script resolution
- Self measures other widget/property work

The Clausewitz profiler UI exposes frame time, ns/tick, thread selection/filtering, recording controls, and CSV export.

This improves the later decision tree for separating script cost, widget/property volume, render/GUI synchronization, and simulation cost.

### 6. Added benchmark matrix preparation tooling

Added tools/prepare_benchmark_matrix.py.

Purpose:

- generate all Phase 1 run directories before measurement
- default to TaskThreadCount 1, 2, 4, 6, 8, 12, 16
- default to one warm-up plus three measured runs per thread count
- create 28 run templates in the default configuration
- embed the known 1.14.5 build identifiers
- create manifest.template.json instead of manifest.json so incomplete runs are not discovered by the analyzer
- refuse to operate on a non-empty output directory to protect measured data

This removes repetitive manual manifest setup and reduces the chance of mixing thread-count or repeat metadata.

### 7. Added benchmark finalization tooling

Added tools/finalize_benchmark_run.py.

Purpose:

- accept the measured wall-clock duration after a game run
- verify that ticktask_timings.csv exists
- verify the required columns:
  - frame
  - task
  - milliseconds
  - calls
  - longest_lock
- reject an empty CSV
- record CSV SHA-256
- record CSV byte size
- record CSV row count
- write the final manifest.json
- refuse to overwrite an existing final manifest

This establishes a clean boundary between planned runs and completed measured runs.

### 8. Added tests for the new benchmark workflow

Added tests/test_benchmark_workflow.py.

Local verification in the chat execution environment covered:

- default 28-run matrix shape
- correct thread-count metadata
- protection against non-empty output directories
- successful run finalization
- SHA-256/row-count capture
- rejection of malformed TickTask CSV input

Result:

4 tests executed, all passed.

The repository GitHub Actions workflow automatically runs all Python unit tests on push; final remote CI status is verified below after the commits settle.

## New commits created in this resumption

- f9a6f8dd9145eef210d8d1676c7f5e31c9398362 — feat: add benchmark matrix preparation tool
- 831637d49da3be05df3ee28ffff6f15731f1740d — feat: add benchmark run finalization tool
- c0ff6d1a8fcfdfa2a0c1498971541e96c5170079 — test: cover benchmark preparation workflow

Additional documentation commits follow this report.

## Current plan status

### Task 1 — Repository and data boundary

Repository-side portion: complete.

The reduced input-data policy and build metadata are documented. The actual selected ZIP archives are still not present in GitHub because the connector cannot transfer conversation-uploaded binary bytes.

### Task 2 — Preserve preliminary static analysis

Complete.

### Task 3 — Static-analysis extraction scripts

Complete for the current scope.

The analyzer can regenerate PE metadata, imports/exports, PDB path, source paths, TickTask inventory, task/job strings, and profiler/console command inventory from a local archive.

### Task 4 — Benchmark protocol

Repository-side preparation is complete and now more executable due to the matrix/finalization tools.

Runtime completion is blocked on a real heavy-save run on Windows.

### Task 5 — Benchmark/result parser

Complete for the planned Phase 1 schema.

Runtime validation with real TickTask CSV remains pending.

### Task 6 — OS-level profiling protocol

Documentation complete.

Real WPR/WPA or AMD uProf evidence remains pending.

### Task 7 — Binary architecture map

Initial static anchor map complete.

Mapping the highest-cost runtime tasks to native functions remains intentionally blocked until the benchmark identifies those tasks.

### Task 8 — Hook feasibility study

Architecture decision complete.

Preferred research architecture: explicit attach loader plus injected read-only profiler DLL, with two-stage fail-closed build/signature validation.

### Task 9 — Read-only native instrumentation

Not started by design.

The implementation plan requires real Phase 1 benchmark data, correlated OS-level profiling, and mapped target functions first.

### Tasks 10–12

Not started. These are evidence-gated optimization/experimental phases.

## Current hard blocker

The next high-value evidence cannot be produced in the chat/container environment.

It requires the Windows Victoria 3 process and a heavy save.

Specifically required next:

1. select a heavy late-game save
2. create the benchmark matrix with prepare_benchmark_matrix.py
3. run the fixed-date speed-5 interval
4. collect ticktask_timings.csv
5. finalize each measured run with finalize_benchmark_run.py
6. analyze the matrix with analyze_benchmarks.py
7. capture one matching WPR/WPA or AMD uProf trace
8. only then choose native reverse-engineering targets

This is an evidence gate, not an implementation failure.

## What should not be done yet

Do not:

- implement speculative Employment hooks
- force more worker threads as an assumed optimization
- rewrite scheduler behavior before scaling data exists
- use culture/Pop reduction as the primary optimization path
- start a native DLL merely because the binary is reverse-engineerable

Doing so would violate the approved design and make regressions difficult to attribute.

## Verification status

Before resumption, the latest repository Actions run for commit 09c7a54db5747178a7ae8ea18f5c318a2fe239c5 completed successfully.

The newly added workflow tools were also tested locally before commit. Their remote GitHub Actions status must be checked after the last documentation commit and recorded in the issue/report if a failure appears.

## Recommended immediate next action

Move to the Windows PC and collect the first real benchmark matrix.

The minimum useful first pass can be reduced to TaskThreadCount 1, 4, 8, 16 with one warm-up plus three measured runs each if time is limited. If the scaling curve is clear, then complete 2, 6, and 12.

The full planned matrix remains 1, 2, 4, 6, 8, 12, 16.
