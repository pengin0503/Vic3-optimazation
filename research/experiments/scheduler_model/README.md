# Synthetic DAG scheduler comparison — offline only

This directory contains a **deliberately simplified, independent integer workload model**, not Victoria 3 source code, reimplemented game jobs, or a measured engine scheduler. It has **no connection to** the game, profiler DLL, saves, GPU or native process. Work units are **not milliseconds**. CPU utilization and speedup values do not refer to Victoria 3.

## Run

From the repository root, Python 3.11+ standard library only:

```sh
python -m unittest discover -s research/experiments/scheduler_model -p 'test_*.py' -v
python research/experiments/scheduler_model/compare_schedulers.py research/experiments/scheduler_model/example-workload.json --output local-data/synthetic-scheduler-comparison.json
```

The JSON input contains `format_version:1`, nonempty `tasks`, distinct positive `worker_counts`, and nonnegative integer `dispatch_cost_units`. To bound memory and work, this implementation accepts at most 4,096 tasks, at most 256 workers per configuration, and each task/dispatch work value at most 1,000,000,000 units. Each task has a distinct nonempty `id`, a positive integer `work_units`, and a list of distinct `depends_on` IDs (no missing IDs/cycles). Wrong/malformed input exits 2 and does not replace existing output. Output preserves the raw source-byte SHA-256 for reproducibility.

## Policies and assumptions

- **ready**: non-preemptive event simulation; as soon as prerequisite tasks complete, dispatch the next ready task to the lowest-index available worker. If several tasks are ready, prefer input order. Dispatch cost occupies that worker for each task.
- **layer-barrier**: intentionally hypothetical global barrier after every longest-predecessor-depth layer. Do not assume Victoria 3 runs this policy.
- No shared-state contention, cache effects, memory bandwidth limit, scheduler wakeups, task migration, cost of graph construction, OS preemption, UI rendering, or dynamically changing task graph is simulated.
- `idealized_lower_bound_units = max(ceil(total useful work/workers), longest useful-work dependency path)`, excluding per-task dispatch overhead. It is an idealized mathematical bound for this model, not an estimate of real execution time.
- `useful_utilization = total useful work / (workers × synthetic makespan)` and `worker_idle_units = workers × makespan - useful_work - dispatch_overhead`. Busy overhead is not counted as useful work.
- All output objects contain `synthetic_only: true`; the script does not infer a `candidate_dependency_edges` graph from the real game.

## Example result (synthetic)

The example has one 8-unit independent job and a chain of 2→3→1 work units. Dispatch cost is 1 unit per task.

| Workers | Ideal lower bound (work-only) | ready makespan | layer-barrier makespan |
| ---: | ---: | ---: | ---: |
| 1 | 14 | 18 | 18 |
| 2 | 8 | 9 | 15 |
| 4 | 8 | 9 | 15 |
| 8 | 8 | 9 | 15 |
| 12 | 8 | 9 | 15 |
| 16 | 8 | 9 | 15 |

This input demonstrates a possible parallelism plateau. It **does not** establish that Victoria 3 has the same DAG, dispatch cost, global barriers, or any particular CPU utilization. Real application decisions still require synchronized Running/Ready/Waiting OS traces, exact-game task evidence, native profiler overhead validation, state determinism and repeatable wall times.

See [parent spec](../../../docs/superpowers/specs/2026-10-11-offline-cpu-research-design.md) and [plan](../../../docs/superpowers/plans/2026-10-11-synthetic-scheduler-comparison.md).
