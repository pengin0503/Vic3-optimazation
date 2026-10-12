# Offline TickTask Gap Triage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task, with test-driven-development and verification-before-completion. Steps use checkbox (`- [ ]`) syntax for tracking. No subagents.

**Goal:** Convert pre-existing exact-build unresolved TickTask structural evidence into a deterministic, evidence-preserving offline work queue without inferring dependencies or performance gains.

**Architecture:** One standard-library Python helper exposes a pure triage function and a small CLI. It consumes the existing versioned dependency artifact unmodified. Tests use owned JSON fixtures; CLI validates first, then writes fresh output. One short handoff document connects future scheduler/native/measurement gates to this output.

**Tech Stack:** Python 3.11+ standard library, unittest; existing JSON artifact.

**Spec:** `docs/superpowers/specs/2026-10-11-offline-cpu-research-design.md`

## Global Constraints

- Exact Windows Victoria 3 1.14.5 hash `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`.
- No game process, injection, native patch, save edit, scheduler override, forced parallelization or live memory read.
- Preserve original `unresolved` records and classify under transparent reason categories; no parent-child edges from calls or shared references.
- Existing `tools/map_ticktask_dependencies.py`, native runtime/lookup shadow contracts, V3PF and measurement artifacts remain unchanged.
- Use Native / executing-plans, no subagents, local tests before CI. Do not run GitHub Actions during each development step.
- Input provenance and unresolved uncertainty must be explicit in every output.

## Review Focus

- Invalid SHA or version must reject input, not silently produce seemingly valid analysis.
- `rva == end_rva` is *outside* a half-open function range.
- Overlapping function ranges must mark owner ambiguous, not select first.
- Unknown unresolved reasons remain present verbatim in `other` class.
- Non-object JSON / malformed RVAs must fail without partially overwriting a previous output.

---

### Task 1: Evidence schema, grouping and conservative owner lookup

**Files:**
- Create: `tools/triage_ticktask_unresolved.py`
- Create: `tests/test_triage_ticktask_unresolved.py`

**Interfaces:**
- Consumes: version 1 `research/generated/ticktask-dependencies-1.14.5.json` with `functions[].ranges[].begin_rva/end_rva` and `unresolved[]`.
- Produces: `build_triage(document: dict) -> dict` with `format_version=1`, `executable_sha256`, `source_unresolved_count`, `input_dependency_edges`, `by_reason`, `work_items`, `warning`.

- [ ] **Step 1: Write failing tests**
  - `test_classifies_without_inventing_edges`: valid fixture with indirect, metadata, dataflow, unknown records, verify exact categories and original fields, `runtime_verified=False`.
  - `test_owner_half_open_and_ambiguous`: interior RVA maps to one function, endpoint maps to none, overlaps map to none with `ownership_ambiguous=True`.
  - `test_rejects_wrong_build_and_malformed_inputs`: wrong version/hash/list/types/invalid RVA reject; input remains unchanged.
- [ ] **Step 2: Run RED**
  - `python -m unittest discover -s tests -p test_triage_ticktask_unresolved.py -v`.
  - Expected: missing module/API fails.
- [ ] **Step 3: Implement**
  - Add strict `_rva(value: str) -> int` for canonical `0x` hexadecimal strings and finite nonnegative values.
  - Add `build_triage(document: dict) -> dict`; check all invariants before returning. Preserve original entries by copying.
  - Function ownership only from validated `ranges`; multiple matching *distinct* functions yield null + ambiguity.
  - Deterministically order `work_items` by category, RVA, reason and input ordinal; report `by_reason` counts.
- [ ] **Step 4: Run GREEN + full available tests**
  - Same unittest command; then `python -m unittest discover -s tests -v` in complete local checkout when possible.
  - Expected: zero failures. If local full checkout unavailable, record precise limitation.
- [ ] **Step 5: Commit**
  - `git add tools/triage_ticktask_unresolved.py tests/test_triage_ticktask_unresolved.py && git commit -m "research: triage unresolved TickTask static evidence safely"`

### Task 2: CLI safety, provenance and repeatability

**Files:**
- Modify: `tools/triage_ticktask_unresolved.py`
- Modify: `tests/test_triage_ticktask_unresolved.py`

**Interfaces:**
- Consumes: Task 1 `build_triage`.
- Produces: `main(argv: list[str] | None = None) -> int`; accepts positional input JSON and mandatory `--output`.

- [ ] **Step 1: Write failing CLI tests**
  - `test_cli_repeatable_and_source_hash`: same fixture creates byte-identical JSON at two output paths; `source_json_sha256` equals raw input bytes SHA-256.
  - `test_cli_invalid_input_preserves_existing_output`: malformed input returns 2 and does not overwrite an existing output.
  - `test_cli_refuses_input_as_output`: same resolved path returns 2 without writing.
- [ ] **Step 2: Run RED**
  - `python -m unittest discover -s tests -p test_triage_ticktask_unresolved.py -v`.
  - Expected: missing CLI behavior fails.
- [ ] **Step 3: Implement**
  - JSON `UTF-8`, stable `json.dumps(sort_keys=True, indent=2)` plus final newline.
  - Catch known input and validation errors; reject same source/destination path; create output directory only after validation.
  - `source_json_sha256` is raw input bytes digest, independent of filename and whitespace.
- [ ] **Step 4: Run GREEN**
  - Focused tests, then full locally available suite; compare two CLI outputs byte-for-byte.
- [ ] **Step 5: Commit**
  - `git add tools/triage_ticktask_unresolved.py tests/test_triage_ticktask_unresolved.py && git commit -m "research: add deterministic fail-closed TickTask triage CLI"`

### Task 3: Document downstream gates without claiming a speedup

**Files:**
- Create: `docs/superpowers/reports/2026-10-11-offline-cpu-research-handoff-ja.md`
- Modify: `docs/superpowers/specs/2026-10-11-offline-cpu-research-design.md` only for factual corrections, if needed.

**Interfaces:**
- Consumes: Task 1 and 2 output contract plus existing read-only measurements.
- Produces: documented command, category meanings, exact-build proof constraints, next offline directions for scheduler synthetic probes and Windows host, and the runtime gate.

- [ ] **Step 1: Verify known baseline**
  - Reconcile 41 functions, 0 confirmed edges, existing unresolved evidence, 8/12/16 thread repeated timing and Stage A/B0 status against source docs.
- [ ] **Step 2: Document reproducible invocation**
  - `python tools/triage_ticktask_unresolved.py research/generated/ticktask-dependencies-1.14.5.json --output local-data/ticktask-triage.json`.
  - Record tests actually executed, no invented native equality / game speedup / CPU utilization.
- [ ] **Step 3: Review**
  - Check all links and path casing, `git diff --check`; copy no game binary into commit.
- [ ] **Step 4: Commit**
  - `git add docs/superpowers/reports/2026-10-11-offline-cpu-research-handoff-ja.md && git commit -m "docs: hand off offline CPU research and evidence gates"`

## Later workstreams (separate small plans, no premature patch)

1. Bounded scheduler-job creation/registration structural investigation using exact binary and this work queue; require explicit dataflow attestation for new graph edges.
2. Synthetic task scheduler/chunking model with input-owned task weights, dependencies, barrier/wakeup costs; always label synthetic, do not extrapolate game speed.
3. Windows native profiler diagnostic-host coverage and B0 live-lifetime obligations, gated on existing attach diagnostics.
4. Offline evidence-gate report synthesizing known CPU/tick/OS capture limitations and exact next real-game measurements.

The three tasks above are independently useful without any new game measurement. These later tracks are not declared complete by this plan.
