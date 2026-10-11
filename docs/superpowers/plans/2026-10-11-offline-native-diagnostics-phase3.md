# Offline Native Diagnostics Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (Native). No subagent-driven-development. Execute continuously within the approved design.

**Goal:** Strengthen offline loader rejection diagnostics and missing lifecycle/shadow regressions without starting Victoria 3.

**Architecture:** Keep the existing Windows host, injector, DLL, PE resolver and B0. Extract only the injector's address/enumeration/read checks into platform-neutral production policy functions used by the Windows adapter. A separate offline test CMake entry point exercises those same policies and existing PE/buffer code; it does not build a loader or claim Windows integration success.

**Tech Stack:** C++20, CMake >=3.25, Python unittest, Windows x64 SDK for integration.

**Spec:** `docs/superpowers/specs/2026-10-11-offline-cpu-research-design.md`

## Global Constraints

- Exact Victoria 3 Windows 1.14.5 SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`; unsupported builds fail closed.
- No game launch, live-pointer API, scheduler changes, lock removal, forced parallelism or performance patches.
- Reuse existing native and Stage A/B0 components; synthetic success does not satisfy real-game gates.
- Commit each verified task to `research/offline-cpu-parallelism-20261011`; do not merge main.
- Use focused local verification per change and one final combined verification; Actions only at the final gate if useful/available.
- Windows integration not executed on Windows x64 remains explicitly unverified.

## Review Focus

- Module enumeration fails after finding one owner: reject with the immediately captured API error, not partial success (Task 1).
- Export's first byte is in range but its 16-byte probe crosses image/address boundaries: reject before any remote allocation (Task 1).
- Duplicate owner, size/bytes mismatch and stale GetLastError: diagnostics distinguish policy rejection from API error (Task 1).
- Stop signal exists without completion, or completion has a nonterminal status: no successful stop (Task 2).
- Nested original throws or telemetry has only one/free zero slots: original calls/exception/opaque return remain unchanged (Task 2).

## Existing coverage and baseline

- Native resolver already covers malformed/truncated PE, machine/magic, missing/ambiguous signature, writable/nonexec text, slot mismatch and arithmetic overflow.
- Injector already covers argument validation, diagnostic formatting, wrong-process CLI gate, invalid snapshot/query handle, successful synthetic injection and stopped/trace-failed IPC.
- Native hooks already cover arguments, one original call, full-buffer drop, stopped recording, throwing original and Windows MinHook.
- B0 already covers opaque bits, reentry, caught inner exception, proof/scope loss, saturation and partial drain. Add only combined exhaustion/reentry and zero-sized/FIFO drain cases.
- Baseline: Python 214 tests, 2 GPU tests skipped after installing pinned optional capstone; Stage A/B0 CTest 11/11 passed. No Windows SDK/runtime available.

### Task 1: Module resolution policies and diagnostics

**Files:** create `src/native/loader/ModuleResolutionPolicy.{h,cpp}`, `src/native/tests/ModuleResolutionTests.cpp`, `src/native/tests/PeFixture.h`, `src/native/tests/offline/CMakeLists.txt`; modify `src/native/loader/{Injector.cpp,ModuleResolutionDiagnostics.h}`, `src/native/tests/TargetResolverTests.cpp`, `src/native/CMakeLists.txt`.

**Interfaces:** `ValidateLocalExport(const PeImage&, uintptr_t owner_base, uintptr_t export_address, ModuleResolutionDiagnostics&) -> bool`; `ValidateRemoteModuleAddress(size_t local_size, size_t export_rva, uintptr_t remote_base, size_t remote_size, ModuleResolutionDiagnostics&) -> uintptr_t` (0 = rejected); `CompleteModuleEnumeration(uint32_t enumeration_error, ModuleResolutionDiagnostics&) -> bool` (0 = clean end); `ValidateRemoteExportRead(span<const byte,16> local, span<const byte,16> remote, size_t bytes_read, ModuleResolutionDiagnostics&) -> bool`.

- [ ] Write policy tests first: successful mapped `.text` export; below-owner/outside-text/writable PE; remote zero base, wrong size, RVA last 15 bytes, overflow; zero/duplicate matches; enumeration error after one match; short read and byte mismatch reset stale error.
- [ ] Run `g++ -std=c++20 -Wall -Wextra -Wpedantic -Werror src/native/tests/ModuleResolutionTests.cpp src/native/common/PeImage.cpp -o build/module-red`. Expected: missing production policy API (RED).
- [ ] Implement the named checks with existing `PeImage`/`CheckedAddress`; add `ModuleNext` and base/address diagnostic fields. Integrate checks in `RemoteLoadLibrary`: capture `Module32NextW` error immediately; accept only `ERROR_NO_MORE_FILES` as clean end; retain no fallback/retry.
- [ ] Extract the existing mapped PE fixture into test-only `PeFixture.h` for reuse. Add Windows and offline CTest targets without changing native's Windows-only configure gate.
- [ ] Configure/build `src/native/tests/offline` with warnings as errors; run CTest. Expected: policy, existing resolver and buffer tests pass. Read the Windows adapter diff; mark its compilation/execution unverified here.
- [ ] Commit `fix: fail closed on incomplete module enumeration and export bounds`.

### Task 2: Missing lifecycle and shadow failure regressions

**Files:** create `src/native/tests/HookFailureTests.cpp`; modify `src/native/tests/InjectorTests.cpp`, native/offline CMake targets, `src/lookup_reuse_contract/tests/NativeShadowTests.cpp`.

**Interfaces:** reuse `TickTaskHooks::Invoke/Active/StopRecording`, `EventBufferPool`, `StopProfilerSession`, `OfflineNativeShadow::Evaluate/DrainRecords` unchanged.

- [ ] Add real owned-object tests: nested hook return/throw keeps Active balanced and correlation pairs; one remaining slot drops End only; pool exhaustion and failed timestamp preserve original; stop during original preserves the in-flight pair and suppresses the next call's telemetry.
- [ ] Add named-IPC Windows regressions: absent mapping/events, timeout with no stopped signal, signaled Pending/Ready rejected, successful retry by the subscriber after completion (not injector retry). No sleeps or game host needed.
- [ ] Add B0 regressions: full records + reentrant inner throw preserves outer opaque bits/exact counts and drops only returned outer record; zero-sized drain preserves uniquely tagged FIFO records across partial drain/refill.
- [ ] Run focused tests. Existing-correct coverage may pass immediately; do not alter production solely to manufacture RED. Verify sensitivity using temporary copies with original suppressed / drain order reversed / Active decrement removed, never commit mutants. Expected: the new tests reject each mutant.
- [ ] Run offline native CTest plus Stage A/B0 CTest once; commit `test: cover native stop and nested telemetry failure paths`.

### Task 3: Final verification and evidence handoff

**Files:** create `docs/superpowers/reports/2026-10-11-offline-native-diagnostics-phase3-ja.md`; update `src/README.md`, operator guide and Phase 2 gate review; mark this plan's steps.

- [ ] Review the whole Phase 3 diff against all four source-of-truth files, preserve exact build gates and unchanged original behavior; record review method/findings.
- [ ] Run `python -m unittest discover -s tests`, scheduler model tests, both generated-include `--check`s, offline native CTest, Stage A/B0 CTest and `git diff --check` as final combined verification. Do not repeat absent new failures/changes.
- [ ] Record commands/counts, baseline dependency error, provenance hashes, mutations, Windows unverified items, code 4 still unresolved in the game and exact real-game acceptance conditions. Final CI is optional; do not open a PR merely to run every workflow.
- [ ] Commit `docs: record Phase 3 offline diagnostics and pending Windows gate`; push only the named research branch without force and verify its remote head.

## Execution decisions

The user supplied an approved design and explicitly authorized uninterrupted plan/implementation/commits, so no additional design/plan approval gate is introduced. The fresh dedicated clone on the named research branch isolates this task. Skill helper scripts are not exposed as executable resources here; keep the equivalent ledger locally in `build/phase3-progress.md` and preserve its substantive evidence in the final report.
