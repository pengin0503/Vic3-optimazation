# Read-only Native Profiler Runtime Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build the first Windows x64 read-only Victoria 3 native profiler prototype for exact build 1.14.5, using an explicit attach loader, independent in-DLL validation, three validated TickTask tail anchors, low-overhead buffered telemetry, and the existing v1 trace format.

**Architecture:** Vic3OptimizationLoader.exe attaches only to an explicitly selected victoria3.exe PID after hashing the on-disk executable. It injects Vic3OptimizationProfiler.dll with LoadLibraryW. The DLL revalidates the build and all targets, installs MinHook-backed observation-only detours for three proven two-pointer/void TickTask tail anchors, writes FunctionBegin/FunctionEnd events into preallocated per-thread SPSC buffers, and drains them from a profiler-owned thread into the existing V3PF v1 trace format. No scheduler return value, game state, simulation cadence, or task data is modified.

**Tech Stack:** C++20, Windows x64, CMake 3.25+, Visual Studio 2022/MSVC, Win32 APIs, BCrypt, MinHook v1.3.4 pinned to commit c3fcafdc10146beb5919319d0683e44e3c30d537, Python 3 existing offline tools/tests.

**Spec:** docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md

**Runtime contracts:** research/hook-feasibility.md, research/native-profiler-event-format.md, research/native-profiler-runtime-targets-1.14.5.json, research/native-profiler-hook-abi-1.14.5.md

## Global Constraints

- Target only Victoria 3 Windows 1.14.5 executable SHA-256 9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54.
- Task 9 is observation only. Do not implement Task 11 or Task 12 behavior changes.
- Loader hash validation and DLL-side validation are independent; either failure arms zero hooks.
- Raw RVAs are corroborating exact-build metadata, never the primary runtime locator.
- A target requires exactly one signature match in executable .text, an executable hook address, and a matching vtable slot 6 pointer before it can be armed.
- Initial targets are exactly HandleAutonomousInvestment, ProcessEconomicMigration, and UpdateEmployment from research/native-profiler-runtime-targets-1.14.5.json.
- Initial detour ABI is exactly void(void* task_object, void* execution_context), justified only for those three target entries.
- Hot hooks perform no heap allocation, file I/O, formatting, mutex/critical-section acquisition, process enumeration, or symbol work.
- Tail-anchor duration must never be reported as total TickTask inclusive cost.
- Unsupported build, ambiguous signature, failed vtable check, exhausted thread-buffer pool, or malformed configuration must fail closed without changing simulation state.
- No claim of performance improvement is allowed from implementation or synthetic tests. Real-game overhead and correlation remain separate acceptance evidence.

## Review Focus

- Wrong-process or wrong-build attachment must stop before DLL injection.
- Signature data that matches bytes but not the expected vtable slot must not arm a hook.
- Hook entry/exit logging must preserve the two pointer arguments and normal game return path without changing the caller-visible result.
- Ring-buffer overflow or thread-pool exhaustion must drop telemetry rather than block a game thread.
- C++ trace bytes must remain parseable by tools/parse_native_profiler_trace.py and compatible with the committed v1 golden contract.

---

### Task 1: Tighten the benchmark comparison gate needed for profiler-overhead tests

**Files:**
- Modify: tools/check_benchmark_quality.py
- Modify: tests/test_check_benchmark_quality.py
- Modify: tools/README.md

**Interfaces:**
- Produces a workload-boundary fingerprint per measured TickTask CSV: frame count, min/max frame, and a deterministic multiset/hash of (frame, task, calls).
- Adds warning code workload_boundary_mismatch.
- valid_for_performance_claim is false when measured runs in one comparison group have mismatched boundaries.

- [ ] **Step 1: Write failing tests**

Add tests where three nominally identical runs have one extra frame and where frame/task/calls differ with identical row counts. Assert workload_boundary_mismatch and valid_for_performance_claim=false. Add a control test for identical boundaries.

- [ ] **Step 2: Verify RED**

Run: python -m unittest tests.test_check_benchmark_quality -v

- [ ] **Step 3: Implement boundary parsing and deterministic fingerprints**

Parse only the CSV columns frame, task, and calls. Do not compare milliseconds or longest_lock as workload identity. Report the exact differing run IDs and boundary summary.

- [ ] **Step 4: Verify GREEN and the preserved nine-run dataset**

Run focused tests, then run:
python tools/check_benchmark_quality.py benchmarks/measured-2026-10-05-3month-repeats --json local-data/repeat-quality-current.json

Expected: the known 12_r2 three-frame extension is surfaced as a workload_boundary_mismatch warning rather than silently treated as exact-boundary performance-ready evidence.

