# Victoria 3 1.14.5 binary map — static anchors

Build:

- executable SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`
- image base: `0x140000000`
- PE sections: `.text`, `.rdata`, `.data`, `.pdata`, `.rsrc`, `.reloc`

This file contains **string/data anchors only**. These RVAs are not function addresses and must never be treated as stable APIs or patch targets. They exist to speed up Ghidra/IDA xref work for this exact executable hash.

## Clausewitz task infrastructure anchors

| String | Section | RVA | Image VA |
| --- | --- | ---: | ---: |
| `pdx_task.cpp` | .rdata | `0x4908d0b` | `0x144908d0b` |
| `pdx_graphjob.cpp` | .rdata | `0x4908d5b` | `0x144908d5b` |
| `pdx_task_scheduler.cpp` | .rdata | `0x4908dfb` | `0x144908dfb` |
| `pdx_workset.h` | .rdata | `0x45c4ecb` | `0x1445c4ecb` |
| `Threading.TaskThreadCount` | .rdata | `0x4908ab0`, `0x4908b2c` | build-specific |
| `MaybeRunRangeExecutionParallelWithHeuristic` | .rdata | `0x44d94a0` | `0x1444d94a0` |

The same parallel/job type names also appear extensively in `.data` RTTI/template strings:

- `CPdxParallelForDescriptor`
- `SPdxParallelFor`
- `CNonBlockingJob`
- `MaybeRunRangeExecutionParallelWithHeuristic`

High occurrence counts in RTTI/template data are expected and should be used to locate type families, not as patch targets.

## Game-state tick anchors

`gamestatetick.cpp` occurs six times in `.rdata`, including:

- `0x44d91c2`
- `0x44d939a`
- `0x44d95ba`
- `0x44d961a`
- `0x44d96ba`
- `0x44d970a`

These are useful xref starting points for the game-state tick orchestration path.

## Economy / population anchors

| Source string | Section | Representative RVA(s) |
| --- | --- | --- |
| `employment_helper.cpp` | .rdata | `0x45673ea`, `0x456754a` |
| `employment_utils.cpp` | .rdata | `0x4579d0a` |
| `pop.cpp` | .rdata | `0x458cc82` |
| `popmanager.cpp` | .rdata | `0x458f23a`, `0x458f4aa` |
| `market.cpp` | .rdata | `0x454594a`, `0x45959a8` |
| `world_market.cpp` | .rdata | `0x45959a2` |
| `modifier.cpp` | .rdata | `0x453a512`, `0x4826d13` |

## Built-in profiler anchors

| String | Section | RVA |
| --- | --- | ---: |
| `clear_ticktask_timings` | .rdata | `0x4575570` |
| `dump_ticktask_timings` | .rdata | `0x45757a8` |
| `Threading.TaskThreadCount` | .rdata | `0x4908ab0`, `0x4908b2c` |

These anchors are especially valuable because their code xrefs should lead toward the internal TickTask timing registry, console-command registration, and task-thread configuration code.

## Next reverse-engineering pass

Do not perform broad blind decompilation. Once the runtime benchmark identifies the top one to three TickTasks:

1. search the corresponding `CTickTask_*` RTTI/name strings
2. identify vtables/type descriptors where possible
3. follow data/code xrefs to task registration and execute paths
4. correlate with relevant source-path assertions/log strings
5. identify the graph/dependency parent and parallel-for children
6. validate with unwind metadata and call graph
7. record confidence level and evidence for each function mapping

Until real TickTask timings exist, scheduler and economy anchors remain research entry points rather than optimization candidates.
