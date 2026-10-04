# Static code-reference map — Victoria 3 1.14.5

Date: 2026-10-04

Target executable:

- SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`
- image base: `0x140000000`
- `.text` RVA: `0x1000`

This document advances the binary map without requiring a Windows runtime. It uses three independent static facts:

1. exact ASCII string locations in the executable,
2. x64 RIP-relative disp32 references from `.text`,
3. PE `.pdata` runtime-function ranges.

Candidate references were then checked with `llvm-objdump` for the high-value anchors below. All addresses are **build-specific research metadata**, not stable APIs.

## Reproducible method

`tools/map_static_xrefs.py` scans every possible four-byte displacement position in `.text` and tests whether:

```text
target_rva = displacement_end_rva + signed_disp32
```

It maps hits into `.pdata` function ranges.

A raw disp32 hit can occur accidentally, so the tool marks every result as a candidate until the surrounding instruction is validated in a real disassembler. The entries marked **validated** below were checked against `llvm-objdump`.

## TickTask timing commands

| Anchor | String RVA | Referencing function RVA | Function end | Validation |
| --- | ---: | ---: | ---: | --- |
| `dump_ticktask_timings` | `0x45757a8` | `0x118f3a0` | `0x118f687` | validated |
| `ticktask_timings.csv` | `0x4575758` | `0x118f690` | `0x118fc3b` | validated |
| `clear_ticktask_timings` | `0x4575570` | `0x118fc40` | `0x118ff01` | validated |
| `log_ticktask_performance` | `0x44da218` | `0x7e2d50` | `0x7e2ffa` | validated |

The `ticktask_timings.csv` function at `0x118f690` is especially useful: it is distinct from the console-command registration function and is the strongest current static candidate for the actual CSV-writing path.

The dump registration function also constructs a callback pointing to `0x118f690`, which strengthens that mapping.

## Thread controls

### TaskThreadCount

`Threading.TaskThreadCount` occurs at `0x4908ab0` and `0x4908b2c`.

The validated command handler is:

- function: `0x3bcd320–0x3bcd7ea`
- direct references to `0x4908ab0` at code RVAs around `0x3bcd417` and `0x3bcd46f`

There is also a small leaf thunk:

```text
0x5c1e10: jmp 0x3bcd320
```

This is useful because it provides a compact entry point to the larger TaskThreadCount handler.

### EnableTaskThreads

`Threading.EnableTaskThreads` is referenced by a tiny leaf/thunk region beginning at:

```text
0x5c1df0
```

The relevant code loads the command string and jumps into a common registration/dispatch helper.

This region is not represented as a normal `.pdata` function, which is expected for simple leaf/thunk code.

## TickTask debug UI commands

| Command | String RVA | Function RVA | Function end | Validation |
| --- | ---: | ---: | ---: | --- |
| `TickTask.List` | `0x4753a10` | `0x28cf5b0` | `0x28cf81b` | validated |
| `TickTask.Graph` | `0x47539c0` | `0x28cf820` | `0x28cfa8b` | validated |

These are useful future anchors for understanding the internal TickTask registry and dependency graph because they must eventually reach the same objects exposed by `game/gui/ticktask_debugger.gui`.

## Script profiler

| Interface | String RVA | Function RVA | Function end | Validation |
| --- | ---: | ---: | ---: | --- |
| `Script.Profiling.Start` | `0x487f590` | `0x3357500` | `0x3357773` | validated |
| `Script.Profiling.Stop` | `0x487f528` | `0x3357830` | `0x3357a97` | validated |
| `Script.Profiling.Restart` | `0x487f488` | `0x3357be0` | `0x3357e61` | validated |
| `Script.Profiling.Gui` | `0x4817a78` | `0x4d9ac0` | `0x4d9c40` | validated |
| `ScriptProfiling.Dump` | `0x4709420` | `0x276a140` | `0x276a371` | validated |

A second raw disp32 candidate for `Script.Profiling.Start` appeared inside `0x2fca9a0–0x2fcafca`, but the disassembly did not contain a real instruction reference to the target string. It is therefore retained only as an example of why raw displacement candidates must be disassembly-validated.

## GUI / Clausewitz profiler

| Interface | String RVA | Function RVA | Function end | Validation |
| --- | ---: | ---: | ---: | --- |
| `Tools.GuiDataProfiler` | `0x4815730` | `0x4c97a0` | `0x4c992b` | validated |
| `PdxProfilerGuiWriteFrameCSV` | `0x48a48f0` | `0x55f530` | `0x55f6c2` | validated |

These functions are useful if real profiling later implicates GUI/GameState synchronization.

## Parallel-range heuristic

The string `MaybeRunRangeExecutionParallelWithHeuristic` at `0x44d94a0` has two validated references inside:

```text
0x7db150–0x7dba91
```

This function is now the strongest static anchor for the internal range-parallelization heuristic.

### Static behavior visible in disassembly

Without assigning source-level field names prematurely, the function clearly performs the following operations:

1. reads a range start/end pair and computes a range size,
2. compares the range size against a value derived from a global/task-system object,
3. can leave through a false/serial path at `0x7db94b`,
4. reads a vector/array of 32-bit historical values,
5. computes minimum and maximum,
6. computes mean,
7. computes variance and square root,
8. forms a threshold approximately equivalent to `mean + 2 * standard_deviation`,
9. compares that threshold against another observed value,
10. maintains/grows global arrays of 32-bit samples,
11. constructs work objects and derives work counts from task-thread-related state,
12. returns true only after the parallel-work path has been constructed.

This is substantially stronger evidence than the original string-only observation: Victoria 3 is not simply using a fixed worker-count threshold. It contains a runtime heuristic that uses historical/sample statistics before selecting/constructing a parallel range-execution path.

### Consequence

If the real TaskThreadCount benchmark later shows under-parallelization, the first scheduler question should be:

> Is the heuristic declining parallel execution or choosing insufficient granularity for a measured hot range?

It should **not** immediately be:

> Can we force more worker threads?

Any later patch to this function remains experimental and must be driven by runtime evidence.

## Scripted test framework

The string `scripted_tests` at `0x44bd9c0` has validated references in:

- `0x633970–0x633e0d`
- `0x1183240–0x11834dc`

The latter has the same command-registration shape seen in other exposed console commands.

Together with `game/tools/scripted_tests/scripted_tests.md`, this confirms that the retail executable retains the Jomini scripted-test manager.

## Built-in game-timer path

The strings:

- `Game Date` at `0x488b448`
- `gametimer_%04d%02d%02d_%02d%02d%02d` at `0x488b468`

both resolve to one validated function:

```text
0x3464410–0x3464858
```

The disassembly constructs a timestamped filename and later constructs a record containing the `Game Date` header. This strongly supports the earlier hypothesis that Jomini contains a built-in game-timer TSV writer.

The activation/caller path still needs mapping before this can replace manual wall-clock timing.

## Source-file anchors that did not directly resolve

Several source-path strings such as:

- `employment_helper.cpp`
- `employment_utils.cpp`
- `market.cpp`
- `world_market.cpp`
- `modifier.cpp`

did not yield trustworthy direct RIP-relative references with the current string-xref technique.

This does not mean the corresponding code is absent. Source-path strings are commonly used only by assertions/logging paths or may be referenced indirectly through tables.

The correct next mapping method for measured TickTask hotspots remains RTTI/vtable/task-registration correlation rather than assuming source-path xrefs will locate the hot implementation.

## Current static mapping confidence

| Area | Confidence before runtime data |
| --- | --- |
| TickTask dump/clear infrastructure | high |
| TaskThreadCount console handler | high |
| Script profiler command handlers | high |
| GUI/Clausewitz profiler entry handlers | high |
| scripted-test registration | high |
| Jomini game-timer writer | medium-high |
| range parallelization heuristic | high as a code anchor; low for exact source-level field semantics |
| Employment/Pop/Market hot implementations | intentionally unresolved pending measured hotspot selection |

## Next non-runtime work

The repository now also contains:

- `tools/map_static_xrefs.py` to reproduce the string-to-code mapping,
- `tools/generate_signatures.py` to generate exact-build secondary validation windows.

The next native mapping pass should use actual Phase 1 hotspot names to avoid broad speculative decompilation.
