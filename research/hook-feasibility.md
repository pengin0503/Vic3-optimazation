# Native hook feasibility study

Target: Victoria 3 Windows 1.14.5

Scope: choose the architecture for **read-only native instrumentation**. Game-state-changing optimization patches are explicitly out of scope until measured hotspots exist.

## Options

### 1. Proxy DLL in the game directory

Mechanism: place a proxy such as a commonly loaded Windows DLL beside `victoria3.exe`, forward the real exports, then load the instrumentation module.

Advantages:

- loads early
- no separate injector step
- convenient after installation

Disadvantages:

- modifies the game directory
- can collide with other wrappers/mod loaders/graphics tools
- proxy choice is tied to the game's import behavior
- mistakes in forwarding can break startup
- less explicit fail/disable behavior for a research tool

Assessment: useful later for distribution convenience, but not preferred for the first research prototype.

### 2. Attach loader + injected DLL

Mechanism: user starts Victoria 3 normally, then a small loader selects the running `victoria3.exe`, validates the build, and loads an instrumentation DLL into that process.

Advantages:

- game directory can remain untouched
- explicit opt-in every run
- simple to disable: do not run the loader
- build hash can be checked before injection
- late attachment is sufficient for TickTask instrumentation after a save is loaded
- easier to distinguish loader failures from game startup failures

Disadvantages:

- requires process-open/injection permissions
- security software may treat remote DLL loading cautiously
- cannot observe the very earliest startup path

Assessment: **preferred Phase 4 architecture**.

### 3. Launch suspended, inject, then resume

Advantages:

- instrumentation can be installed before game initialization
- supports future early-lifecycle hooks

Disadvantages:

- more startup complexity
- more failure modes
- unnecessary for the current read-only TickTask goal

Assessment: reserve as an optional later loader mode if a measured target requires startup-time interception.

### 4. Debugger-only instrumentation

Ghidra/IDA/x64dbg/WinDbg breakpoints and ETW are valuable for research but are not a distributable performance extender. Use them to validate mappings, not as the final runtime architecture.

## Selected architecture

Phase 4 should use:

```text
Vic3OptimizationLoader.exe
        |
        | exact executable-path + SHA-256 gate
        v
running victoria3.exe
        |
        | LoadLibrary-style explicit injection
        v
Vic3OptimizationProfiler.dll
        |
        +-- build validation
        +-- section-aware signature scanner
        +-- structural validation
        +-- read-only hooks
        +-- low-overhead event/timing buffer
        +-- log/export
```

The loader attaches only after Victoria 3 is running. The first instrumentation DLL must not mutate simulation state.

## Two-stage fail-closed validation

### Loader gate

Before loading the DLL:

1. identify the target process explicitly
2. obtain the executable path
3. compute SHA-256 of the executable on disk
4. compare against a supported-build table
5. reject unknown builds by default

Initial supported executable:

`9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

### DLL gate

The injected DLL independently validates:

1. expected PE machine/section layout
2. module build identity
3. target signature match count
4. nearby bytes/control-flow assumptions
5. optional RTTI/vtable relationship where available

A failed check disables that hook. It must not fall back to a guessed address.

## Target resolution

Never store a raw absolute address as the primary locator.

Each target definition should contain:

- supported executable SHA-256
- target name
- section to scan
- masked byte signature
- expected match count, normally exactly one
- offset from match to hook point
- validation bytes/instructions around the candidate
- evidence/source notes
- optional RTTI/string-xref evidence

Addresses observed in Ghidra are build-specific research metadata only.

## Hooking library

Do not choose a hooking library until the first concrete function boundary is mapped. MinHook-style trampoline hooking is a reasonable candidate for ordinary x64 functions, but the project should keep the hook backend behind a small internal interface so a target that requires vtable/IAT/inline instrumentation does not force a redesign.

Any third-party hook library must have its license recorded before vendoring.

## Instrumentation data path

The first profiler should record only compact fixed-size events such as:

- timestamp/cycle counter
- target ID
- thread ID
- enter/exit or duration
- optional call counter

Avoid allocation, file I/O, symbol formatting, locks, and console output in a hot hook. Buffer in memory and flush from a separate low-priority path.

Measure profiler overhead against vanilla before trusting its results.

## Shutdown / recovery

Design requirements:

- every hook can be enabled independently
- partial signature failure leaves other validated hooks optional, but never enables the failed hook
- a global `disabled` configuration starts the DLL without hooks for loader diagnostics
- retain original bytes/trampolines until clean shutdown
- logging must identify exact executable hash and enabled target signatures
- crashes during research must never trigger automatic patching on the next unknown build

## Multiplayer and determinism

The instrumentation milestone is intended for local performance research. Do not claim multiplayer compatibility. Later optimization patches require explicit determinism/save-state validation even if the read-only profiler itself appears benign.

## Implementation gate

Do not implement the injected DLL yet.

Start Task 9 only after:

- real Phase 1 benchmark data exists
- at least one OS-level trace is correlated
- one to three native target functions are mapped with sufficient confidence

Until then, this document is the selected architecture, not authorization to patch speculative targets.
