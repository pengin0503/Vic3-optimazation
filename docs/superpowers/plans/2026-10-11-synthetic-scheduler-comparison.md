# Synthetic Scheduler Comparison — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with test-driven-development and verification-before-completion. Steps use checkbox (`- [ ]`) syntax. No subagents.

**Goal:** Construct a reproducible synthetic DAG scheduler comparison that exposes dependency/barrier/dispatch overhead tradeoffs without altering or impersonating Victoria 3 engine code.

**Architecture:** A standard-library Python module models abstract integer work units. It compares an event-driven ready-task scheduler with a hypothetical per-depth-layer global barrier scheduler. The inputs are fully user-owned synthetic workloads; no task timings, engine state or workload semantics are inferred from the real game.

**Tech Stack:** Python 3.11+, `unittest`, `json`/CLI.

**Spec:** `docs/superpowers/specs/2026-10-11-offline-cpu-research-design.md`

## Global Constraints

- Satisfies Workstream 2 only; synthetic timings are **not** milliseconds or Victoria 3 estimates.
- No real game file/process/loader/DLL/scheduler changes.
- Preserve deterministic ordering and input provenance.
- Fail closed on missing dependencies, cycles, duplicate task IDs, negative/invalid work, zero workers and unsupported format.
- Avoid Github Actions during development; run local synthetic tests. Record inability to run full repository suite.
- Do not present worker utilization as a real-game CPU utilization prediction.

## Review Focus

- Shared dependency completed exactly at same timestamp should make children immediately runnable.
- Global layer barrier must not start deeper work before all tasks in the previous layer finish.
- One worker must produce same makespan for both policies when tasks are topologically ordered, not necessarily for arbitrary task ordering.
- Dispatch overhead accumulates once per scheduled task; useful work excludes dispatch overhead.
- A cycle, missing parent, duplicate IDs and non-integer work must not produce a plausible result.

---

### Task 1: Validate DAG and build deterministic static bounds

**Files:**
- Create: `research/experiments/scheduler_model/compare_schedulers.py`
- Create: `research/experiments/scheduler_model/test_compare_schedulers.py`

**Interfaces:**
- `validate_workload(doc: dict) -> tuple[list[dict], list[int], int]` where each task has `id`, `work_units`, `depends_on`. Returns tasks, worker counts, dispatch cost.
- `critical_path_work_units(tasks: list[dict]) -> int` as idealized work-only DAG lower bound.

- [ ] Write tests for chain, fork/join, duplicate ID, missing dep, cycle, negative/noninteger work, unsupported version.
- [ ] Run RED: `python -m unittest discover -s research/experiments/scheduler_model -p 'test_*.py' -v`; expected missing module/API.
- [ ] Implement only validation, topological order and critical path.
- [ ] Run GREEN focused suite, no errors.
- [ ] Commit source and tests.

### Task 2: Compare ready-queue vs hypothetical layer-barrier scheduling

**Files:**
- Modify: `research/experiments/scheduler_model/compare_schedulers.py`
- Modify: `research/experiments/scheduler_model/test_compare_schedulers.py`

**Interfaces:**
- `simulate(tasks: list[dict], workers: int, dispatch_cost: int, *, policy: str) -> dict` (`policy` is `ready` or `layer-barrier`).
- Output fields: `makespan_units`, `useful_work_units`, `dispatch_overhead_units`, `worker_busy_units`, `worker_idle_units`, `useful_utilization`. All are synthetic.

- [ ] Write tests for one worker, two independent tasks, chain, unbalanced layers, dispatch cost, deterministic results.
- [ ] Run RED to confirm missing interface.
- [ ] Implement event-driven dispatch with ready-queue and level barriers. Event timestamps and worker tie-breaks are deterministic. No preemption or context-switch model.
- [ ] Run GREEN focused suite; run all locally available tests.
- [ ] Commit source and tests.

### Task 3: Reproducible CLI and documented limitations

**Files:**
- Modify: `research/experiments/scheduler_model/compare_schedulers.py`
- Create: `research/experiments/scheduler_model/example-workload.json`
- Create: `research/experiments/scheduler_model/README.md`
- Modify: `research/experiments/scheduler_model/test_compare_schedulers.py`

**Interfaces:**
- `build_comparison(doc: dict) -> dict` evaluates each requested worker count under both policies and records theoretical static lower bound.
- CLI: `python research/experiments/scheduler_model/compare_schedulers.py INPUT.json --output OUTPUT.json`.

- [ ] Test CLI: byte-identical outputs for the same input; malformed source/identical output path fail-closed; provenance SHA-256.
- [ ] Run RED focused tests.
- [ ] Implement stable JSON output and atomic write; add an explicit `synthetic_only` flag and warning.
- [ ] Run GREEN focused tests, compare runs, document units, example, non-conclusions, and exact command.
- [ ] Commit all artifacts.

No task in this plan licenses live scheduler patches or estimates real-game speedups.
