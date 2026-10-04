# Scheduler / range-parallel heuristic static analysis — Victoria 3 1.14.5

Date: 2026-10-05

Target executable SHA-256:

`9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Scope

This is an offline static-analysis result. It does not claim that the scheduler is currently the performance bottleneck. Runtime TaskThreadCount scaling and OS-level traces remain the evidence gate for any scheduler modification.

## Strong code anchors

The executable retains the string:

`MaybeRunRangeExecutionParallelWithHeuristic`

at RVA `0x44d94a0`.

Two validated references to that string are inside one native function:

`0x7db150–0x7dba91`

A direct x64 `call rel32` scan finds one validated caller of this function:

- call site RVA: `0x7dbde0`
- caller runtime-function range: `0x7dbaa0–0x7dc13e`

The caller itself references the string:

`RunRangeExecutionParallel`

at RVA `0x44d9728`.

This makes the static relationship considerably stronger than a name-only inference:

```text
RunRangeExecutionParallel-like caller
        |
        +-- call 0x7db150
              |
              +-- MaybeRunRangeExecutionParallelWithHeuristic
```

## Source-level anchors retained in the binary

The same nearby read-only-data region contains:

- `MaybeRunRangeExecutionParallelWithHeuristic`
- ` Expensive`
- ` Affordable`
- ` Parallel`
- `Heuristic must have values for entire range.`
- `gamestatetick.cpp:1252`
- `gamestatetick.cpp:1158`
- `gamestatetick.cpp:1159`
- `RunRangeExecutionParallel`
- `Prepare`

This strongly links the heuristic and its caller to `source/logic/gamestatetick.cpp`.

The line numbers are build-specific diagnostics left by the compiler/source assertions and should not be treated as stable APIs.

## Early rejection tests in the heuristic

Static disassembly of `0x7db150` shows several early exits to a common false/serial path near `0x7db94b`.

Observed checks include:

1. a byte flag at an object-relative offset around `+0xb0`,
2. range size computed as:
   `end - begin`,
3. comparison of that range size against approximately twice a task-system/global count,
4. verification that historical/heuristic values cover the requested range,
5. rejection when the historical range has no useful spread.

The embedded assertion text:

`Heuristic must have values for entire range.`

is referenced from the same function.

The exact field names are unknown and should not be invented from offsets alone.

## Statistical decision logic

The function walks a 32-bit value array for the requested range and visibly computes:

- minimum,
- maximum,
- arithmetic mean,
- variance,
- square root of variance,
- approximately `mean + 2 * standard_deviation`.

The critical sequence includes scalar floating-point:

- integer-to-float conversion,
- division by sample count,
- squared deviation accumulation,
- variance division,
- `vsqrtss`,
- doubling of the standard deviation,
- addition to the mean,
- conversion back to integer.

The resulting threshold is compared against the observed maximum. If the threshold is not below the maximum, the function exits through the non-parallel path.

This is direct evidence that the decision is not just:

`range size > constant => parallel`

Instead, it uses historical per-range measurements and variability to decide whether the parallel path is worthwhile.

## Heuristic state and classification strings

Later parts of the same function reference:

- `MaybeRunRangeExecutionParallelWithHeuristic`
- ` Expensive`
- ` Affordable`

The caller references:

- ` Parallel`

The exact user-visible/logging semantics of those labels are not yet proven, but they are consistent with a runtime classification of work according to observed cost.

## Task-thread-aware work splitting

The caller `0x7dbaa0–0x7dc13e` derives work quantities from task-system state before calling the heuristic.

Static behavior includes:

- reading a current start/end range,
- deriving a range length,
- reading a count from a global/task-system object,
- integer division to determine work size/count,
- handling several mode/state values,
- preparing callable/work objects,
- invoking `0x7db150`,
- taking a different path when the heuristic returns true.

After the heuristic call, the false path continues to calculate chunking/work information and references `RunRangeExecutionParallel`.

The exact object types and field names remain unresolved.

## Why this matters for the project

The original user-visible symptom is:

> total CPU utilization can be low while simulation speed is poor.

This static analysis means a future weak-scaling result has at least three distinct scheduler-level hypotheses:

1. **intentional serial rejection** — the heuristic decides the range is not worth parallelizing,
2. **granularity selection** — parallelization occurs but the chosen work/chunk count is suboptimal,
3. **dependency/lock bottleneck elsewhere** — the heuristic is behaving correctly and another dependency chain dominates.

Only runtime evidence can distinguish them.

Therefore the project must not equate:

`low CPU usage`

with:

`TaskThreadCount is too low`.

## Exact-build validators

`research/generated/exact-signatures-1.14.5.json` contains a unique exact-build byte window for the function beginning at `0x7db150`.

The signature is valid only after the exact executable SHA-256 matches. It is not a cross-version signature.

`tools/validate_exact_signatures.py` enforces this fail-closed model.

## Next static step after real benchmark data

If scaling data later implicates the scheduler:

1. identify the top runtime TickTasks,
2. map them through the RTTI/vtable map,
3. inspect whether their task-specific code reaches the range-parallel path,
4. map the relevant data flow into `RunRangeExecutionParallel`,
5. correlate WPR/uProf worker-idle periods with the heuristic decision,
6. instrument the decision read-only before changing it.

A future experimental patch should first log:

- range length,
- task/thread count input,
- heuristic result,
- calculated chunk/work count,
- historical minimum/maximum/mean/dispersion inputs,

rather than blindly forcing the return value.