- [ ] **Step 5: Commit**

Commit message: test: enforce benchmark workload boundaries

---

### Task 2: Add the native build scaffold, dependency pin, and target database code generation

**Files:**
- Create: src/native/CMakeLists.txt
- Create: src/native/cmake/CompilerWarnings.cmake
- Create: third_party/licenses/MinHook.txt
- Create: tools/render_native_profiler_targets.py
- Create: tests/test_render_native_profiler_targets.py
- Create: src/native/generated/targets_1_14_5.inc
- Modify: .gitignore
- Modify: src/README.md

**Interfaces:**
- render_native_profiler_targets.py consumes research/native-profiler-runtime-targets-1.14.5.json and emits deterministic C++ constants for build hash, target IDs/names/ranges, vtable RVAs/slot, signature bytes/offsets, canonical targets JSON bytes, and target-table SHA-256.
- CMake builds only on WIN32 and x64; non-Windows configuration fails with a clear message.
- MinHook is fetched by CMake at exact commit c3fcafdc10146beb5919319d0683e44e3c30d537.

- [ ] **Step 1: Write failing deterministic-codegen tests**

Pin all three target IDs, exact signatures, canonical target JSON, and target-table SHA-256. Assert a duplicate target ID, invalid hex range, non-unique declared match count, or unsupported slot index is rejected.

- [ ] **Step 2: Verify RED**

Run: python -m unittest tests.test_render_native_profiler_targets -v

- [ ] **Step 3: Implement the renderer and generate targets_1_14_5.inc**

Do not hand-maintain a second copy of the target database. The generated include must state its source file and executable hash.

- [ ] **Step 4: Add CMake scaffold and MinHook license**

Use FetchContent with the pinned MinHook commit. Do not vendor binaries. Build directories and produced exe/dll/lib/pdb files remain ignored.

- [ ] **Step 5: Verify**

Run Python tests and regenerate the include twice; output must be byte-identical.

- [ ] **Step 6: Commit**

Commit message: build: add native profiler scaffold and target codegen

---

### Task 3: Implement shared exact-build validation and target resolution

**Files:**
- Create: src/native/common/Sha256.h
- Create: src/native/common/Sha256.cpp
- Create: src/native/common/PeImage.h
- Create: src/native/common/PeImage.cpp
- Create: src/native/common/TargetResolver.h
- Create: src/native/common/TargetResolver.cpp
- Create: src/native/tests/TargetResolverTests.cpp
- Modify: src/native/CMakeLists.txt

**Interfaces:**
- Sha256File(path) -> std::array<std::byte, 32>
- PeImage::FromModule(HMODULE) validates PE32+, AMD64, section bounds, and exposes executable sections.
- ResolveTarget(module, TargetSpec) returns a resolved address only when:
  1. exactly one signature match exists in .text,
  2. match minus offset_from_function_start lies in executable .text,
  3. module_base + vtable_rva is readable,
  4. vtable[6] equals the resolved hook address.
- Any failure returns a typed validation error; no guessed RVA fallback.

- [ ] **Step 1: Write failing resolver tests with synthetic PE-like fixtures**

Cover unique match, zero matches, duplicate matches, match outside executable section, bad vtable pointer, truncated PE metadata, and unsupported machine.

- [ ] **Step 2: Verify RED on Windows**

Run: cmake --build build --config Release --target NativeResolverTests && ctest --test-dir build -C Release -R NativeResolverTests --output-on-failure

- [ ] **Step 3: Implement minimal validators**

Use checked arithmetic for every RVA/size conversion. Do not scan writable sections.

- [ ] **Step 4: Verify GREEN**

Run the focused CTest target.

- [ ] **Step 5: Commit**

Commit message: feat: add fail-closed native target resolution

---

### Task 4: Implement the C++ V3PF v1 writer and fixed preallocated telemetry buffers

**Files:**
- Create: src/native/common/V3pfFormat.h
- Create: src/native/common/V3pfFormat.cpp
- Create: src/native/common/EventBuffer.h
- Create: src/native/common/EventBuffer.cpp
- Create: src/native/common/TraceWriter.h
- Create: src/native/common/TraceWriter.cpp
- Create: src/native/tests/V3pfFormatTests.cpp
- Create: src/native/tests/EventBufferTests.cpp
- Modify: src/native/CMakeLists.txt

