# TickTask vtable semantics — conservative static notes

Date: 2026-10-05
Target: Victoria 3 Windows 1.14.5
Executable SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Purpose

The RTTI pass mapped 258 concrete `CTickTask_*` classes to vtables. This note records what can be inferred from shared virtual slots without assigning unproven source-level method names.

The main rule is conservative:

> A vtable position or call shape is a native anchor, not a source symbol.

## Common virtual slots

Across the 258 mapped classes:

- slot 1 is `0x3bf7200` for 258 / 258 classes,
- slot 3 is `0x3bf7270` for 258 / 258,
- slot 5 is `0x62d680` for 258 / 258,
- slot 2 is `0x62d680` for 252 / 258,
- slot 4 is `0x1808250` for 251 / 258,
- slot 6 is `0x7d76b0` for the 69 eight-slot classes,
- the **final** virtual slot is unique for all 258 mapped classes.

This structure strongly suggests a common task interface plus one concrete class-specific operation at the tail, but exact source method names remain unproven.

## Shared slot 1 — `0x3bf7200`

Static disassembly shows a generic wrapper shape. It:

1. receives the TickTask object and an execution/context object,
2. adjusts execution/context bookkeeping,
3. performs an indirect virtual call through an earlier class slot,
4. restores/updates surrounding execution state.

This looks like shared task-interface plumbing rather than task-specific simulation logic.

The exact semantic label is intentionally left unspecified.

## Shared slot 3 — `0x3bf7270`

This is another generic wrapper. Its static shape is similar to slot 1 but it dispatches through a different virtual offset and participates in the common execution-context path.

Again, it is useful for understanding interface structure but is not a useful optimization target by itself without runtime evidence.

## Shared `0x62d680`

`0x62d680` is a minimal return stub.

It occupies:

- slot 5 for all mapped classes,
- slot 2 for 252 of 258 classes.

This is consistent with optional/default no-op interface hooks.

## Shared slot 4 — `0x1808250`

Most classes use `0x1808250` in slot 4. Static inspection shows a thunk/common Jomini/task-system path rather than a large class-specific implementation.

The minority of classes overriding this slot may be interesting if runtime data selects one of them, but no assumption is made from the override alone.

## Shared slot 6 in eight-slot classes — `0x7d76b0`

All 69 mapped eight-slot classes use `0x7d76b0` in slot 6 and place their unique class-specific virtual in slot 7.

Static inspection of `0x7d76b0` shows:

- construction of a small stack callable/helper object,
- entry into shared task/range machinery,
- no evidence that it is itself a concrete simulation subsystem implementation.

This is consistent with the eight-slot family having one additional shared interface stage before the class-specific tail virtual.

## Why the final slot is the preferred static anchor

For every mapped concrete class, the last vtable slot is unique.

That gives a deterministic path:

```text
runtime TickTask name
        ↓
MSVC RTTI TypeDescriptor
        ↓
Complete Object Locator
        ↓
concrete vtable
        ↓
final class-specific virtual
        ↓
small native call-graph region
```

This is substantially better than searching the whole executable by source strings after every benchmark.

The project calls this field:

`task_specific_tail_vfunc`

and does **not** call it `Execute`, `Prepare`, or `Run` unless later dynamic/static evidence proves the source-level semantic.

## UpdateEmployment caution

`CTickTask_UpdateEmployment` maps to:

- vtable RVA: `0x4590800`
- task-specific tail virtual: `0x13b8310`
- runtime-function range: `0x13b8310–0x13b853b`

Its vtable is:

```text
slot 0  0x13c2fe0
slot 1  0x3bf7200
slot 2  0x62d680
slot 3  0x3bf7270
slot 4  0x1808250
slot 5  0x62d680
slot 6  0x13b8310   <- unique class-specific tail virtual
```

Static inspection of `0x13b8310` shows nontrivial class-specific work, including:

- reset/preparation of internal structures,
- resizing/initializing arrays or work buffers,
- iteration using game/task/world counts,
- population of integer/work arrays through helper calls,
- construction of a callable/work object,
- dispatch into common helper/task machinery.

This means `0x13b8310` is a strong Employment task anchor, but it may represent **preparation/range setup** rather than the entire expensive employment calculation.

Therefore a future profiler must not hook only this function and conclude that its inclusive duration equals all employment cost.

If `UpdateEmployment` is a real runtime hotspot, next static/dynamic work should inspect its callees/child jobs and correlate them with the scheduler/range-parallel machinery.

## Destructor-like slot 0

For `CTickTask_UpdateEmployment`, slot 0 at `0x13c2fe0` has cleanup/destructor-like behavior.

This further supports treating the final slot as the relevant class-specific non-destructor anchor while avoiding assumptions about exact C++ names.

## Consequence for read-only instrumentation

If Task 9 is reached, initial instrumentation should prefer:

1. built-in TickTask timings as the authoritative aggregate,
2. the class-specific tail virtual only as a correlation anchor,
3. child/common task/range helpers when inclusive work is dispatched outside the tail function,
4. timestamps/call counts with minimal hook overhead.

The profiler should report both direct-hook duration and built-in TickTask duration so divergence is visible.

## Update resilience

These RVAs are valid only for the exact 1.14.5 executable hash.

When the executable changes:

1. rerun `tools/analyze_vic3.py`,
2. rerun `tools/map_ticktask_rtti.py`,
3. use `tools/compare_static_analysis.py`,
4. regenerate exact-build signatures,
5. keep native hooks disabled until all mappings are revalidated.

No vtable RVA is a stable API.
