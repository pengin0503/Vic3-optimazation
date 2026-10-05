# Native profiler hook ABI evidence — Victoria 3 1.14.5

Date: 2026-10-05

Target executable SHA-256: 9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54

## Purpose

Pin the minimum calling-convention evidence needed for the first read-only TickTask detours. This document does not name an unproven source-level method and does not authorize any simulation-changing patch.

## Common dispatch witness

The exact-build dispatcher candidate at RVA 0x7dc160 contains this sequence:

- 0x7dc233: load the task object's vtable into RAX from [R14]
- 0x7dc236: form a pointer to the execution-context object in RDX
- 0x7dc23b: copy the task object into RCX
- 0x7dc23e: indirect call through [RAX + 0x30]
- 0x7dc241 onward: continue without consuming RAX as a return value

On Windows x64, RCX and RDX are the first two integer/pointer arguments. The call therefore supports the conservative prototype:

    void TickTaskTail(void* task_object, void* execution_context)

The caller does not use a return value. This is the ABI used by the first instrumentation-only detours.

## Why slot 6 is the relevant slot

The selected RTTI/vtable evidence for all three initial targets has seven slots, with the unique class-specific tail virtual at index 6 (byte offset 0x30):

| Runtime task | Vtable RVA | Slot 6 target | Resolved function range |
| --- | ---: | ---: | --- |
| HandleAutonomousInvestment | 0x4558d98 | 0xf6e590 | 0xf6e590–0xf6e7a3 |
| ProcessEconomicMigration | 0x4576b98 | 0x11b0c00 | 0x11b0c00–0x11b0dde |
| UpdateEmployment | 0x4590800 | 0x13b8310 | 0x13b8310–0x13b853b |

Each target prologue also consumes RCX and RDX consistently with the dispatcher witness. The migration range is a chained three-fragment unwind group but is contiguous as 0x11b0c00–0x11b0dde.

## Hooking constraints

- Resolve a target from an exact executable hash plus a unique .text signature; do not use the RVA as the primary locator.
- Cross-check the resolved address against the selected vtable slot before arming the hook.
- Use the two-pointer, void-return prototype only for these three exact-build tail anchors.
- Record FunctionBegin immediately before calling the original trampoline and FunctionEnd immediately after it returns.
- Do not catch, transform, suppress, or synthesize game exceptions. If the original does not return normally, the trace may contain a broken pair; the offline parser must report it.
- Do not interpret a tail-anchor duration as the total cost of the corresponding TickTask. Existing callback/job evidence shows that work can continue below the tail anchor.

## Evidence boundary

This is sufficient to start Task 9 read-only instrumentation. It does not establish lock causality, critical path, cache/allocation bottlenecks, observer overhead, or optimization benefit.