**Interfaces:**
- V3PF serialization must match research/native-profiler-event-format.md exactly.
- FunctionBegin record size: 32 bytes.
- FunctionEnd record size: 40 bytes.
- Use QueryPerformanceCounter timestamps and GetCurrentThreadId.
- Thread buffer pool: 64 fixed buffers; each buffer has 1024 fixed event slots large enough for the current maximum 72-byte v1 record.
- A producer claims a buffer by atomic owner-thread ID. Producer/consumer indices are SPSC atomics.
- TryWrite never waits; overflow increments a drop counter.
- TraceWriter runs only on a profiler-owned thread and is the only component performing file I/O.

- [ ] **Step 1: Write failing cross-language golden tests**

Construct the same metadata/events as the existing Python v1 golden fixture and compare exact bytes where the fixture is identical. For runtime target metadata, parse produced output using tools/parse_native_profiler_trace.py in a CTest/Python compatibility step.

- [ ] **Step 2: Verify RED**

Run the focused native format tests.

- [ ] **Step 3: Implement packed explicit serialization**

Never fwrite an unpacked C++ struct as wire format. Serialize fields at specified offsets and zero all padding.

- [ ] **Step 4: Implement fixed SPSC event slots**

Do not allocate on TryWrite. A missing/overflowed buffer increments diagnostics and returns immediately.

- [ ] **Step 5: Verify GREEN plus Python parser compatibility**

Run native tests, then parse the produced trace with:
python tools/parse_native_profiler_trace.py <trace> --expected-executable-sha256 9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54

- [ ] **Step 6: Commit**

Commit message: feat: add native V3PF writer and event buffers

---

### Task 5: Implement profiler DLL lifecycle in disabled/no-hook mode first

**Files:**
- Create: src/native/profiler/DllMain.cpp
- Create: src/native/profiler/ProfilerRuntime.h
- Create: src/native/profiler/ProfilerRuntime.cpp
- Create: src/native/common/SharedConfig.h
- Create: src/native/tests/ProfilerRuntimeTests.cpp
- Modify: src/native/CMakeLists.txt

**Interfaces:**
- DllMain does only module-handle capture, DisableThreadLibraryCalls, and creation of one initialization thread; it never validates, scans, hooks, logs, or waits under loader lock.
- Loader/DLL configuration uses named shared memory Local\\Vic3OptimizationProfilerConfig-<pid> with a versioned fixed structure containing flags, output path, and enabled target bitmask.
- DLL copies configuration before signaling Local\\Vic3OptimizationProfilerReady-<pid>.
- disabled flag starts validation/trace diagnostics but arms zero game hooks.
- A named stop event Local\\Vic3OptimizationProfilerStop-<pid> requests orderly hook disable/trace finalization; the DLL may remain loaded but inert.

- [ ] **Step 1: Write failing lifecycle/config tests**

Cover missing mapping, bad config version/magic, oversized/non-terminated output path, disabled mode, and stop signaling.

- [ ] **Step 2: Verify RED**

Run the focused native tests.

- [ ] **Step 3: Implement initialization/control/flush thread ownership**

All heavy work occurs outside DllMain.

- [ ] **Step 4: Verify GREEN**

Ensure disabled mode creates no MinHook hook and produces only valid diagnostics/trace metadata.

- [ ] **Step 5: Commit**

Commit message: feat: add profiler DLL lifecycle and disabled mode

---

### Task 6: Add MinHook backend and the three observation-only TickTask detours

**Files:**
- Create: src/native/profiler/HookBackend.h
- Create: src/native/profiler/MinHookBackend.cpp
- Create: src/native/profiler/TickTaskHooks.h
- Create: src/native/profiler/TickTaskHooks.cpp
- Create: src/native/tests/TickTaskHookTests.cpp
- Modify: src/native/profiler/ProfilerRuntime.cpp
- Modify: src/native/CMakeLists.txt

**Interfaces:**
- HookBackend exposes Initialize, Create, Enable, Disable, Remove, Shutdown.
- TickTaskTailFn is exactly void(*)(void*, void*) for the three pinned targets.
- Each detour:
  1. obtains/claims the current thread buffer,
  2. allocates a thread-local correlation ID,
  3. writes FunctionBegin if possible,
  4. calls the exact original trampoline with unchanged task_object and execution_context,
  5. writes FunctionEnd if the original returns normally.
- If telemetry cannot be written, call the original immediately; telemetry failure never blocks or suppresses game execution.
- A target is armed only after TargetResolver passes all checks.
- Partial target validation is allowed only when configured: failed targets remain disabled and are named in diagnostics.

- [ ] **Step 1: Write failing hook tests against local fixture functions with the same two-pointer/void ABI**

Assert arguments and side effects are unchanged, exactly one original call occurs, Begin/End share thread/target/correlation ID, disabled target calls no detour, and ring overflow still calls original.

- [ ] **Step 2: Verify RED**

Run the focused native tests.

