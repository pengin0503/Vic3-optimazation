# Non-game research closeout implementation plan

> **For agentic workers:** Use superpowers:executing-plans / Native. No implementation subagents.

**Goal:** Complete the bounded non-game remainder and preserve exact limits.
**Architecture:** Add diagnostic details to the existing auditor; extend existing static triage with exact indirect witnesses; reuse synthetic GPU fixtures for a lifecycle/byte-count probe. Review and consolidate source on a research branch only.
**Tech Stack:** Python/unittest, Capstone, existing PE helpers, NumPy, Git/Markdown.
**Spec:** `docs/superpowers/specs/2026-10-12-offline-closeout-design.md`

## Global Constraints

- Exact exe SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`.
- No main/PR merge, game operation, scheduler/lock/performance patch; no invented GPU timings.
- Preserve existing phase reports/hash-pinned evidence; fresh refs, no force updates.
- Focused local tests, one final suite; no repetitive CI/native/B0 runs.
- Dedicated checkout reused; equivalent ledger `build/closeout/progress.md` because packaged workspace helpers are unavailable.

## Review Focus

- Parser diagnostics must survive JSON serialization without weakening rejection or alias protection.
- Indirect witness instruction boundaries must come from backed declared ranges, not arbitrary offsets.
- Ownership ambiguity, truncated decode and duplicate evidence must not invent verified callees/dependencies.
- GPU transfer models must disallow batching when the consumer requires intermediate outputs or host input updates.
- PR15/branch integration must preserve original sources and distinguish fake/controller tests, real GPU evidence and game performance; main remains unchanged.

## Task 1: Structured native rejection diagnostics

Files: `tools/check_cpu_runtime_gate.py`, `tests/test_check_cpu_runtime_gate.py`.
Interface: `NativeTraceError(ValueError)` with copied parser diagnostic list; `native_capture_invalid.parser_diagnostics` in output.

- [ ] Add a truncated/dropped trace test: rejection keeps the exact parser diagnostics, JSON survives, overhead null. Expected RED missing detail.
- [ ] Implement copied diagnostic detail without changing parser or native runtime. Expected GREEN full gate suite. Commit.

## Task 2: Exact indirect witnesses

Files: `tools/witness_ticktask_indirect_sites.py`, `tests/test_witness_ticktask_indirect_sites.py`, `research/generated/offline-closeout-2026-10-12/indirect-witnesses.json`.
Interfaces: `decode_witness(code: bytes, begin_rva: int, site_rva: int) -> dict`; `build_witnesses(binary: bytes, source: dict) -> dict`; stdout-only CLI `EXE_OR_ZIP SOURCE_JSON` (no input overwrite).

- [ ] RED owned machine-byte tests: call memory/register, tail jump, preceding context, exact bytes, wrong/non-boundary/direct site, partial decode and budget rejection. Source ownership reuses triage; no callee guessed.
- [ ] GREEN strict bounded implementation; verify exact input hash before PE interpretation. Commit code/tests.
- [ ] Run exact ZIP twice, compare bytes, assert 40 unique source sites, no dependency edges, source hashes unchanged. Save generated witnesses and bounded interpretation.

## Task 3: GPU lifecycle probe

Files: `research/experiments/gpu_offload_spike/resident_lifecycle_probe.py`, `test_resident_lifecycle_probe.py`, guide/generated model result.
Interface: `probe(case, stages, *, host_updates=False, intermediate_outputs=False) -> dict`; deterministic stdout CLI for fixed seed 4 scenarios ×3 sizes ×3 stage counts. Uses existing fixture and cpu_reference, independent scalar oracle in tests.

- [ ] RED: stage recurrence exact integer output/hash, input nonmutation, masked/large integer/empty cases, bounded stage/record/schema types. For final-only fixed input: upload12N, download4N; per-stage roundtrip: transfer16NS. Host updates/intermediate outputs make batched route null/unavailable; no fake GPU measurement.
- [ ] GREEN: compute final digest and explicit lifecycle model, always gpu_executed=false, times/bandwidth/speedup null. Run matrix once; no real GPU claimed. Commit.

## Task 4: Review, branch consolidation and report

Files: final report/roadmap/source links; unchanged PR15 source imported by branch consolidation only if compatible and reviewed.

- [ ] Inspect PR15 complete diff/CI and latest 3-session evidence; preserve NumPy vs optimized CPU and H2D-invalid distinctions. Keep Issue12/PR15 open pending separate main merge decision.
- [ ] One fresh-context final review covering all tasks and PR15. Fix Important/Critical findings in one TDD pass; record minors/declined judgments.
- [ ] If source consolidation is compatible, merge GPU research into CPU research branch (not main), retaining both parents. Verify merged tree, existing provenance and relevant tests. Run one final repository suite; run GPU CPU tests if dependency available or report exact limitation.
- [ ] Save final report, roadmap and commits to research branch; verify remote tree/head and unchanged main. No automatic claim of game/runtime gate or GPU hardware validation.
