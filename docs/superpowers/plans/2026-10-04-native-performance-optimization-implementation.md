# Victoria 3 Native Performance Optimization — Implementation Plan

Date: 2026-10-04
Source of truth: latest `main` plus the approved design in `docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md`.

## Scope

Build a measurement-first Victoria 3 1.14.5 performance research platform, then use evidence to decide whether a native extender is justified. Do not begin with gameplay-reducing optimizations and do not implement unsafe simulation parallelization in the initial phases.

## Task 1 — Repository and data boundary

Create/maintain:

- `README.md`
- `research/`
- `tools/`
- `benchmarks/` for small metadata/results only
- `src/` for future original native code
- `.gitignore`

Rules:

- do not commit Paradox executables, DLLs, PDBs, saves, or the original combined `Vic3_data.zip`
- this repository is private and may contain only the deliberately reduced research-input archives documented in `research/input-data-manifest.md` under `input-data/`
- keep large/unrelated proprietary assets outside the repository
- commit hashes, checksums, signatures, file inventories, and derived analysis freely

Acceptance:

- repository documents the target build
- accidental binary commits are blocked
- data provenance is reproducible by hashes

## Task 2 — Preserve preliminary static analysis

Store the current 1.14.5 findings in `research/preliminary-static-analysis.md`.

Acceptance:

- build/revision hashes recorded
- `victoria3.exe` hash recorded
- discovered TickTask/profiler/threading interfaces recorded
- findings distinguish confirmed evidence from inference

## Task 3 — Build static-analysis extraction scripts

Implement reusable scripts that operate on a local Victoria 3 install/archive and emit text/JSON only.

Minimum outputs:

- PE metadata and section table
- import/export summary
- embedded PDB path
- source `.cpp/.h` path inventory
- `CTickTask_*` inventory
- RTTI/template-name inventory
- profiler/console command inventory
- SHA-256 manifest

Preferred implementation: Python, with optional external-tool integration when installed.

Tests:

- scripts fail cleanly when input path is missing
- deterministic output ordering
- known 1.14.5 fixture metadata matches recorded hashes

Acceptance:

- a fresh local copy of 1.14.5 can regenerate the committed inventories without storing the binary

## Task 4 — Define the benchmark protocol

Create `research/profiling-plan.md` and a machine-readable benchmark manifest format.

Protocol:

1. choose a heavy late-game save
2. fix game version, DLC/mod state, camera/UI state, speed, and start date
3. perform one warm-up run
4. `clear_ticktask_timings`
5. run a fixed in-game interval
6. `dump_ticktask_timings`
7. record wall-clock duration
8. repeat at least three measured runs
9. repeat for `Threading.TaskThreadCount` = 1, 2, 4, 6, 8, 12, 16
10. separately capture Script Profiler and GUI Data Profiler where relevant

Acceptance:

- another run can reproduce the procedure exactly
- all run metadata needed for comparison is recorded
- no optimization claim is accepted without baseline variance

## Task 5 — Benchmark/result parser

Create a tool that ingests `ticktask_timings.csv` and benchmark metadata and reports:

- total time by task
- mean/max time
- calls
- longest lock
- ranking by cumulative cost
- ranking by lock cost
- scaling by TaskThreadCount
- run-to-run variance

Do not infer causality solely from one metric.

Acceptance:

- produces Markdown/CSV or JSON summaries
- can compare two benchmark sets
- highlights regressions and statistically noisy results separately

## Task 6 — OS-level profiling protocol

Document and, where practical, script capture using:

- Windows Performance Recorder / Windows Performance Analyzer
- AMD uProf as an optional Ryzen-focused path

Capture targets:

- per-thread CPU utilization
- context switches
- waits
- synchronization
- CPU sampling stacks where symbols allow
- memory/cache indicators where available

Acceptance:

- profiler capture can be correlated with the same benchmark interval
- OS-level evidence is used to distinguish compute from waiting

## Task 7 — Binary architecture map

Using Ghidra/IDA/Binary Ninja/rizin as available, produce:

- `research/binary-map.md`
- `research/ticktask-map.md`

Focus on:

- task scheduler
- graph job/dependency system
- parallel-for descriptor/heuristics
- game-state tick dispatch
- Employment
- Pop need cache/purchases
- modifier recalculation
- market/world market
- AI
- GUI/GameState synchronization

Method:

- strings are entry points only
- validate with xrefs, RTTI/vtables, unwind/exception metadata, imports, and call graphs where possible
- mark uncertain mappings explicitly

Acceptance:

- top measured hotspots map to concrete candidate functions or function families
- no addresses are treated as stable API

## Task 8 — Hook feasibility study

Create `research/hook-feasibility.md`.

Compare:

- proxy DLL
- external injector + injected DLL
- loader executable
- other maintainable Windows approaches

Evaluate:

- startup reliability
- update resilience
- debugging
- distribution complexity
- risk of collision with Steam/Paradox/graphics DLLs
- ability to fail closed

Define target resolution:

- executable hash
- signature scan
- surrounding-code validation
- optional RTTI/vtable validation
- unsupported-build rejection

Acceptance:

- select one preferred architecture for read-only instrumentation
- no native game-state-changing patch yet

## Task 9 — Read-only native instrumentation prototype

Only start after Tasks 1–8 and after a real benchmark identifies targets.

Prototype requirements:

- original C++ code only
- version gate
- pattern scanning
- validated hook targets
- timestamp/call-count/thread data
- no game-state modification
- clean unload/disable path where feasible

Acceptance:

- unsupported executable remains unmodified
- overhead is measured
- results can be correlated with built-in TickTask timings

## Task 10 — Candidate optimization decision

Create `research/candidate-hotspots.md`.

For each candidate:

- measured cost
- scaling behavior
- lock/wait evidence
- suspected root cause
- native function mapping confidence
- safest intervention
- determinism/save-risk assessment
- expected maximum benefit

Select no more than 1–3 first patches.

Acceptance:

- every selected patch is evidence-backed
- expected improvement is larger than benchmark noise

## Task 11 — Safe native patch prototype

Implement only the selected low-risk patch(es), individually toggleable.

Requirements:

- build/signature gate
- fail-safe
- before/after benchmark
- crash test
- long-run save test
- no silent gameplay-semantic change

Acceptance:

- reproducible performance improvement
- no observed simulation-state regression in the defined validation set

## Task 12 — Experimental scheduler work

Do not start unless profiling shows scheduler/chunking/lock behavior is a major limitation.

Potential research:

- task chunk size
- worker wake/sleep behavior
- parallel-for heuristics
- work distribution
- dependency/barrier structure

Keep behind experimental flags and off by default.

Acceptance:

- demonstrable gain over safe baseline
- deterministic behavior investigated explicitly
- easy rollback to vanilla behavior

## Execution order

Tasks 1–8 are research/foundation.
Task 9 is the first native code milestone.
Tasks 10–11 are the first optimization milestone.
Task 12 is optional and evidence-gated.

Do not skip directly to Task 11/12.

## Verification-before-completion

Before declaring any phase complete:

- rerun extraction/tests from a clean checkout
- verify hashes/build metadata
- verify benchmark reproducibility
- verify unsupported-build fail-safe where native code exists
- document limitations and unresolved assumptions
- commit generated research outputs only when they are derived data, not proprietary binaries