- [ ] **Step 3: Implement MinHook backend and detours**

Do not add scheduler, wait, allocator, child callback, or deeper economics hooks in this task.

- [ ] **Step 4: Verify GREEN**

Run hook tests and parse the produced test trace with the Python parser.

- [ ] **Step 5: Commit**

Commit message: feat: instrument three TickTask tail anchors

---

### Task 7: Implement the explicit PID loader and fail-closed injection path

**Files:**
- Create: src/native/loader/Main.cpp
- Create: src/native/loader/Injector.h
- Create: src/native/loader/Injector.cpp
- Create: src/native/tests/InjectorHost.cpp
- Create: src/native/tests/InjectionProbe.cpp
- Create: src/native/tests/InjectorTests.cpp
- Modify: src/native/CMakeLists.txt

**Interfaces:**
- CLI:
  Vic3OptimizationLoader.exe --pid <PID> [--dll <path>] [--output <trace>] [--targets investment,migration,employment] [--disabled]
  Vic3OptimizationLoader.exe --stop --pid <PID>
- Require explicit PID; do not inject into every process named victoria3.exe.
- QueryFullProcessImageNameW must resolve the target executable and the loader must hash that on-disk file before injection.
- Unknown hash exits nonzero before VirtualAllocEx/WriteProcessMemory/CreateRemoteThread.
- Injection writes only the DLL path into remote memory and invokes LoadLibraryW.
- Loader creates shared config before injection and waits for the ready event; timeout/failure is reported without retry loops or fallback addresses.

- [ ] **Step 1: Write failing injector primitive tests with a dedicated helper process/DLL**

Test remote LoadLibrary mechanics separately from the Victoria hash gate.

- [ ] **Step 2: Verify RED**

Run InjectorTests on Windows.

- [ ] **Step 3: Implement the injector and production hash gate**

Use the minimum required process rights and RAII handles. Free remote path memory after the LoadLibrary thread completes.

- [ ] **Step 4: Verify GREEN**

The helper injection test must pass; a non-Victoria process passed to the production loader must fail before injection.

- [ ] **Step 5: Commit**

Commit message: feat: add exact-build profiler attach loader

---

### Task 8: Add Windows CI, operator documentation, and the real-game verification handoff

**Files:**
- Modify: .github/workflows/tests.yml
- Modify: README.md
- Modify: src/README.md
- Create: docs/superpowers/guides/2026-10-05-native-profiler-runtime-validation-ja.md
- Create: docs/superpowers/reports/2026-10-05-native-profiler-runtime-implementation-handoff-ja.md

**Interfaces:**
- GitHub Actions keeps the existing Ubuntu Python job and adds a windows-2022 native job.
- Native CI configures x64 Release, builds, runs CTest, regenerates the target include, and parses generated V3PF traces with the Python parser.
- Runtime guide uses 12 threads as the diagnostic baseline and 16 as comparison, with exact workload boundaries and alternating order where comparisons are made.
- Real-game validation records profiler-disabled and profiler-enabled wall times, TickTask CSV, trace hash, enabled targets, dropped events, and build hash.

- [ ] **Step 1: Add Windows CI and run all repository tests**

Commands:
python -m unittest discover -s tests -v
cmake -S src/native -B build/native -A x64
cmake --build build/native --config Release
ctest --test-dir build/native -C Release --output-on-failure

- [ ] **Step 2: Add operator validation guide**

Require, before Task 9 can be called complete:
1. unsupported executable remains unmodified,
2. exact 1.14.5 loader/DLL validation succeeds,
3. three hooks produce parseable traces with no unexplained broken pairs,
4. built-in TickTask counts/timing can be correlated with native events,
5. profiler enabled-vs-disabled overhead is measured against repeated identical-boundary runs,
6. no game-state mutation exists.

- [ ] **Step 3: Run diff/format verification**

Run git diff --check and all tests. Read back generated target data and compare it to research/native-profiler-runtime-targets-1.14.5.json.

- [ ] **Step 4: Commit**

Commit message: ci: verify read-only native profiler prototype

---

## Explicit stop point

After Task 8 repository implementation, stop before any optimization patch.

Do not implement:

- scheduler decision override
- forced parallel execution/chunk count
- worker-count override
- lock removal or synchronization bypass
- cached/reused game-state data whose semantic equivalence is not proven
- Employment pass fusion
- allocation-elimination changes inside game code
- simulation cadence changes
- any Task 11 or Task 12 patch

The next action after repository implementation is Windows game validation of Task 9. Task 10 patch selection remains closed until observer overhead, matched runtime boundaries, and CPU/wait/critical-path evidence support a concrete safe intervention.
